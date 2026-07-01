# 🏦 People Analytics — Banco BV | Painel Estratégico Sênior

[![CI/CD Pipeline](https://img.shields.io/github/actions/workflow/status/jgustavoloureiro/bv-people-analytics/ci_cd.yml?label=CI%2FCD&logo=github)](https://github.com/jgustavoloureiro/bv-people-analytics/actions)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![PySpark](https://img.shields.io/badge/PySpark-3.5-orange?logo=apache-spark)](https://spark.apache.org)
[![Dashboard](https://img.shields.io/badge/Dashboard-GitHub%20Pages-brightgreen?logo=github)](https://jgustavoloureiro.github.io/bv-people-analytics/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> ⚠️ **"Banco BV" é usado aqui apenas como referência de vaga de emprego.**
> Todos os dados, colaboradores, métricas e processos são **100% sintéticos**,
> gerados para demonstração técnica de portfólio. Não representam nenhum
> funcionário, dado real ou processo do Banco BV ou de qualquer instituição financeira.

---

## 🎯 O que este projeto demonstra

Este repositório demonstra, de ponta a ponta, as competências de um **Analista de People Analytics Sênior** com foco em engenharia de dados:

| Competência | Como é demonstrada |
|---|---|
| **Pipeline de dados** | Bronze→Silver→Gold (Medallion Architecture) com pandas e PySpark |
| **Qualidade de dados** | Deduplicação, imputação, outliers, log auditável, Great Expectations |
| **Modelagem preditiva** | Random Forest (scikit-learn + Spark MLlib), ROC-AUC 0.689 |
| **9-Box Grid** | Ferramenta nativa de gestão de talentos (Performance × Potencial) |
| **Employee Journey Map** | NPS por momento da jornada com pain points e oportunidades |
| **Star Schema (DW)** | DDL completo: fct_desligamento, fct_headcount_mensal, dims |
| **Orquestração** | Apache Airflow DAG com branches, sensors e notificações |
| **IaC** | Terraform para AWS (S3, Glue, Redshift) + Azure (ADLS, Databricks) |
| **Dashboard** | HTML standalone com Chart.js, filtros dinâmicos e IA offline |
| **CI/CD** | GitHub Actions: lint → testes → validação → deploy em Pages |

---

## 🏗️ Arquitetura

```
HRIS ──┐
ERP ───┤   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌──────────┐
ATS ───┼──▶│ BRONZE  │──▶│ SILVER  │──▶│  GOLD   │──▶│Dashboard │
Survey─┤   │ (S3/CSV)│   │(Parquet)│   │(Redshift│   │(HTML +   │
       │   └─────────┘   └─────────┘   │/Synapse)│   │Chart.js) │
       │       │ AWS Glue / Databricks  └─────────┘   └──────────┘
       │       │ PySpark 3.5                │
       │       └─── Apache Airflow ─────────┘
       │           (orquestração diária 06h)
       └── Terraform (AWS + Azure)
```

[📐 Ver arquitetura completa](docs/architecture/ARCHITECTURE.md)

---

## 🚀 Quick Start

### Pré-requisitos
```bash
python 3.11+
pip install -r requirements.txt
```

### Rodar o pipeline completo (modo local, sem cluster)
```bash
# 1. Gerar dados Bronze sintéticos
python pipeline/scripts/00_bronze_hris.py

# 2. Tratamento Silver (pandas)
python pipeline/scripts/01_silver_tratamento.py

# 3. Agregações Gold + Modelo preditivo
python pipeline/scripts/02_gold_series.py
python pipeline/scripts/03_modelo_attrition.py
python pipeline/scripts/04_gold_governanca_benchmark.py
python pipeline/scripts/05_gold_capex_arquitetura.py

# 4. Consolidar data.json e gerar XLSX
python pipeline/scripts/06_consolidar_data_json.py
python pipeline/scripts/07_gerar_xlsx.py

# 5. Abrir o dashboard
open dashboard/index.html
```

### Rodar com PySpark (requer Java 11+)
```bash
pip install -r requirements-pyspark.txt

# Bronze → Silver (PySpark)
python pipeline/scripts/10_pyspark_bronze_to_silver.py

# Silver → Gold + MLlib
python pipeline/scripts/11_pyspark_silver_to_gold.py
```

### Rodar os testes
```bash
pytest tests/ -v --cov=pipeline/scripts --cov-report=html
```

---

## 📊 Dashboard

**[🔗 Acessar dashboard online](https://jgustavoloureiro.github.io/bv-people-analytics/)**

O dashboard é um arquivo HTML standalone com **Chart.js embutido** — funciona offline,
sem servidor, sem dependências externas.

**19 módulos analíticos:**

| Grupo | Módulos |
|---|---|
| Visão Geral | Visão Executiva, Turnover, Engajamento & eNPS, Produtividade, Workforce Planning |
| Análise Profunda | Segmentação, Recrutamento (ATS), 9-Box Grid, Employee Journey Map, Causa Raiz (RCA), Benchmarking, Attrition Preditivo, CAPEX & OPEX |
| Governança | Planos de Ação 30/60/90, 5W2H, RACI, PDCA, PMO/Squads |
| Referência | Relatório Diretoria, Arquitetura, **Analista IA Offline** (13 intents) |

---

## 🤖 Modelo Preditivo de Attrition

| Parâmetro | Valor |
|---|---|
| Algoritmo | Random Forest Classifier |
| ROC-AUC | **0.689** (holdout 25%, sem data leakage) |
| Janela de predição | 12 meses |
| Base de treino | ~3.200 colaboradores |
| Feature dominante | Engajamento (43.5% de importância) |
| Colaboradores em risco alto | **2.568** (56% da base ativa) |

> ⚠️ Modelo treinado sobre dados sintéticos. Em produção, exigiria validação cruzada
> temporal, auditoria de viés e aprovação de comitê de ética antes de uso em decisões de RH.

---

## 🗂️ Estrutura do Repositório

```
bv-people-analytics/
├── .github/workflows/ci_cd.yml         # CI/CD: lint → test → deploy Pages
├── pipeline/
│   ├── bronze/                          # Dados brutos (CSV + XLSX)
│   ├── silver/                          # Dados tratados (Parquet/Delta)
│   ├── gold/                            # Agregados de negócio
│   └── scripts/
│       ├── 00–07_*.py                   # Pipeline pandas (desenvolvimento)
│       ├── 10_pyspark_bronze_to_silver.py  # PySpark produção
│       ├── 11_pyspark_silver_to_gold.py    # PySpark + MLlib
│       ├── 12_airflow_dag.py               # Orquestração Airflow
│       └── 13_star_schema_ddl.sql          # Modelagem dimensional
├── dashboard/index.html                 # Dashboard standalone
├── tests/test_pipeline_quality.py       # Suite de testes (pytest)
├── config/terraform_infra.tf            # IaC AWS + Azure
├── docs/architecture/ARCHITECTURE.md    # Documentação completa
├── requirements.txt
└── requirements-pyspark.txt
```

---

## 🛠️ Stack Tecnológica

**Data Engineering:** Python · PySpark 3.5 · Delta Lake · Apache Airflow · dbt · Great Expectations

**Cloud:** AWS (S3, Glue, Redshift, MWAA, Lambda) · Azure (ADLS Gen2, Databricks, Synapse)

**Machine Learning:** scikit-learn · Spark MLlib · MLflow

**BI & Visualização:** Chart.js · Power BI · SQL (Redshift / Synapse)

**DevOps:** GitHub Actions · Terraform · Docker · pytest · Bandit

---

## 👤 Autor

**José Gustavo Loureiro Campos Silva**
Data & Process Analyst | People Analytics Sênior

[![LinkedIn](https://img.shields.io/badge/LinkedIn-josegustavoloureiro-blue?logo=linkedin)](https://www.linkedin.com/in/josegustavoloureiro/)
[![GitHub](https://img.shields.io/badge/GitHub-jgustavoloureiro-black?logo=github)](https://github.com/jgustavoloureiro)

---

*Este projeto é um portfólio técnico demonstrando competências em People Analytics,
Engenharia de Dados e Ciência de Dados. Todos os dados são 100% sintéticos.*
