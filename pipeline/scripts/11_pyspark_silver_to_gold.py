# -*- coding: utf-8 -*-
"""
PIPELINE PYSPARK: SILVER → GOLD
====================================
Lê a camada Silver (Parquet/Delta), produz agregados analíticos de negócio
e treina o modelo de attrition com Spark ML (MLlib).

Stack simulada:
  - AWS: S3 (Silver) → AWS Glue / EMR Serverless → S3 (Gold/Parquet)
  - Azure: ADLS Gen2 → Databricks (Delta Live Tables) → Synapse Analytics

Em produção, este job seria orquestrado pelo Apache Airflow (DAG diário às 06h)
e armazenado no Databricks Unity Catalog com controle de linhagem (lineage).
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.ml import Pipeline as MLPipeline
from pyspark.ml.feature import VectorAssembler, StringIndexer, StandardScaler
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
import json, os
from datetime import datetime, timedelta

SILVER_PATH = "pipeline/silver/colaboradores"
GOLD_PATH   = "pipeline/gold"
os.makedirs(GOLD_PATH, exist_ok=True)

def create_spark_session():
    return (
        SparkSession.builder
        .appName("BV_People_Analytics_Silver_to_Gold")
        .master("local[*]")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

def run_gold_pipeline():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    print("=" * 70)
    print("SILVER → GOLD | PySpark ML Pipeline")
    print("=" * 70)

    # ── LEITURA SILVER ──────────────────────────────────────────────────────
    df = spark.read.parquet(SILVER_PATH)
    print(f"\nSilver carregada: {df.count():,} linhas | {len(df.columns)} colunas")

    # ── MÓDULO 1: SÉRIE TEMPORAL MENSAL ─────────────────────────────────────
    print("\n[1/4] Calculando série mensal...")
    df_ativos = df.filter(F.col("status").isin("Ativo", "Desligado"))

    # Extrai ano-mês da data de admissão e desligamento para séries temporais
    df_mensal_hc = (
        df_ativos
        .withColumn("competencia", F.date_format("data_admissao", "yyyy-MM"))
        .groupBy("competencia", "area")
        .agg(
            F.count("matricula").alias("admissoes"),
            F.avg("engajamento_score_base").alias("engajamento_medio"),
            F.avg("salario_mensal").alias("salario_medio"),
            F.avg("performance_score").alias("performance_medio"),
        )
        .orderBy("competencia", "area")
    )

    df_deslig = (
        df.filter(F.col("data_desligamento").isNotNull())
          .withColumn("competencia", F.date_format("data_desligamento", "yyyy-MM"))
          .groupBy("competencia", "area")
          .agg(
              F.count("matricula").alias("desligamentos"),
              F.sum(F.when(F.col("tipo_desligamento") == "Voluntário", 1).otherwise(0)).alias("voluntarios"),
          )
    )

    gold_serie = df_mensal_hc.join(df_deslig, ["competencia","area"], "left").fillna(0)
    gold_serie.write.mode("overwrite").parquet(f"{GOLD_PATH}/serie_mensal")
    print(f"  Série mensal: {gold_serie.count()} linhas")

    # ── MÓDULO 2: RISCO POR ÁREA (agregado) ─────────────────────────────────
    print("\n[2/4] Calculando risk score por área...")
    gold_area = (
        df.filter(F.col("status") == "Ativo")
          .groupBy("area")
          .agg(
              F.count("matricula").alias("headcount"),
              F.avg("engajamento_score_base").alias("engajamento_medio"),
              F.avg("salario_mensal").alias("salario_medio"),
              F.avg("performance_score").alias("performance_medio"),
              F.stddev("engajamento_score_base").alias("engajamento_std"),
          )
          .withColumn("risco_proxy",
              # Proxy de risco: quanto menor o engajamento e maior a volatilidade, maior o risco
              (10 - F.col("engajamento_medio")) * 0.7 +
              F.coalesce(F.col("engajamento_std"), F.lit(0)) * 0.3
          )
          .orderBy(F.desc("risco_proxy"))
    )
    gold_area.write.mode("overwrite").parquet(f"{GOLD_PATH}/risco_por_area")
    print(f"  Risco por área: {gold_area.count()} linhas")

    # ── MÓDULO 3: MODELO PREDITIVO COM SPARK ML ─────────────────────────────
    print("\n[3/4] Treinando modelo preditivo (Spark MLlib)...")
    DATA_REF = datetime(2025, 6, 30)

    # Elegíveis: ativos na data de referência
    elegiveis = df.filter(
        (F.to_date(F.lit(DATA_REF.strftime("%Y-%m-%d"))) >= F.col("data_admissao")) &
        (
            F.col("data_desligamento").isNull() |
            (F.col("data_desligamento") > F.to_date(F.lit(DATA_REF.strftime("%Y-%m-%d"))))
        )
    )

    # Target: saiu voluntariamente nos 12 meses seguintes
    DATA_FIM = DATA_REF + timedelta(days=365)
    elegiveis = elegiveis.withColumn("label",
        F.when(
            F.col("data_desligamento").isNotNull() &
            (F.col("data_desligamento") > F.to_date(F.lit(DATA_REF.strftime("%Y-%m-%d")))) &
            (F.col("data_desligamento") <= F.to_date(F.lit(DATA_FIM.strftime("%Y-%m-%d")))) &
            (F.col("tipo_desligamento") == "Voluntário"),
            F.lit(1.0)
        ).otherwise(F.lit(0.0))
    ).withColumn("tempo_casa_dias",
        F.datediff(
            F.to_date(F.lit(DATA_REF.strftime("%Y-%m-%d"))),
            F.col("data_admissao")
        ).cast("double")
    )

    # Features categóricas → numéricas
    cat_features = ["area", "senioridade", "genero", "cidade"]
    indexers = [
        StringIndexer(inputCol=c, outputCol=f"{c}_idx", handleInvalid="keep")
        for c in cat_features
    ]
    num_features = [
        "idade", "tempo_casa_dias", "salario_mensal",
        "engajamento_score_base", "performance_score", "produtividade_index_base"
    ] + [f"{c}_idx" for c in cat_features]

    assembler = VectorAssembler(inputCols=num_features, outputCol="features_raw")
    scaler = StandardScaler(inputCol="features_raw", outputCol="features")
    clf = RandomForestClassifier(
        labelCol="label", featuresCol="features",
        numTrees=100, maxDepth=6, minInstancesPerNode=15,
        seed=42
    )

    ml_pipeline = MLPipeline(stages=indexers + [assembler, scaler, clf])

    # Split treino/teste (sem vazamento temporal)
    train, test = elegiveis.randomSplit([0.75, 0.25], seed=42)
    print(f"  Treino: {train.count():,} | Teste: {test.count():,} | Positivos treino: {train.filter(F.col('label')==1).count():,}")

    model = ml_pipeline.fit(train)
    predictions = model.transform(test)

    evaluator = BinaryClassificationEvaluator(labelCol="label", metricName="areaUnderROC")
    auc = evaluator.evaluate(predictions)
    print(f"  ROC-AUC: {auc:.3f}")

    # Score nos ativos de hoje
    ativos_hoje = df.filter(F.col("status") == "Ativo").withColumn(
        "tempo_casa_dias",
        F.datediff(F.current_date(), F.col("data_admissao")).cast("double")
    )
    scored = model.transform(ativos_hoje)
    scored_gold = scored.select(
        "matricula", "area", "cargo", "senioridade",
        "engajamento_score_base", "performance_score",
        F.col("probability").getItem(1).alias("risco_attrition_score")
    )
    scored_gold.write.mode("overwrite").parquet(f"{GOLD_PATH}/scores_attrition")
    print(f"  Scores gerados: {scored_gold.count():,} colaboradores")

    # Salva métricas
    metrics = {"roc_auc": round(auc, 3), "n_treino": int(train.count()), "n_teste": int(test.count())}
    with open(f"{GOLD_PATH}/metricas_modelo_pyspark.json","w") as f:
        json.dump(metrics, f, indent=2)

    # ── MÓDULO 4: NINE-BOX GOLD ─────────────────────────────────────────────
    print("\n[4/4] Calculando 9-Box Grid...")
    # Performance 1-3 baseada em performance_score (1-5 original)
    # Potencial 1-3 baseado em engajamento + tempo de casa
    ativos = df.filter(F.col("status") == "Ativo")
    nine_box = ativos.withColumn("perf_box",
        F.when(F.col("performance_score") >= 4.0, 3)
         .when(F.col("performance_score") >= 3.0, 2)
         .otherwise(1)
    ).withColumn("pot_box",
        F.when(
            (F.col("engajamento_score_base") >= 7.5) &
            (F.col("tempo_casa_meses") <= 60),
            3
        ).when(F.col("engajamento_score_base") >= 6.0, 2)
         .otherwise(1)
    ).groupBy("perf_box","pot_box","area").agg(
        F.count("matricula").alias("headcount"),
        F.avg("engajamento_score_base").alias("engajamento_medio"),
        F.avg("salario_mensal").alias("salario_medio"),
    ).orderBy("pot_box","perf_box","area")

    nine_box.write.mode("overwrite").parquet(f"{GOLD_PATH}/nine_box_grid")
    print(f"  9-Box Grid: {nine_box.count()} células")

    print("\n" + "=" * 70)
    print("Gold completa — ROC-AUC:", round(auc,3))
    print("=" * 70)
    spark.stop()

if __name__ == "__main__":
    run_gold_pipeline()
