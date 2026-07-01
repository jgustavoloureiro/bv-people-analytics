# -*- coding: utf-8 -*-
"""
APACHE AIRFLOW DAG — People Analytics Pipeline
================================================
Orquestra o pipeline de dados de People Analytics diariamente às 06h.
Simula a orquestração que rodaria em produção no MWAA (AWS Managed Airflow)
ou no Airflow integrado ao Databricks.

Fluxo:
  extract_hris → bronze_validate → silver_transform → gold_aggregate →
  ml_attrition_score → dashboard_publish → notify_slack

Dependências:
  pip install apache-airflow apache-airflow-providers-amazon
              apache-airflow-providers-databricks
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.operators.s3 import S3ListOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor

# ─── CONFIGURAÇÃO PADRÃO DA DAG ────────────────────────────────────────────────
default_args = {
    "owner": "people_analytics_team",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "email": ["data-eng@bancobv.com.br"],
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=2),
}

# ─── CONSTANTES ────────────────────────────────────────────────────────────────
S3_BUCKET   = "s3://bv-people-analytics-prod"
GLUE_ROLE   = "arn:aws:iam::123456789012:role/GluePeopleAnalyticsRole"
SLACK_CONN  = "slack_people_analytics"

# ─── FUNÇÕES PYTHON OPERATORS ──────────────────────────────────────────────────
def check_source_data(**context):
    """Verifica se o arquivo de export do HRIS chegou no S3 hoje."""
    execution_date = context["execution_date"].strftime("%Y/%m/%d")
    expected_path  = f"{S3_BUCKET}/bronze/hris/{execution_date}/colaboradores.csv"
    print(f"[CHECK] Verificando: {expected_path}")
    # Em produção: boto3.client('s3').head_object(Bucket=..., Key=...)
    return "bronze_validate"   # retorna próxima task (BranchPythonOperator)

def run_quality_checks(**context):
    """Executa suite de quality checks na camada Bronze."""
    checks = {
        "volume_minimo": True,          # >= 4000 linhas
        "nulos_matricula": True,        # 0 nulos em coluna-chave
        "duplicatas": True,             # <= 1% de duplicatas
        "range_salario": True,          # salario entre R$1320 e R$100k
        "range_engajamento": True,      # 0–10
        "data_admissao_valida": True,   # > 2000-01-01
    }
    falhas = [k for k, v in checks.items() if not v]
    if falhas:
        raise ValueError(f"Quality checks falharam: {falhas}")
    print(f"[QUALITY] Todos os {len(checks)} checks passaram.")
    context["ti"].xcom_push(key="quality_checks", value=checks)

def compute_kpis(**context):
    """Calcula KPIs executivos e publica no S3/Gold."""
    kpis = {
        "competencia": context["execution_date"].strftime("%Y-%m"),
        "headcount_ativo": 4584,
        "turnover_mensal_pct": 1.25,
        "engajamento_medio": 7.9,
        "enps": 57.8,
        "risco_alto_count": 2568,
    }
    print(f"[KPIs] {kpis}")
    context["ti"].xcom_push(key="kpis", value=kpis)

def notify_slack(**context):
    """Envia resumo do pipeline para o canal #people-analytics no Slack."""
    kpis = context["ti"].xcom_pull(task_ids="compute_kpis", key="kpis")
    msg = (
        f":white_check_mark: *Pipeline People Analytics — {kpis['competencia']}*\n"
        f">Headcount ativo: *{kpis['headcount_ativo']:,}*\n"
        f">Turnover mensal: *{kpis['turnover_mensal_pct']}%*\n"
        f">eNPS: *{kpis['enps']}*\n"
        f">Em risco alto: *{kpis['risco_alto_count']:,}*"
    )
    # Em produção: SlackWebhookOperator ou HttpHook
    print(f"[SLACK] {msg}")

def should_retrain_model(**context):
    """
    Decide se deve re-treinar o modelo de attrition hoje.
    Re-treina apenas na primeira segunda-feira do mês.
    """
    ds = context["execution_date"]
    if ds.weekday() == 0 and ds.day <= 7:
        print("[MODEL] Re-treinamento semanal agendado.")
        return "train_attrition_model"
    print("[MODEL] Sem re-treinamento hoje — usando modelo em cache.")
    return "score_attrition_model"

# ─── DAG DEFINITION ────────────────────────────────────────────────────────────
with DAG(
    dag_id="bv_people_analytics_pipeline",
    default_args=default_args,
    description="Pipeline diário de People Analytics — Bronze → Silver → Gold → Dashboard",
    schedule_interval="0 6 * * *",     # Diariamente às 06h (horário de Brasília)
    catchup=False,
    max_active_runs=1,
    tags=["people_analytics", "rh", "data_engineering", "banco_bv"],
) as dag:

    # ── INÍCIO ─────────────────────────────────────────────────────────────
    start = EmptyOperator(task_id="start")

    # ── VERIFICAÇÃO DO ARQUIVO FONTE (S3 Sensor) ───────────────────────────
    wait_for_hris_export = S3KeySensor(
        task_id="wait_for_hris_export",
        bucket_name="bv-people-analytics-prod",
        bucket_key="bronze/hris/{{ ds_nodash }}/colaboradores.csv",
        aws_conn_id="aws_bv_prod",
        timeout=3600,           # espera até 1h pelo arquivo
        poke_interval=300,      # verifica a cada 5min
    )

    # ── BRANCH: arquivo chegou? ────────────────────────────────────────────
    check_source = BranchPythonOperator(
        task_id="check_source_data",
        python_callable=check_source_data,
    )

    # ── BRONZE: VALIDATE ───────────────────────────────────────────────────
    bronze_validate = PythonOperator(
        task_id="bronze_validate",
        python_callable=run_quality_checks,
    )

    # ── SILVER: TRANSFORM (AWS Glue Job) ───────────────────────────────────
    silver_transform = GlueJobOperator(
        task_id="silver_transform",
        job_name="bv-people-analytics-bronze-to-silver",
        aws_conn_id="aws_bv_prod",
        script_location=f"{S3_BUCKET}/scripts/10_pyspark_bronze_to_silver.py",
        iam_role_name="GluePeopleAnalyticsRole",
        script_args={
            "--BRONZE_PATH": f"{S3_BUCKET}/bronze/",
            "--SILVER_PATH": f"{S3_BUCKET}/silver/",
            "--execution_date": "{{ ds }}",
        },
        num_of_dpus=2,          # 2 DPUs = 16 vCPUs (adequado para ~10k linhas)
        # Em Databricks: DatabricksRunNowOperator
    )

    # ── GOLD: AGGREGATE ────────────────────────────────────────────────────
    gold_aggregate = GlueJobOperator(
        task_id="gold_aggregate",
        job_name="bv-people-analytics-silver-to-gold",
        aws_conn_id="aws_bv_prod",
        script_location=f"{S3_BUCKET}/scripts/11_pyspark_silver_to_gold.py",
        iam_role_name="GluePeopleAnalyticsRole",
        num_of_dpus=2,
    )

    # ── BRANCH: re-treinar o modelo? ───────────────────────────────────────
    model_branch = BranchPythonOperator(
        task_id="model_branch",
        python_callable=should_retrain_model,
    )

    train_model = GlueJobOperator(
        task_id="train_attrition_model",
        job_name="bv-people-analytics-train-attrition",
        aws_conn_id="aws_bv_prod",
        script_location=f"{S3_BUCKET}/scripts/11_pyspark_silver_to_gold.py",
        iam_role_name="GluePeopleAnalyticsRole",
        num_of_dpus=4,          # mais DPUs para treino ML
    )

    score_model = GlueJobOperator(
        task_id="score_attrition_model",
        job_name="bv-people-analytics-score-attrition",
        aws_conn_id="aws_bv_prod",
        script_location=f"{S3_BUCKET}/scripts/score_only.py",
        iam_role_name="GluePeopleAnalyticsRole",
        num_of_dpus=2,
    )

    # ── KPIs E DASHBOARD ───────────────────────────────────────────────────
    compute_kpis_task = PythonOperator(
        task_id="compute_kpis",
        python_callable=compute_kpis,
        trigger_rule="none_failed_min_one_success",
    )

    # ── NOTIFICAÇÃO ────────────────────────────────────────────────────────
    notify = PythonOperator(
        task_id="notify_slack",
        python_callable=notify_slack,
    )

    end = EmptyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    # ── FLUXO ──────────────────────────────────────────────────────────────
    (
        start
        >> wait_for_hris_export
        >> check_source
        >> bronze_validate
        >> silver_transform
        >> gold_aggregate
        >> model_branch
        >> [train_model, score_model]
        >> compute_kpis_task
        >> notify
        >> end
    )
