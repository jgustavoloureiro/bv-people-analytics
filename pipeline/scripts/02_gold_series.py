# -*- coding: utf-8 -*-
"""
CAMADA GOLD (parte 1) — Agregados de negócio prontos para consumo.
Séries mensais, granular para filtro, produtividade, workforce planning,
recrutamento (ATS fictício).
"""
import pandas as pd
import numpy as np
import json
import os

BASE = "/home/claude/bv_people_analytics"
rng = np.random.default_rng(77)

df = pd.read_csv(f"{BASE}/silver/colaboradores_clean.csv")
df["data_admissao"] = pd.to_datetime(df["data_admissao"])
df["data_desligamento"] = pd.to_datetime(df["data_desligamento"])
with open(f"{BASE}/bronze/_meta.json") as f: meta = json.load(f)

meses = pd.date_range(start=meta["data_inicio"], end=meta["data_fim"], freq="MS")
areas = meta["areas"]
senioridades = ["Júnior/Pleno", "Sênior/Especialista", "Liderança"]
generos = sorted(df.genero.unique().tolist())

os.makedirs(f"{BASE}/gold", exist_ok=True)

# ----------------------------------------------------------------------
# 1. SÉRIE MENSAL GERAL (headcount, turnover, eNPS, produtividade, custo)
# ----------------------------------------------------------------------
serie = []
for mes in meses:
    fim_mes = mes + pd.offsets.MonthEnd(0)
    ativos = df[(df.data_admissao <= fim_mes) & ((df.data_desligamento.isna()) | (df.data_desligamento > fim_mes))]
    deslig_mes = df[(df.data_desligamento.notna()) & (df.data_desligamento.dt.to_period("M") == mes.to_period("M"))]
    admiss_mes = df[df.data_admissao.dt.to_period("M") == mes.to_period("M")]
    hc_inicio = len(df[(df.data_admissao <= mes) & ((df.data_desligamento.isna()) | (df.data_desligamento > mes))])

    engaj_medio = ativos.engajamento_score_base.mean()
    tendencia = -3 if mes.year == 2024 else (0 if mes.year == 2025 else 4)
    enps = max(-100, min(100, round((engaj_medio - 5) * 18 + tendencia + rng.normal(0, 4), 1)))

    perf_medio = ativos.performance_score.mean()
    produtividade = round(max(60, min(135, 85 + (perf_medio - 3) * 12 + rng.normal(0, 2.5))), 1)

    serie.append({
        "competencia": mes.strftime("%Y-%m"),
        "headcount_total": len(ativos),
        "admissoes": len(admiss_mes),
        "desligamentos": len(deslig_mes),
        "desligamentos_voluntarios": int((deslig_mes.tipo_desligamento == "Voluntário").sum()),
        "desligamentos_involuntarios": int((deslig_mes.tipo_desligamento == "Involuntário").sum()),
        "turnover_mensal_pct": round(len(deslig_mes) / max(hc_inicio,1) * 100, 2),
        "custo_folha_total": round(ativos.salario_mensal.sum(), 2),
        "engajamento_medio": round(engaj_medio, 2) if not pd.isna(engaj_medio) else None,
        "enps": enps,
        "produtividade_index": produtividade,
        "performance_medio": round(perf_medio, 2) if not pd.isna(perf_medio) else None,
    })
df_serie = pd.DataFrame(serie)
df_serie.to_csv(f"{BASE}/gold/serie_mensal_geral.csv", index=False, encoding="utf-8-sig")
print(f"Série mensal geral: {len(df_serie)} meses")

# ----------------------------------------------------------------------
# 2. GRANULAR (mes x area x senioridade x genero) — alimenta filtro global
# ----------------------------------------------------------------------
registros = []
for mes in meses:
    fim_mes = mes + pd.offsets.MonthEnd(0)
    ativos_mes = df[(df.data_admissao <= fim_mes) & ((df.data_desligamento.isna()) | (df.data_desligamento > fim_mes))]
    deslig_mes = df[(df.data_desligamento.notna()) & (df.data_desligamento.dt.to_period("M") == mes.to_period("M"))]
    for area in areas:
        for senior in senioridades:
            for genero in generos:
                grp = ativos_mes[(ativos_mes.area==area)&(ativos_mes.senioridade==senior)&(ativos_mes.genero==genero)]
                if len(grp) == 0: continue
                grp_d = deslig_mes[(deslig_mes.area==area)&(deslig_mes.senioridade==senior)&(deslig_mes.genero==genero)]
                registros.append({
                    "competencia": mes.strftime("%Y-%m"), "area": area, "senioridade": senior, "genero": genero,
                    "headcount": len(grp), "desligamentos": len(grp_d),
                    "desligamentos_voluntarios": int((grp_d.tipo_desligamento=="Voluntário").sum()),
                    "engajamento_medio": round(grp.engajamento_score_base.mean(),2),
                    "salario_medio": round(grp.salario_mensal.mean(),2),
                    "performance_medio": round(grp.performance_score.mean(),2),
                    "produtividade_medio": round(grp.produtividade_index_base.mean(),1),
                })
df_gran = pd.DataFrame(registros)
df_gran.to_csv(f"{BASE}/gold/granular_mensal.csv", index=False, encoding="utf-8-sig")
print(f"Granular: {len(df_gran)} linhas")

# ----------------------------------------------------------------------
# 3. WORKFORCE PLANNING — headcount plan vs real por área, próximos 6 meses
# ----------------------------------------------------------------------
wf_plan = []
hc_atual_area = df[df.status=="Ativo"].groupby("area").size().to_dict()
meses_futuro = pd.date_range(start="2026-07-01", periods=6, freq="MS")
for area in areas:
    hc_base = hc_atual_area.get(area, 50)
    crescimento_mensal = meta["crescimento_anual"] / 12
    for i, mes in enumerate(meses_futuro):
        planejado = round(hc_base * (1 + crescimento_mensal) ** (i+1))
        realizado_proj = round(planejado * rng.normal(0.97, 0.05))
        wf_plan.append({
            "competencia": mes.strftime("%Y-%m"), "area": area,
            "headcount_planejado": int(planejado), "headcount_projetado": int(realizado_proj),
            "gap": int(realizado_proj - planejado),
        })
df_wf = pd.DataFrame(wf_plan)
df_wf.to_csv(f"{BASE}/gold/workforce_planning.csv", index=False, encoding="utf-8-sig")
print(f"Workforce planning: {len(df_wf)} linhas")

# ----------------------------------------------------------------------
# 4. RECRUTAMENTO (ATS fictício) — funil de contratação últimos 12 meses
# ----------------------------------------------------------------------
recrutamento = []
for mes in meses[-12:]:
    for area in areas:
        candidatos = int(rng.uniform(15, 120))
        triagem = int(candidatos * rng.uniform(0.35, 0.55))
        entrevista = int(triagem * rng.uniform(0.30, 0.50))
        oferta = int(entrevista * rng.uniform(0.25, 0.45))
        contratado = int(oferta * rng.uniform(0.65, 0.90))
        tempo_medio_dias = round(rng.uniform(18, 65), 0)
        recrutamento.append({
            "competencia": mes.strftime("%Y-%m"), "area": area, "candidatos": candidatos,
            "triagem": triagem, "entrevista": entrevista, "oferta": oferta, "contratado": contratado,
            "tempo_medio_contratacao_dias": tempo_medio_dias,
        })
df_recrut = pd.DataFrame(recrutamento)
df_recrut.to_csv(f"{BASE}/gold/recrutamento_funil.csv", index=False, encoding="utf-8-sig")
print(f"Recrutamento: {len(df_recrut)} linhas")

# ----------------------------------------------------------------------
# 5. PRODUTIVIDADE POR ÁREA (mensal) — para módulo dedicado
# ----------------------------------------------------------------------
produtividade_area = []
for mes in meses[-18:]:
    fim_mes = mes + pd.offsets.MonthEnd(0)
    ativos_mes = df[(df.data_admissao <= fim_mes) & ((df.data_desligamento.isna()) | (df.data_desligamento > fim_mes))]
    for area in areas:
        grp = ativos_mes[ativos_mes.area == area]
        if len(grp) == 0: continue
        prod_medio = grp.produtividade_index_base.mean() + rng.normal(0, 3)
        produtividade_area.append({
            "competencia": mes.strftime("%Y-%m"), "area": area,
            "produtividade_index": round(max(50, min(140, prod_medio)), 1),
            "headcount": len(grp),
            "horas_extras_medio": round(rng.uniform(2, 18), 1),
            "absenteismo_pct": round(rng.uniform(1.5, 6.5), 2),
        })
df_prod = pd.DataFrame(produtividade_area)
df_prod.to_csv(f"{BASE}/gold/produtividade_area.csv", index=False, encoding="utf-8-sig")
print(f"Produtividade por área: {len(df_prod)} linhas")

print("\n=== GOLD PARTE 1 CONCLUÍDA ===")
