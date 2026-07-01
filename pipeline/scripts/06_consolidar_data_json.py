# -*- coding: utf-8 -*-
"""Script 06 — Consolida toda a camada Gold em data.json único."""
import pandas as pd
import json
import os

BASE = "/home/claude/bv_people_analytics"
G = f"{BASE}/gold"

def load_csv(name): return pd.read_csv(f"{G}/{name}").to_dict("records")
def load_json(name):
    with open(f"{G}/{name}", encoding="utf-8") as f: return json.load(f)

with open(f"{BASE}/bronze/_meta.json") as f: meta_b = json.load(f)
with open(f"{BASE}/silver/_log_qualidade.json") as f: log_qualidade = json.load(f)

serie_geral = load_csv("serie_mensal_geral.csv")
granular = load_csv("granular_mensal.csv")
workforce = load_csv("workforce_planning.csv")
recrutamento = load_csv("recrutamento_funil.csv")
produtividade_area = load_csv("produtividade_area.csv")
risco_area = load_csv("risco_attrition_por_area.csv")
top_risco = load_csv("top_risco_attrition.csv")

modelo = load_json("metricas_modelo_attrition.json")
causa_raiz = load_json("causa_raiz.json")
planos_acao = load_json("planos_acao.json")
plano_5w2h = load_json("plano_5w2h.json")
matriz_raci = load_json("matriz_raci.json")
pdca = load_json("pdca.json")
pmo = load_json("pmo.json")
benchmark = load_json("benchmark_mercado.json")
capex_opex = load_json("capex_opex.json")
arquitetura = load_json("arquitetura_dados.json")

df_g = pd.DataFrame(granular)
dimensoes = {
    "areas": sorted(df_g.area.unique().tolist()),
    "senioridades": sorted(df_g.senioridade.unique().tolist()),
    "generos": sorted(df_g.genero.unique().tolist()),
}

# KPIs da capa (últimos valores)
ultimo = serie_geral[-1]
kpis_capa = {
    "headcount_atual": ultimo["headcount_total"],
    "turnover_ltm_pct": round(sum(m["desligamentos"] for m in serie_geral[-12:]) / max(serie_geral[-13]["headcount_total"],1) * 100, 1),
    "enps_atual": ultimo["enps"],
    "produtividade_atual": ultimo["produtividade_index"],
    "custo_folha_atual": ultimo["custo_folha_total"],
}

DATA = {
    "meta": {
        "empresa": "Banco BV", "projeto": "People Analytics — Painel Estratégico Sênior",
        "designed_by": "José Gustavo Loureiro Campos Silva",
        "linkedin": "https://www.linkedin.com/in/josegustavoloureiro/",
        "data_atualizacao": "30/06/2026 19:15 (BRT)",
        "periodo_inicio": meta_b["data_inicio"], "periodo_fim": meta_b["data_fim"],
        "meta_turnover_referencia_pct": 18.0, "meta_enps_excelencia": 50, "meta_concentracao_minima_pct": 98,
        "natureza_dados": "100% sintéticos, com estrutura analítica e lógica causal realistas. Modelo preditivo "
                           "treinado e validado de verdade sobre a série sintética. Dados de benchmarking setorial "
                           "são estimativas baseadas em sinais públicos qualitativos (ver aba Benchmarking).",
        "kpis_capa": kpis_capa,
    },
    "dimensoes": dimensoes,
    "serie_mensal_geral": serie_geral,
    "granular_mensal": granular,
    "workforce_planning": workforce,
    "recrutamento_funil": recrutamento,
    "produtividade_area": produtividade_area,
    "risco_por_area": risco_area,
    "top_risco": top_risco,
    "modelo_attrition": modelo,
    "causa_raiz_ranking": causa_raiz,
    "planos_acao": planos_acao,
    "plano_5w2h": plano_5w2h,
    "matriz_raci": matriz_raci,
    "pdca": pdca,
    "pmo_projetos": pmo,
    "benchmark_mercado": benchmark,
    "capex": capex_opex["capex"],
    "opex_mensal": capex_opex["opex_mensal"],
    "opex_categoria": capex_opex["opex_categoria"],
    "arquitetura_dados": arquitetura,
    "log_qualidade": log_qualidade,
}

os.makedirs(f"{BASE}/dashboard", exist_ok=True)
with open(f"{BASE}/dashboard/data.json", "w", encoding="utf-8") as f:
    json.dump(DATA, f, ensure_ascii=False, default=str)

tamanho = os.path.getsize(f"{BASE}/dashboard/data.json")
print(f"data.json consolidado: {tamanho/1024:.1f} KB")
print(f"Chaves: {list(DATA.keys())}")
print(f"Granular: {len(granular)} | Top risco: {len(top_risco)} | Causa raiz: {len(causa_raiz)} | Bancos benchmark: {len(benchmark['concorrentes'])+1}")
