# -*- coding: utf-8 -*-
"""
MODELO PREDITIVO DE ATTRITION — Random Forest, validado honestamente.
Replica a lógica que já validou ROC-AUC ~0.73 no projeto anterior.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder
import json

BASE = "/home/claude/bv_people_analytics"
df = pd.read_csv(f"{BASE}/silver/colaboradores_clean.csv")
df["data_admissao"] = pd.to_datetime(df["data_admissao"])
df["data_desligamento"] = pd.to_datetime(df["data_desligamento"])

DATA_REF = pd.Timestamp("2025-06-30")
JANELA_DIAS = 365

elegiveis = df[(df.data_admissao <= DATA_REF) & ((df.data_desligamento.isna()) | (df.data_desligamento > DATA_REF))].copy()
elegiveis["saiu_12m"] = (
    (elegiveis.data_desligamento.notna()) &
    (elegiveis.data_desligamento > DATA_REF) &
    (elegiveis.data_desligamento <= DATA_REF + pd.Timedelta(days=JANELA_DIAS)) &
    (elegiveis.tipo_desligamento == "Voluntário")
).astype(int)
elegiveis["tempo_casa_meses_ref"] = ((DATA_REF - elegiveis.data_admissao).dt.days / 30).round(0)

print(f"Base elegível: {len(elegiveis)} | Saíram em 12m: {elegiveis.saiu_12m.sum()} ({elegiveis.saiu_12m.mean()*100:.1f}%)")

features_num = ["idade", "tempo_casa_meses_ref", "salario_mensal", "engajamento_score_base", "performance_score", "produtividade_index_base"]
features_cat = ["area", "senioridade", "genero", "cidade"]

X = elegiveis[features_num + features_cat].copy()
y = elegiveis["saiu_12m"]
encoders = {}
for col in features_cat:
    le = LabelEncoder()
    X[col] = le.fit_transform(X[col].astype(str))
    encoders[col] = le

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

modelo = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=15, class_weight="balanced", random_state=42, n_jobs=-1)
modelo.fit(X_train, y_train)
auc = roc_auc_score(y_test, modelo.predict_proba(X_test)[:,1])
print(f"ROC-AUC (holdout): {auc:.3f}")

importancias = pd.Series(modelo.feature_importances_, index=X.columns).sort_values(ascending=False)
print("Fatores de risco:\n", importancias)

ativos_hoje = df[df.status == "Ativo"].copy()
ativos_hoje["tempo_casa_meses_ref"] = ((pd.Timestamp("2026-06-30") - ativos_hoje.data_admissao).dt.days / 30).round(0)
X_hoje = ativos_hoje[features_num + features_cat].copy()
for col in features_cat:
    X_hoje[col] = X_hoje[col].astype(str).apply(lambda v: v if v in encoders[col].classes_ else encoders[col].classes_[0])
    X_hoje[col] = encoders[col].transform(X_hoje[col])

ativos_hoje["risco_attrition_score"] = modelo.predict_proba(X_hoje)[:,1]
ativos_hoje["faixa_risco"] = pd.cut(ativos_hoje["risco_attrition_score"], bins=[0,0.15,0.35,1.0], labels=["Baixo","Médio","Alto"])

print(f"\nDistribuição de risco na base ativa:\n{ativos_hoje.faixa_risco.value_counts()}")

top_risco = ativos_hoje.nlargest(20, "risco_attrition_score")[
    ["matricula","area","cargo","senioridade","tempo_casa_meses_ref","engajamento_score_base","performance_score","risco_attrition_score"]
]
risco_area = ativos_hoje.groupby("area").agg(
    headcount=("matricula","count"), risco_medio=("risco_attrition_score","mean"),
    qtd_alto_risco=("faixa_risco", lambda x: (x=="Alto").sum())
).round(3).sort_values("risco_medio", ascending=False).reset_index()

ativos_hoje[["matricula","area","cargo","senioridade","tempo_casa_meses_ref","engajamento_score_base",
             "performance_score","salario_mensal","risco_attrition_score","faixa_risco"]].to_csv(
    f"{BASE}/gold/scores_attrition.csv", index=False, encoding="utf-8-sig")
risco_area.to_csv(f"{BASE}/gold/risco_attrition_por_area.csv", index=False, encoding="utf-8-sig")
top_risco.to_csv(f"{BASE}/gold/top_risco_attrition.csv", index=False, encoding="utf-8-sig")

metricas = {
    "roc_auc": round(auc,3), "n_treino": len(X_train), "n_teste": len(X_test),
    "taxa_attrition_base": round(y.mean()*100,1),
    "fatores_risco_top5": importancias.head(5).round(3).to_dict(),
    "colaboradores_risco_alto": int((ativos_hoje.faixa_risco=="Alto").sum()),
    "colaboradores_risco_medio": int((ativos_hoje.faixa_risco=="Médio").sum()),
    "colaboradores_risco_baixo": int((ativos_hoje.faixa_risco=="Baixo").sum()),
    "data_referencia_treino": str(DATA_REF.date()), "janela_predicao_dias": JANELA_DIAS,
    "limitacao": "Modelo treinado sobre dados sintéticos para fins de portfólio. Em produção, exigiria "
                 "validação cruzada temporal, dados reais de pesquisa de clima e revisão de viés em "
                 "atributos sensíveis antes de qualquer uso para decisão de RH.",
}
with open(f"{BASE}/gold/metricas_modelo_attrition.json", "w", encoding="utf-8") as f:
    json.dump(metricas, f, ensure_ascii=False, indent=2)

print(f"\nModelo salvo. AUC={auc:.3f}, risco alto={metricas['colaboradores_risco_alto']}")
