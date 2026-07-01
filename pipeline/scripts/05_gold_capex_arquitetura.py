# -*- coding: utf-8 -*-
"""GOLD parte 3 — CAPEX/OPEX + consolidação final em data.json"""
import pandas as pd
import numpy as np
import json

BASE = "/home/claude/bv_people_analytics"
rng = np.random.default_rng(505)

with open(f"{BASE}/bronze/_meta.json") as f: meta_b = json.load(f)
meses = pd.date_range(start=meta_b["data_inicio"], end=meta_b["data_fim"], freq="MS")

capex = [
    {"id":"CAPEX01","descricao":"Implantação de plataforma de People Analytics (BI + modelagem preditiva)","categoria":"Tecnologia","competencia":"2024-09","valor_planejado":220000,"valor_realizado":231450.0,"status":"Concluído"},
    {"id":"CAPEX02","descricao":"Ferramenta de pesquisa de clima e eNPS contínuo","categoria":"Tecnologia","competencia":"2024-11","valor_planejado":95000,"valor_realizado":98200.0,"status":"Concluído"},
    {"id":"CAPEX03","descricao":"Programa de trilhas de carreira e sucessão (consultoria + plataforma)","categoria":"Desenvolvimento","competencia":"2025-03","valor_planejado":310000,"valor_realizado":298500.0,"status":"Em execução"},
    {"id":"CAPEX04","descricao":"Revisão de estrutura salarial e cargos (consultoria externa)","categoria":"Remuneração","competencia":"2025-06","valor_planejado":180000,"valor_realizado":175900.0,"status":"Em execução"},
    {"id":"CAPEX05","descricao":"Programa de onboarding digital (primeiros 90 dias)","categoria":"Tecnologia","competencia":"2025-09","valor_planejado":130000,"valor_realizado":0.0,"status":"Planejado"},
    {"id":"CAPEX06","descricao":"Migração de Data Warehouse de RH para arquitetura Lakehouse","categoria":"Tecnologia","competencia":"2026-02","valor_planejado":420000,"valor_realizado":385000.0,"status":"Em execução"},
]
opex_mensal = []
base_opex = 185000
for i, mes in enumerate(meses):
    sazonal = 1.15 if mes.month==12 else (1.08 if mes.month in [1,6] else 1.0)
    realizado = base_opex * sazonal * rng.normal(1.0,0.04) + i*350
    opex_mensal.append({"competencia": mes.strftime("%Y-%m"), "orcado": round(base_opex+i*300,2), "realizado": round(realizado,2)})

opex_categoria = [
    {"categoria":"Plataformas e Licenças (HRIS, BI, Pesquisa)","orcado":850000,"realizado":879400.0},
    {"categoria":"Programas de Treinamento e Desenvolvimento","orcado":620000,"realizado":645800.0},
    {"categoria":"Pesquisas de Clima e Consultoria","orcado":380000,"realizado":365200.0},
    {"categoria":"Ações de Retenção e Reconhecimento","orcado":290000,"realizado":312600.0},
    {"categoria":"Recrutamento e Seleção","orcado":540000,"realizado":578900.0},
    {"categoria":"Infraestrutura de Dados (Cloud)","orcado":310000,"realizado":298700.0},
]
with open(f"{BASE}/gold/capex_opex.json","w",encoding="utf-8") as f:
    json.dump({"capex":capex,"opex_mensal":opex_mensal,"opex_categoria":opex_categoria}, f, ensure_ascii=False, indent=2)
print(f"CAPEX/OPEX salvo: {len(capex)} projetos, {len(opex_mensal)} meses OPEX")

# ----------------------------------------------------------------------
# ARQUITETURA DE DADOS (texto estruturado para a aba do dashboard)
# ----------------------------------------------------------------------
arquitetura = {
    "visao_geral": "Pipeline de dados de People Analytics seguindo medallion architecture (Bronze → Silver → Gold), "
                   "com camada de consumo via dashboard e API de IA offline. Arquitetura fictícia inspirada em "
                   "padrões reais de mercado (AWS e Azure), montada para fins de portfólio.",
    "camadas": [
        {"nome": "Bronze (Raw)", "descricao": "Dados brutos, exatamente como extraídos das fontes — HRIS, ERP financeiro, ATS de recrutamento, plataforma de pesquisa de clima. Sem tratamento, inclui duplicatas e inconsistências propositais.",
         "tecnologia_simulada": "Amazon S3 (raw zone) / Azure Data Lake Storage Gen2 (raw container)", "formato": "CSV / JSON"},
        {"nome": "Silver (Cleansed)", "descricao": "Dados tratados: deduplicados, tipos padronizados, nulos tratados com regra documentada, outliers corrigidos. Granularidade de evento (1 linha = 1 colaborador).",
         "tecnologia_simulada": "AWS Glue (ETL jobs) + Athena / Azure Data Factory + Databricks (Delta Lake)", "formato": "Parquet / Delta"},
        {"nome": "Gold (Curated)", "descricao": "Agregados de negócio prontos para consumo: séries mensais, scores de modelo preditivo, granular para filtros, benchmarking, governança ITIL.",
         "tecnologia_simulada": "Amazon Redshift / Azure Synapse Analytics (Lakehouse) — modelagem dimensional (star schema)", "formato": "Parquet + JSON (consumo)"},
        {"nome": "Consumo", "descricao": "Dashboard HTML interativo com IA offline embarcada, lendo diretamente do data.json gerado pela camada Gold.",
         "tecnologia_simulada": "Power BI Premium (paralelo) / Dashboard HTML standalone (este projeto)", "formato": "HTML/JS"},
    ],
    "orquestracao_simulada": "Apache Airflow (DAGs diários) orquestrando: extração HRIS (06h) → Bronze → validação de qualidade → Silver → agregações → Gold → publicação dashboard.",
    "governanca": ["Linhagem de dados documentada por script numerado (00 a 06)", "Catalogação via metadados em cada camada (_meta.json, _log_qualidade.json)",
                   "Qualidade validada com testes automatizados (volumetria, nulos, ranges)", "Versionamento de schema via Git"],
    "stack_completa": ["Python (pandas, numpy, scikit-learn)", "SQL (modelagem dimensional)", "AWS (S3, Glue, Redshift) — simulado",
                       "Azure (Data Lake, Synapse, Databricks) — simulado", "Power BI / Power Platform", "Git/GitHub para versionamento"],
}
with open(f"{BASE}/gold/arquitetura_dados.json","w",encoding="utf-8") as f:
    json.dump(arquitetura, f, ensure_ascii=False, indent=2)
print("Arquitetura de dados documentada")

print("\n=== GOLD COMPLETA ===")
