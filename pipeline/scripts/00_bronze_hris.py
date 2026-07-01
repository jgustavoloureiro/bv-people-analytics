# -*- coding: utf-8 -*-
"""
CAMADA BRONZE — Geração de dados brutos fictícios
Simula exportação direta de sistemas: HRIS, ERP financeiro, plataforma de
pesquisa de clima, ATS (recrutamento). Propositalmente "sujo" (nulos,
duplicatas, inconsistências) para a camada Silver tratar depois.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import os

rng = np.random.default_rng(2026)
BASE = "/home/claude/bv_people_analytics"

N_COLAB_INICIAL = 4400
MESES_HISTORICO = 36
DATA_FIM = datetime(2026, 6, 30)
DATA_INICIO_HIST = DATA_FIM - timedelta(days=MESES_HISTORICO * 30)
CRESCIMENTO_ANUAL = 0.045

# ----------------------------------------------------------------------
# ESTRUTURA ORGANIZACIONAL
# ----------------------------------------------------------------------
AREAS = {
    "Tecnologia": {"peso": 0.20, "turnover_base": 0.017, "senior_mix": [0.35, 0.40, 0.25]},
    "Comercial/Varejo": {"peso": 0.19, "turnover_base": 0.021, "senior_mix": [0.45, 0.40, 0.15]},
    "Operações": {"peso": 0.14, "turnover_base": 0.019, "senior_mix": [0.50, 0.35, 0.15]},
    "Risco e Crédito": {"peso": 0.10, "turnover_base": 0.011, "senior_mix": [0.30, 0.45, 0.25]},
    "Atendimento/CX": {"peso": 0.12, "turnover_base": 0.027, "senior_mix": [0.60, 0.30, 0.10]},
    "Financeiro": {"peso": 0.07, "turnover_base": 0.010, "senior_mix": [0.30, 0.45, 0.25]},
    "RH": {"peso": 0.05, "turnover_base": 0.012, "senior_mix": [0.35, 0.40, 0.25]},
    "Jurídico/Compliance": {"peso": 0.05, "turnover_base": 0.009, "senior_mix": [0.25, 0.45, 0.30]},
    "Marketing": {"peso": 0.04, "turnover_base": 0.018, "senior_mix": [0.40, 0.40, 0.20]},
    "Produtos Digitais": {"peso": 0.04, "turnover_base": 0.020, "senior_mix": [0.40, 0.40, 0.20]},
}
SENIORIDADES = ["Júnior/Pleno", "Sênior/Especialista", "Liderança"]
CARGOS = {
    "Tecnologia": ["Analista de Dados", "Engenheiro de Software", "Engenheiro de Dados", "Arquiteto de Soluções", "Coordenador de TI", "Gerente de TI"],
    "Comercial/Varejo": ["Gerente de Contas", "Analista Comercial", "Consultor de Investimentos", "Coordenador Comercial", "Gerente Regional"],
    "Operações": ["Analista de Operações", "Especialista em Processos", "Coordenador de Operações", "Gerente de Operações"],
    "Risco e Crédito": ["Analista de Risco", "Analista de Crédito", "Especialista em Modelagem", "Coordenador de Risco", "Gerente de Risco"],
    "Atendimento/CX": ["Atendente", "Analista de CX", "Supervisor de Atendimento", "Coordenador de CX"],
    "Financeiro": ["Analista Financeiro", "Controller", "Coordenador Financeiro", "Gerente Financeiro"],
    "RH": ["Analista de RH", "Business Partner", "Especialista em People Analytics", "Coordenador de RH", "Gerente de RH"],
    "Jurídico/Compliance": ["Analista Jurídico", "Especialista em Compliance", "Coordenador Jurídico", "Gerente Jurídico"],
    "Marketing": ["Analista de Marketing", "Especialista em Growth", "Coordenador de Marketing", "Gerente de Marketing"],
    "Produtos Digitais": ["Product Analyst", "Product Manager", "UX Researcher", "Coordenador de Produto", "Head de Produto"],
}
CIDADES = [("São Paulo", 0.42), ("Rio de Janeiro", 0.17), ("Belo Horizonte", 0.09),
           ("Porto Alegre", 0.08), ("Curitiba", 0.07), ("Brasília", 0.07), ("Recife", 0.05), ("Remoto", 0.05)]
GENEROS = [("Feminino", 0.49), ("Masculino", 0.50), ("Não-binário/Outro", 0.01)]
RACAS = [("Branca", 0.50), ("Parda", 0.28), ("Preta", 0.15), ("Amarela", 0.04), ("Indígena", 0.01), ("Não informado", 0.02)]

def escolher(opcoes):
    valores = [o[0] for o in opcoes]
    pesos = [o[1] for o in opcoes]
    return rng.choice(valores, p=np.array(pesos)/sum(pesos))

# ----------------------------------------------------------------------
# GERAR COLABORADORES INICIAIS
# ----------------------------------------------------------------------
colaboradores = []
areas_list = list(AREAS.keys())
pesos_area = [AREAS[a]["peso"] for a in areas_list]

for i in range(N_COLAB_INICIAL):
    matricula = 100000 + i
    area = rng.choice(areas_list, p=np.array(pesos_area)/sum(pesos_area))
    senior_mix = AREAS[area]["senior_mix"]
    senioridade = rng.choice(SENIORIDADES, p=senior_mix)
    cargo = rng.choice(CARGOS[area])

    if rng.random() < 0.55:
        tempo_casa_meses = int(rng.uniform(MESES_HISTORICO + 1, 240))
    else:
        tempo_casa_meses = int(rng.uniform(0, MESES_HISTORICO))
    data_admissao = DATA_FIM - timedelta(days=tempo_casa_meses * 30)

    idade = int(rng.normal(loc=33 + tempo_casa_meses/24, scale=7))
    idade = max(19, min(idade, 68))
    genero = escolher(GENEROS)
    raca = escolher(RACAS)
    cidade = escolher(CIDADES)

    faixa_base = {"Júnior/Pleno": 5500, "Sênior/Especialista": 11000, "Liderança": 22000}[senioridade]
    ajuste_area = {"Tecnologia": 1.18, "Produtos Digitais": 1.15, "Risco e Crédito": 1.10,
                   "Comercial/Varejo": 1.05, "Jurídico/Compliance": 1.08, "Financeiro": 1.05}.get(area, 1.0)
    salario = round(max(faixa_base * ajuste_area * rng.normal(1.0, 0.12), 2200), 2)

    engajamento_base = 7.5 - 0.02 * min(tempo_casa_meses, 36) + 0.01 * max(0, tempo_casa_meses - 36)
    engajamento_base += rng.normal(0, 1.8)
    engajamento_base = max(1, min(10, engajamento_base))

    performance = rng.normal(3.4, 0.7)
    performance = max(1, min(5, round(performance * 2) / 2))

    # Produtividade individual (índice 0-150, base 100) — correlacionado com performance
    produtividade_individual = 70 + performance * 12 + rng.normal(0, 10)
    produtividade_individual = max(40, min(150, produtividade_individual))

    colaboradores.append({
        "matricula": matricula, "nome_ficticio": f"Colaborador_{matricula}",
        "area": area, "cargo": cargo, "senioridade": senioridade,
        "data_admissao": data_admissao.strftime("%Y-%m-%d"),
        "tempo_casa_meses": tempo_casa_meses, "idade": idade, "genero": genero,
        "raca_cor": raca, "cidade": cidade, "salario_mensal": salario,
        "engajamento_score_base": round(engajamento_base, 2), "performance_score": performance,
        "produtividade_index_base": round(produtividade_individual, 1),
        "gestor_matricula": None,
    })

df_colab = pd.DataFrame(colaboradores)

for area in areas_list:
    lideres = df_colab[(df_colab.area == area) & (df_colab.senioridade == "Liderança")].matricula.tolist()
    subordinados_idx = df_colab[(df_colab.area == area) & (df_colab.senioridade != "Liderança")].index
    if len(lideres) == 0:
        lideres = [None]
    for idx in subordinados_idx:
        df_colab.loc[idx, "gestor_matricula"] = rng.choice(lideres) if lideres[0] is not None else None

print(f"Colaboradores iniciais: {len(df_colab)}")

# ----------------------------------------------------------------------
# LOOP CRONOLÓGICO: turnover + contratações (engajamento como driver causal)
# ----------------------------------------------------------------------
meses_periodo = pd.date_range(start=DATA_INICIO_HIST, end=DATA_FIM, freq="MS")
desligamentos = []
status_atual = {row.matricula: "Ativo" for row in df_colab.itertuples()}
pool = {row.matricula: dict(area=row.area, engajamento=row.engajamento_score_base, data_admissao=pd.Timestamp(row.data_admissao))
        for row in df_colab.itertuples()}
novas_contratacoes = []
proxima_matricula = df_colab.matricula.max() + 1
headcount_corrente = sum(1 for v in pool.values() if v["data_admissao"] <= meses_periodo[0])

for mes in meses_periodo:
    sazonalidade = 1.35 if mes.month in [1, 2] else (1.20 if mes.month == 12 else 1.0)
    deslig_no_mes = 0
    for matricula, info in pool.items():
        if status_atual[matricula] != "Ativo" or info["data_admissao"] > mes:
            continue
        turnover_base = AREAS[info["area"]]["turnover_base"]
        fator_engajamento = max(0.2, 5.0 - 0.55 * info["engajamento"])
        meses_desde = (mes.year - info["data_admissao"].year) * 12 + (mes.month - info["data_admissao"].month)
        fator_tempo = 2.2 if meses_desde < 6 else (1.7 if meses_desde > 48 else 0.6)
        prob = turnover_base * fator_engajamento * fator_tempo * sazonalidade
        if rng.random() < prob:
            status_atual[matricula] = "Desligado"
            tipo = "Voluntário" if rng.random() < 0.68 else "Involuntário"
            motivo = rng.choice([
                "Proposta salarial melhor", "Falta de plano de carreira", "Conflito com liderança",
                "Mudança de cidade", "Questões de saúde", "Reestruturação", "Baixa performance",
                "Aposentadoria", "Insatisfação com cultura"
            ], p=[0.22, 0.18, 0.12, 0.08, 0.06, 0.10, 0.10, 0.04, 0.10])
            desligamentos.append({"matricula": matricula, "data_desligamento": mes.strftime("%Y-%m-%d"),
                                    "tipo_desligamento": tipo, "motivo_desligamento": motivo})
            deslig_no_mes += 1

    meta_crescimento = headcount_corrente * (CRESCIMENTO_ANUAL / 12)
    n_contratacoes = max(0, int(round(deslig_no_mes * rng.uniform(0.85, 1.05) + meta_crescimento + rng.normal(0, 2))))
    for _ in range(n_contratacoes):
        area = rng.choice(areas_list, p=np.array(pesos_area)/sum(pesos_area))
        senioridade = rng.choice(SENIORIDADES, p=[0.55, 0.35, 0.10])
        cargo = rng.choice(CARGOS[area])
        idade = max(21, min(int(rng.normal(29, 5)), 55))
        genero, raca, cidade = escolher(GENEROS), escolher(RACAS), escolher(CIDADES)
        faixa_base = {"Júnior/Pleno": 5500, "Sênior/Especialista": 11000, "Liderança": 22000}[senioridade]
        ajuste_area = {"Tecnologia": 1.18, "Produtos Digitais": 1.15, "Risco e Crédito": 1.10,
                       "Comercial/Varejo": 1.05, "Jurídico/Compliance": 1.08, "Financeiro": 1.05}.get(area, 1.0)
        salario = round(max(faixa_base * ajuste_area * rng.normal(1.0, 0.12), 2200), 2)
        engaj_inicial = max(1, min(10, rng.normal(7.8, 0.8)))
        performance = max(1, min(5, round(rng.normal(3.2, 0.6) * 2) / 2))
        prod = max(40, min(150, 70 + performance * 12 + rng.normal(0, 10)))

        novas_contratacoes.append({
            "matricula": proxima_matricula, "nome_ficticio": f"Colaborador_{proxima_matricula}",
            "area": area, "cargo": cargo, "senioridade": senioridade,
            "data_admissao": mes.strftime("%Y-%m-%d"), "tempo_casa_meses": 0, "idade": idade,
            "genero": genero, "raca_cor": raca, "cidade": cidade, "salario_mensal": salario,
            "engajamento_score_base": round(engaj_inicial, 2), "performance_score": performance,
            "produtividade_index_base": round(prod, 1), "gestor_matricula": None,
        })
        status_atual[proxima_matricula] = "Ativo"
        pool[proxima_matricula] = dict(area=area, engajamento=engaj_inicial, data_admissao=mes)
        proxima_matricula += 1
    headcount_corrente += n_contratacoes - deslig_no_mes

df_deslig = pd.DataFrame(desligamentos)
df_novas = pd.DataFrame(novas_contratacoes)
df_colab = pd.concat([df_colab, df_novas], ignore_index=True)
df_colab["status"] = df_colab.matricula.map(lambda m: status_atual[m])
df_colab = df_colab.merge(df_deslig, on="matricula", how="left")

print(f"Total histórico (inicial + contratados): {len(df_colab)}")
print(f"Desligamentos: {len(df_deslig)}")
print(f"Ativos hoje: {(df_colab.status=='Ativo').sum()}")

# ----------------------------------------------------------------------
# INJETAR PROBLEMAS DE QUALIDADE (propositais)
# ----------------------------------------------------------------------
df_raw = df_colab.copy()
n_dup = 52
df_raw = pd.concat([df_raw, df_raw.sample(n=n_dup, random_state=1)], ignore_index=True)

for col, n in [("genero", 90), ("raca_cor", 150), ("engajamento_score_base", 230), ("salario_mensal", 25)]:
    idx = rng.choice(df_raw.index, size=n, replace=False)
    df_raw.loc[idx, col] = None

idx_out = rng.choice(df_raw[df_raw.salario_mensal.notna()].index, size=16, replace=False)
df_raw.loc[idx_out, "salario_mensal"] = df_raw.loc[idx_out, "salario_mensal"] * 100

idx_inval = rng.choice(df_raw[df_raw.engajamento_score_base.notna()].index, size=14, replace=False)
df_raw.loc[idx_inval, "engajamento_score_base"] = rng.choice([-1, 11, 15, 99], size=14)

idx_incons = rng.choice(df_raw[df_raw.status == "Desligado"].index, size=7, replace=False)
df_raw.loc[idx_incons, "data_desligamento"] = "2021-01-01"

idx_var = rng.choice(df_raw[df_raw.area == "Tecnologia"].index, size=20, replace=False)
df_raw.loc[idx_var, "area"] = "TECNOLOGIA "

os.makedirs(f"{BASE}/bronze", exist_ok=True)
df_raw.to_csv(f"{BASE}/bronze/hris_colaboradores_raw.csv", index=False, encoding="utf-8-sig")
df_deslig.to_csv(f"{BASE}/bronze/hris_desligamentos_raw.csv", index=False, encoding="utf-8-sig")

meta = {"n_colab_inicial": N_COLAB_INICIAL, "meses_historico": MESES_HISTORICO,
        "data_inicio": DATA_INICIO_HIST.strftime("%Y-%m-%d"), "data_fim": DATA_FIM.strftime("%Y-%m-%d"),
        "areas": areas_list, "crescimento_anual": CRESCIMENTO_ANUAL}
with open(f"{BASE}/bronze/_meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print(f"\nBronze salva: {len(df_raw)} linhas (com {n_dup} duplicatas propositais)")
