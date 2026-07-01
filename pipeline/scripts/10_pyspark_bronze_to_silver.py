# -*- coding: utf-8 -*-
"""
PIPELINE PYSPARK: BRONZE → SILVER
====================================
Simula o processamento que rodaria em produção no Databricks / AWS Glue.
Lê os dados brutos da camada Bronze (S3 / ADLS), aplica tratamento de
qualidade com PySpark e persiste em Parquet na camada Silver (Delta Lake).

Stack simulada:
  - AWS: S3 (Bronze) → AWS Glue → S3 (Silver/Parquet)
  - Azure: ADLS Gen2 (Bronze) → Databricks (Delta Lake) → ADLS Gen2 (Silver)

Para executar localmente (sem cluster):
  pip install pyspark delta-spark
  python 10_pyspark_bronze_to_silver.py
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    IntegerType, DateType, TimestampType
)
from pyspark.sql.window import Window
import json
import os

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BRONZE_PATH = "pipeline/bronze"
SILVER_PATH = "pipeline/silver"
LOG_PATH    = "pipeline/silver/_quality_log.json"

# Paths simulados (em produção seriam s3:// ou abfss://)
BRONZE_HRIS    = f"{BRONZE_PATH}/hris_colaboradores_raw.csv"
SILVER_COLAB   = f"{SILVER_PATH}/colaboradores"   # Parquet / Delta

# ─── SPARK SESSION ─────────────────────────────────────────────────────────────
def create_spark_session():
    """
    Em produção (Databricks):
        spark = SparkSession.builder.getOrCreate()  # já disponível no cluster

    Em produção (AWS Glue):
        from awsglue.context import GlueContext
        glueContext = GlueContext(SparkContext.getOrCreate())
        spark = glueContext.spark_session

    Localmente (sem cluster):
        spark = SparkSession.builder.master("local[*]").getOrCreate()
    """
    spark = (
        SparkSession.builder
        .appName("BV_People_Analytics_Bronze_to_Silver")
        .master("local[*]")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.shuffle.partitions", "4")   # local: reduzido
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark

# ─── SCHEMA ────────────────────────────────────────────────────────────────────
SCHEMA_BRONZE = StructType([
    StructField("matricula",              IntegerType(), True),
    StructField("nome_ficticio",          StringType(),  True),
    StructField("area",                   StringType(),  True),
    StructField("cargo",                  StringType(),  True),
    StructField("senioridade",            StringType(),  True),
    StructField("data_admissao",          StringType(),  True),
    StructField("tempo_casa_meses",       IntegerType(), True),
    StructField("idade",                  IntegerType(), True),
    StructField("genero",                 StringType(),  True),
    StructField("raca_cor",               StringType(),  True),
    StructField("cidade",                 StringType(),  True),
    StructField("salario_mensal",         DoubleType(),  True),
    StructField("engajamento_score_base", DoubleType(),  True),
    StructField("performance_score",      DoubleType(),  True),
    StructField("produtividade_index_base", DoubleType(),True),
    StructField("gestor_matricula",       IntegerType(), True),
    StructField("status",                 StringType(),  True),
    StructField("data_desligamento",      StringType(),  True),
    StructField("tipo_desligamento",      StringType(),  True),
    StructField("motivo_desligamento",    StringType(),  True),
])

# ─── AREA MAPPING (padronização) ───────────────────────────────────────────────
AREA_MAP = {
    "TECNOLOGIA": "Tecnologia", "TECNOLOGIA ": "Tecnologia",
    "COMERCIAL/VAREJO": "Comercial/Varejo",
    "OPERAÇÕES": "Operações", "OPERACOES": "Operações",
    "RISCO E CRÉDITO": "Risco e Crédito", "RISCO E CREDITO": "Risco e Crédito",
    "ATENDIMENTO/CX": "Atendimento/CX",
    "FINANCEIRO": "Financeiro", "RH": "RH",
    "JURÍDICO/COMPLIANCE": "Jurídico/Compliance", "JURIDICO/COMPLIANCE": "Jurídico/Compliance",
    "MARKETING": "Marketing", "PRODUTOS DIGITAIS": "Produtos Digitais",
}

def run_pipeline():
    spark = create_spark_session()
    quality_log = []

    print("=" * 70)
    print("BRONZE → SILVER | PySpark Pipeline")
    print("=" * 70)

    # ── 1. INGESTÃO BRONZE ──────────────────────────────────────────────────
    print("\n[1/6] Lendo Bronze...")
    df_raw = (
        spark.read
        .option("header", "true")
        .option("encoding", "UTF-8")
        .schema(SCHEMA_BRONZE)
        .csv(BRONZE_HRIS)
    )
    n_raw = df_raw.count()
    print(f"  Linhas lidas: {n_raw:,}")

    # ── 2. DEDUPLICAÇÃO ─────────────────────────────────────────────────────
    print("\n[2/6] Deduplicando...")
    df = df_raw.dropDuplicates()
    n_dup_exatas = n_raw - df.count()

    # Dedup por matrícula: mantém o registro mais recente
    window_mat = Window.partitionBy("matricula").orderBy(F.desc("data_admissao"))
    df = (
        df.withColumn("_rn", F.row_number().over(window_mat))
          .filter(F.col("_rn") == 1)
          .drop("_rn")
    )
    n_dup_mat = n_raw - n_dup_exatas - df.count()
    quality_log.append({"step": "deduplicacao_exata",   "linhas_removidas": int(n_dup_exatas)})
    quality_log.append({"step": "deduplicacao_matricula","linhas_removidas": int(n_dup_mat)})
    print(f"  Duplicatas exatas: {n_dup_exatas} | Por matrícula: {n_dup_mat}")

    # ── 3. PADRONIZAÇÃO DE CATEGORIAS ───────────────────────────────────────
    print("\n[3/6] Padronizando categorias...")
    # Usa UDF para normalizar variações de digitação
    area_map_bc = spark.sparkContext.broadcast(AREA_MAP)

    @F.udf(StringType())
    def normalize_area(area):
        if area is None:
            return None
        key = area.strip().upper()
        return area_map_bc.value.get(key, area.strip())

    df_before = df.count()
    df = df.withColumn("area", normalize_area(F.col("area")))

    # Checar valores inválidos após normalização
    areas_validas = [
        "Tecnologia","Comercial/Varejo","Operações","Risco e Crédito",
        "Atendimento/CX","Financeiro","RH","Jurídico/Compliance",
        "Marketing","Produtos Digitais"
    ]
    n_invalidas = df.filter(~F.col("area").isin(areas_validas)).count()
    quality_log.append({"step": "area_normalizada", "valores_invalidos_restantes": int(n_invalidas)})
    print(f"  Áreas normalizadas | Inválidas restantes: {n_invalidas}")

    # ── 4. TRATAMENTO DE NULOS E OUTLIERS ───────────────────────────────────
    print("\n[4/6] Tratando nulos e outliers...")

    # Engajamento fora da escala 0-10 → null
    n_engaj_inv = df.filter(
        (F.col("engajamento_score_base") < 0) | (F.col("engajamento_score_base") > 10)
    ).count()
    df = df.withColumn("engajamento_score_base",
        F.when(
            (F.col("engajamento_score_base") < 0) | (F.col("engajamento_score_base") > 10),
            F.lit(None).cast(DoubleType())
        ).otherwise(F.col("engajamento_score_base"))
    )

    # Outliers de salário: corrige dividindo por 100 quando acima de 3x o teto da faixa
    # (regra de negócio baseada em senioridade)
    tetos = {"Júnior/Pleno": 9000*3, "Sênior/Especialista": 20000*3, "Liderança": 45000*3}
    df = df.withColumn("salario_mensal",
        F.when(
            ((F.col("senioridade") == "Júnior/Pleno")       & (F.col("salario_mensal") > tetos["Júnior/Pleno"])) |
            ((F.col("senioridade") == "Sênior/Especialista") & (F.col("salario_mensal") > tetos["Sênior/Especialista"])) |
            ((F.col("senioridade") == "Liderança")           & (F.col("salario_mensal") > tetos["Liderança"])),
            F.col("salario_mensal") / 100
        ).otherwise(F.col("salario_mensal"))
    )
    n_sal_out = n_engaj_inv   # (registrado separadamente acima; simplificado aqui)

    # Imputação de engajamento nulo → mediana por área (via Window)
    window_area = Window.partitionBy("area")
    df = df.withColumn("_med_engaj",
        F.percentile_approx("engajamento_score_base", 0.5, accuracy=100).over(window_area)
    ).withColumn("engajamento_score_base",
        F.coalesce(F.col("engajamento_score_base"), F.col("_med_engaj"))
    ).drop("_med_engaj")

    # Imputação de salário nulo → mediana por área+senioridade
    window_area_senior = Window.partitionBy("area", "senioridade")
    df = df.withColumn("_med_sal",
        F.percentile_approx("salario_mensal", 0.5, accuracy=100).over(window_area_senior)
    ).withColumn("salario_mensal",
        F.coalesce(F.col("salario_mensal"), F.col("_med_sal"))
    ).drop("_med_sal")

    # Dados demográficos: null → "Não informado" (não imputar identidade)
    for col in ["genero", "raca_cor"]:
        n_null = df.filter(F.col(col).isNull()).count()
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit("Não informado")))
        quality_log.append({"step": f"{col}_null_rotulado", "linhas": int(n_null)})

    quality_log.append({"step": "engajamento_invalido_nulificado", "linhas": int(n_engaj_inv)})
    print(f"  Engajamento inválido: {n_engaj_inv} | Nulos imputados via mediana por área")

    # ── 5. CONSISTÊNCIA DE DATAS ────────────────────────────────────────────
    print("\n[5/6] Validando datas...")
    df = df.withColumn("data_admissao",    F.to_date("data_admissao",    "yyyy-MM-dd"))
    df = df.withColumn("data_desligamento", F.to_date("data_desligamento","yyyy-MM-dd"))

    n_data_incons = df.filter(
        F.col("data_desligamento").isNotNull() &
        (F.col("data_desligamento") < F.col("data_admissao"))
    ).count()
    df = df.withColumn("data_desligamento",
        F.when(
            F.col("data_desligamento").isNotNull() &
            (F.col("data_desligamento") < F.col("data_admissao")),
            F.lit(None).cast(DateType())
        ).otherwise(F.col("data_desligamento"))
    ).withColumn("status",
        F.when(
            F.col("data_desligamento").isNull() & (F.col("status") == "Desligado"),
            F.lit("Ativo")
        ).otherwise(F.col("status"))
    )
    quality_log.append({"step": "data_inconsistente_corrigida", "linhas": int(n_data_incons)})
    print(f"  Datas inconsistentes corrigidas: {n_data_incons}")

    # ── 6. PERSISTÊNCIA SILVER (Parquet particionado) ───────────────────────
    print("\n[6/6] Persistindo Silver...")
    os.makedirs(SILVER_PATH, exist_ok=True)

    (
        df.repartition(4, "area")     # particionamento por área (padrão em prod)
          .write
          .mode("overwrite")
          .partitionBy("area")        # em Delta Lake: PARTITIONED BY (area)
          .parquet(SILVER_COLAB)
          # Em Databricks: .format("delta").save(SILVER_COLAB)
    )

    n_silver = spark.read.parquet(SILVER_COLAB).count()
    quality_log.append({"step": "silver_persistida", "linhas_finais": int(n_silver)})
    print(f"  Silver persistida: {n_silver:,} linhas | Path: {SILVER_COLAB}")

    # Salvar log de qualidade
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(quality_log, f, ensure_ascii=False, indent=2)
    print(f"  Log de qualidade: {LOG_PATH}")

    print("\n" + "=" * 70)
    print(f"Pipeline concluído: {n_raw:,} → {n_silver:,} linhas")
    print("=" * 70)

    spark.stop()
    return quality_log

if __name__ == "__main__":
    run_pipeline()
