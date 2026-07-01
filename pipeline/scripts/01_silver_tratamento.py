# -*- coding: utf-8 -*-
"""
CAMADA SILVER — Tratamento de qualidade, documentado linha a linha.
Aplica a regra: nada tratado em silêncio, todo log de transformação é
auditável e vira insumo da aba "Arquitetura de Dados" do dashboard.
"""
import pandas as pd
import numpy as np
import json
import os

BASE = "/home/claude/bv_people_analytics"
df = pd.read_csv(f"{BASE}/bronze/hris_colaboradores_raw.csv")
log = []

def registrar(acao, qtd, detalhe=""):
    log.append({"acao": acao, "linhas_afetadas": int(qtd), "detalhe": detalhe})
    print(f"[{qtd:>4}] {acao} {('— ' + detalhe) if detalhe else ''}")

print("="*70 + "\nTRATAMENTO SILVER\n" + "="*70)

n0 = len(df)
df = df.drop_duplicates()
registrar("Duplicatas exatas removidas", n0 - len(df))

n0 = len(df)
df = df.drop_duplicates(subset=["matricula"], keep="first")
registrar("Duplicatas residuais por matrícula removidas", n0 - len(df))

mapa_area = {a.upper(): a for a in [
    "Tecnologia","Comercial/Varejo","Operações","Risco e Crédito","Atendimento/CX",
    "Financeiro","RH","Jurídico/Compliance","Marketing","Produtos Digitais"
]}
df["area"] = df["area"].str.strip()
qtd_corrigida = (~df["area"].isin(mapa_area.values())).sum()
df["area"] = df["area"].apply(lambda x: mapa_area.get(x.upper(), x))
registrar("Inconsistências de categoria 'área' padronizadas", qtd_corrigida, "ex: 'TECNOLOGIA ' → 'Tecnologia'")

mask_inv = (df["engajamento_score_base"] < 0) | (df["engajamento_score_base"] > 10)
qtd = mask_inv.sum()
df.loc[mask_inv, "engajamento_score_base"] = np.nan
registrar("Engajamento fora da escala 0-10 invalidado", qtd, "valores como -1, 11, 15, 99")

qtd_nulo_engaj = df["engajamento_score_base"].isnull().sum()
df["engajamento_score_base"] = df.groupby("area")["engajamento_score_base"].transform(lambda x: x.fillna(x.median()))
registrar("Nulos de engajamento imputados (mediana por área)", qtd_nulo_engaj)

faixa = {"Júnior/Pleno": (2000, 9000), "Sênior/Especialista": (6000, 20000), "Liderança": (15000, 45000)}
def fix_sal(row):
    if pd.isnull(row["salario_mensal"]): return row["salario_mensal"]
    lo, hi = faixa.get(row["senioridade"], (0, 1e9))
    return row["salario_mensal"]/100 if row["salario_mensal"] > hi*3 else row["salario_mensal"]
mask_out = df.apply(lambda r: not pd.isnull(r["salario_mensal"]) and r["salario_mensal"] > faixa.get(r["senioridade"],(0,1e9))[1]*3, axis=1)
qtd_out = mask_out.sum()
df["salario_mensal"] = df.apply(fix_sal, axis=1)
registrar("Outliers de salário corrigidos (erro de digitação ÷100)", qtd_out)

qtd_nulo_sal = df["salario_mensal"].isnull().sum()
df["salario_mensal"] = df.groupby(["area","senioridade"])["salario_mensal"].transform(lambda x: x.fillna(x.median()))
registrar("Nulos de salário imputados (mediana área+senioridade)", qtd_nulo_sal)

qtd_g = df["genero"].isnull().sum()
df["genero"] = df["genero"].fillna("Não informado")
registrar("Nulos de gênero rotulados como 'Não informado'", qtd_g, "dado demográfico não é imputável")

qtd_r = df["raca_cor"].isnull().sum()
df["raca_cor"] = df["raca_cor"].fillna("Não informado")
registrar("Nulos de raça/cor rotulados como 'Não informado'", qtd_r, "dado demográfico não é imputável")

df["data_admissao"] = pd.to_datetime(df["data_admissao"])
df["data_desligamento"] = pd.to_datetime(df["data_desligamento"], errors="coerce")
mask_dt = df["data_desligamento"].notna() & (df["data_desligamento"] < df["data_admissao"])
qtd_dt = mask_dt.sum()
df.loc[mask_dt, ["data_desligamento","tipo_desligamento","motivo_desligamento","status"]] = [pd.NaT, None, None, "Ativo"]
registrar("Inconsistências data_desligamento < data_admissao corrigidas", qtd_dt, "revertido para Ativo")

df["status"] = df["status"].replace("Ativo (corrigido)", "Ativo")

print(f"\nValidação final: {len(df)} linhas, {df.isnull().sum().sum() - df[['gestor_matricula','data_desligamento','tipo_desligamento','motivo_desligamento']].isnull().sum().sum()} nulos inesperados remanescentes")

os.makedirs(f"{BASE}/silver", exist_ok=True)
df.to_csv(f"{BASE}/silver/colaboradores_clean.csv", index=False, encoding="utf-8-sig")
with open(f"{BASE}/silver/_log_qualidade.json", "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)

print(f"\nSilver salva: {len(df)} linhas | {df.status.value_counts().to_dict()}")
