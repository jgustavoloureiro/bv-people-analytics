# Arquitetura de Dados — People Analytics | Banco BV

> **Nota:** Esta arquitetura é **fictícia**, criada para fins de portfólio profissional,
> demonstrando como seria estruturado um ecossistema de dados de People Analytics
> de classe enterprise. Os valores de infraestrutura, configurações e integrações
> simulam padrões reais de mercado (AWS, Azure, Databricks, Airflow).

---

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PEOPLE ANALYTICS DATA PLATFORM                      │
│                           Banco BV — 2026                               │
└─────────────────────────────────────────────────────────────────────────┘

 FONTES                 INGESTÃO            PROCESSAMENTO         CONSUMO
 ─────────            ─────────           ──────────────        ─────────
 ┌────────┐           ┌────────┐          ┌───────────┐         ┌───────┐
 │  HRIS  │──────────▶│        │          │           │         │ Dash  │
 │(People │           │ Apache │          │  BRONZE   │         │ board │
 │ Soft)  │           │ NiFi / │──────── ▶│  (S3/ADLS)│         │ HTML  │
 └────────┘           │ AWS    │          │           │         └───────┘
 ┌────────┐           │ Glue   │          └─────┬─────┘         ┌───────┐
 │  ERP   │──────────▶│ (ETL)  │                │               │Power  │
 │(SAP)   │           │        │          ┌─────▼─────┐         │  BI   │
 └────────┘           └────────┘          │           │         └───────┘
 ┌────────┐                               │  SILVER   │         ┌───────┐
 │  ATS   │──────────▶┌────────┐          │ (Parquet/ │         │Python │
 │(Gupy)  │           │ Kafka  │          │  Delta)   │         │/ SQL  │
 └────────┘           │(stream)│          │           │         │  API  │
 ┌────────┐           └────────┘          └─────┬─────┘         └───────┘
 │ Survey │                                     │
 │(NPS/   │──────────▶┌────────┐          ┌─────▼─────┐
 │ Clima) │           │  SFTP  │          │           │
 └────────┘           │/ API   │          │   GOLD    │
 ┌────────┐           └────────┘          │(Redshift/ │
 │ Collab │                               │ Synapse)  │
 │(Teams/ │──────────▶┌────────┐          │           │
 │Slack)  │           │ REST   │          └─────┬─────┘
 └────────┘           │  API   │                │
                      └────────┘          ┌─────▼─────┐
                                          │   MODEL   │
                                          │ (MLlib/   │
                                          │ sklearn)  │
                                          └───────────┘
```

---

## Camadas Medallion Architecture

### 🥉 Bronze (Raw Zone)

| Atributo | Detalhe |
|---|---|
| **Storage** | AWS S3 `s3://bv-people-analytics-prod/bronze/` / Azure ADLS Gen2 |
| **Formato** | CSV, JSON (formato nativo dos sistemas fonte) |
| **Particionamento** | Por data de chegada: `year=YYYY/month=MM/day=DD/` |
| **Retenção** | 7 anos (compliance regulatório) → Glacier após 90 dias |
| **Qualidade** | Dados brutos, **sem transformação**. Inclui nulos, duplicatas e inconsistências propositais para auditoria |
| **Acesso** | Restrito à equipe de Data Engineering |

Dados de entrada (bronze):
- `hris_colaboradores_raw.csv` — exportação diária do HRIS
- `hris_desligamentos_raw.csv` — eventos de desligamento
- `ats_recrutamento_raw.json` — funil de recrutamento (Gupy)
- `survey_clima_raw.csv` — pesquisa de clima/eNPS
- `erp_folha_raw.csv` — dados de folha de pagamento (SAP)

### 🥈 Silver (Cleansed Zone)

| Atributo | Detalhe |
|---|---|
| **Storage** | AWS S3 (Parquet) + Delta Lake (Databricks) |
| **Formato** | Parquet / Delta (compressão Snappy) |
| **Particionamento** | Por `area` (campo de alta cardinalidade nos joins) |
| **Engine** | PySpark (AWS Glue 4.0 / Databricks Runtime 13.x) |
| **Qualidade** | Deduplicado, tipado, outliers corrigidos, nulos tratados com regra documentada |

Transformações aplicadas:
1. **Deduplicação** — exacta + por matrícula (SCD Tipo 1)
2. **Padronização de categoria** — normaliza variações de digitação em `area`
3. **Correção de outliers** — salário 100x o esperado → divide por 100
4. **Imputação** — engajamento/salário nulos → mediana por grupo (área + senioridade)
5. **Dados demográficos** — nulos → `"Não informado"` (não imputar identidade)
6. **Validação de datas** — `data_desligamento < data_admissao` → invalida o desligamento

### 🥇 Gold (Curated Zone)

| Atributo | Detalhe |
|---|---|
| **Storage** | Amazon Redshift / Azure Synapse Analytics |
| **Formato** | Tabelas Parquet (para Spark) + tabelas materializadas no DW |
| **Modelagem** | Star schema (fatos + dimensões) — ver `13_star_schema_ddl.sql` |
| **SLA** | Disponível até 08h30 após execução das 06h00 |

Tabelas Gold principais:
- `fct_desligamento` — grain: 1 linha por desligamento
- `fct_headcount_mensal` — grain: mês × área × senioridade
- `dim_colaborador` (SCD Tipo 2) — histórico de mudanças
- `dim_area`, `dim_data`, `dim_motivo_saida` — dimensões

---

## Stack Tecnológica Completa

### AWS (primário)
| Serviço | Uso |
|---|---|
| **S3** | Data Lake (Bronze/Silver/Gold/Scripts) |
| **AWS Glue 4.0** | ETL jobs PySpark — Bronze→Silver, Silver→Gold |
| **Amazon Redshift ra3** | Data Warehouse analítico |
| **Amazon MWAA** | Apache Airflow gerenciado — orquestração |
| **AWS Secrets Manager** | Credenciais e tokens |
| **AWS IAM** | Controle de acesso (least privilege) |
| **Amazon CloudWatch** | Logs e alertas de pipeline |
| **AWS Lambda** | Triggers de ingestão (arrival event) |

### Azure (secundário / DR)
| Serviço | Uso |
|---|---|
| **ADLS Gen2** | Data Lake espelho para DR |
| **Databricks Premium** | Processamento Spark + Unity Catalog |
| **Azure Synapse Analytics** | DW analítico + serverless SQL |
| **Azure Data Factory** | Orquestração alternativa |
| **Azure Key Vault** | Gerenciamento de segredos |
| **Microsoft Entra ID** | SSO e autenticação |

### Ferramentas de Dados
| Ferramenta | Versão | Uso |
|---|---|---|
| **PySpark** | 3.5 | Processamento distribuído (Bronze→Silver, Silver→Gold) |
| **Delta Lake** | 3.0 | ACID transactions no data lake |
| **Apache Airflow** | 2.8 | Orquestração do pipeline |
| **dbt** | 1.7 | Transformações SQL (camada Gold → marts) |
| **Great Expectations** | 0.18 | Testes automatizados de qualidade |
| **scikit-learn** | 1.4 | Modelo de attrition (Random Forest) |
| **MLflow** | 2.10 | MLOps: rastreamento de experimentos |
| **Power BI Premium** | — | BI corporativo (paralelo ao dashboard HTML) |
| **Terraform** | 1.7 | Infrastructure as Code |
| **GitHub Actions** | — | CI/CD |

---

## Governança de Dados

### Linhagem (Data Lineage)
```
HRIS Export (07:00)
    └── Bronze: hris_colaboradores_raw.csv
        └── Silver: colaboradores/ (Parquet, particionado por area)
            ├── Gold: fct_headcount_mensal
            ├── Gold: fct_desligamento
            ├── Gold: scores_attrition
            └── Gold: nine_box_grid
                └── Dashboard: index.html (data.json embutido)
```

### Catalogação (Data Catalog)
- **AWS Glue Data Catalog** — metadados de todas as tabelas Bronze e Silver
- **Databricks Unity Catalog** — metadados Gold + controle de acesso colunar
- Toda tabela tem: `owner`, `description`, `pii_columns`, `refresh_frequency`, `sla`

### Dados PII (Privacidade)
Colunas sensíveis identificadas e tratadas:
| Coluna | Classificação | Tratamento |
|---|---|---|
| `matricula` | PII Indireto | Pseudonimização em ambientes não-prod |
| `nome_ficticio` | PII Direto | Mascaramento em Silver/Gold |
| `genero` | PII Sensível | Acesso restrito, agrupado em relatórios |
| `raca_cor` | PII Sensível | Acesso restrito, agregado apenas |
| `salario_mensal` | Confidencial | Criptografado em repouso, acesso por role |

### Controle de Qualidade (SLA de Qualidade)
| Métrica | Alvo | Alerta |
|---|---|---|
| Completude de matrícula | 100% | < 99.5% |
| Taxa de duplicatas | < 0.5% | > 1% |
| Engajamento no range 0-10 | 100% | < 99% |
| Disponibilidade da Gold | 08h30 | 09h30 |
| ROC-AUC do modelo | ≥ 0.65 | < 0.60 |

---

## Orquestração (Apache Airflow)

```
DAG: bv_people_analytics_pipeline
Schedule: 0 6 * * * (diário às 06h BRT)
SLA: 08h30

[06:00] start
    │
[06:05] wait_for_hris_export (S3KeySensor, timeout=60min)
    │
[06:xx] check_source_data (BranchPythonOperator)
    │
[06:xx] bronze_validate (PythonOperator — quality checks)
    │
[06:xx] silver_transform (GlueJobOperator — 2 DPUs, ~20min)
    │
[07:xx] gold_aggregate (GlueJobOperator — 2 DPUs, ~15min)
    │
[07:xx] model_branch ──────────────────────────┐
    │                                           │
[07:xx] train_attrition_model (4 DPUs)    score_attrition_model (2 DPUs)
         (somente 1ª seg/mês)              (demais dias — modelo em cache)
    │                                           │
    └───────────────────┬───────────────────────┘
                        │
[08:xx] compute_kpis (PythonOperator)
    │
[08:xx] notify_slack (#people-analytics)
    │
[08:xx] end
```

---

## Modelo Preditivo de Attrition

### Algoritmo
- **Random Forest Classifier** (scikit-learn / Spark MLlib)
- **Janela de predição:** 12 meses
- **Validação:** holdout temporal (75/25), sem vazamento de dados

### Features (top 5 por importância)
| Feature | Importância | Justificativa de Negócio |
|---|---|---|
| `engajamento_score_base` | 43.5% | Driver direto de intenção de saída |
| `tempo_casa_meses` | 16.0% | Curva em U: risco alto nos primeiros 6m e após 48m |
| `produtividade_index_base` | 10.3% | Baixa produtividade + insatisfação → saída |
| `salario_mensal` | 8.6% | Defasagem salarial sinaliza risco |
| `idade` | 6.9% | Proxy de senioridade de mercado |

### Decisões de Design
1. **Por que Random Forest e não XGBoost?** — Maior interpretabilidade (feature importance nativa), sem necessidade de tuning extenso para dados com esta granularidade.
2. **Por que janela de 12 meses?** — 6 meses gera poucos eventos positivos (<5%); 12 meses dá taxa de ~10%, mais robusto para treino.
3. **Por que não usar `status` como feature?** — Data leakage. `status` é derivado do target.
4. **Limitação importante:** Modelo treinado sobre dados sintéticos. Em produção, exige validação cruzada temporal, auditoria de viés em `genero`/`raca_cor` e aprovação do comitê de ética em dados antes de qualquer uso em decisão de RH.

---

## Estrutura do Repositório

```
bv-people-analytics/
├── .github/
│   └── workflows/
│       └── ci_cd.yml              # GitHub Actions: lint → test → deploy
│
├── pipeline/
│   ├── bronze/                    # Dados brutos (Bronze layer)
│   │   ├── hris_colaboradores_raw.csv
│   │   ├── hris_desligamentos_raw.csv
│   │   └── Banco_BV_People_Analytics_Base_Bruta.xlsx
│   │
│   ├── silver/                    # Dados tratados (Silver layer)
│   │   ├── colaboradores/         # Parquet particionado por área
│   │   └── _quality_log.json      # Log auditável de transformações
│   │
│   ├── gold/                      # Agregados de negócio (Gold layer)
│   │   ├── serie_mensal/          # Parquet: série temporal mensal
│   │   ├── scores_attrition.csv   # Scores por colaborador ativo
│   │   ├── metricas_modelo_attrition.json
│   │   └── nine_box_grid/         # 9-Box Grid Parquet
│   │
│   └── scripts/                   # Pipeline scripts (numerados por ordem)
│       ├── 00_bronze_hris.py          # Geração de dados sintéticos
│       ├── 01_silver_tratamento.py    # Limpeza e padronização (pandas)
│       ├── 02_gold_series.py          # Agregações de negócio
│       ├── 03_modelo_attrition.py     # ML com scikit-learn
│       ├── 04_gold_governanca_benchmark.py
│       ├── 05_gold_capex_arquitetura.py
│       ├── 06_consolidar_data_json.py
│       ├── 07_gerar_xlsx.py
│       ├── 10_pyspark_bronze_to_silver.py  # Versão PySpark (produção)
│       ├── 11_pyspark_silver_to_gold.py    # PySpark + MLlib
│       ├── 12_airflow_dag.py               # Orquestração Airflow
│       └── 13_star_schema_ddl.sql          # Modelagem dimensional
│
├── dashboard/
│   └── index.html                  # Dashboard standalone (Chart.js embutido)
│
├── tests/
│   └── test_pipeline_quality.py   # Pytest: qualidade de dados + modelo
│
├── config/
│   └── terraform_infra.tf         # IaC: AWS + Azure
│
├── docs/
│   └── architecture/
│       └── ARCHITECTURE.md        # Este documento
│
├── requirements.txt               # Dependências Python
├── requirements-pyspark.txt       # Dependências PySpark específicas
├── .gitignore
└── README.md
```

---

*Designed by José Gustavo Loureiro Campos Silva — [linkedin.com/in/josegustavoloureiro](https://www.linkedin.com/in/josegustavoloureiro/)*
