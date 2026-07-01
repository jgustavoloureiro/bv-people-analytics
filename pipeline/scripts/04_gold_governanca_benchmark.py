# -*- coding: utf-8 -*-
"""
GOLD parte 2 — Causa raiz (ITIL), governança completa, benchmarking setorial.
Benchmark usa apenas o que é publicamente verificável (GPTW 2025: Itaú líder
em retenção) + estimativas sintéticas claramente rotuladas como tal.
"""
import pandas as pd
import numpy as np
import json

BASE = "/home/claude/bv_people_analytics"
rng = np.random.default_rng(303)

df = pd.read_csv(f"{BASE}/silver/colaboradores_clean.csv")
deslig = df[df.status == "Desligado"].copy()
motivos_count = deslig[deslig.tipo_desligamento == "Voluntário"].motivo_desligamento.value_counts()

CI_MAP = {
    "Proposta salarial melhor": ["Sistema-Remuneracao-RM", "Politica-Reajuste-Anual", "Pesquisa-Salarial-Externa"],
    "Falta de plano de carreira": ["Sistema-Trilhas-Carreira", "Processo-PDI", "Comite-Sucessao"],
    "Conflito com liderança": ["Programa-Lideranca", "Pesquisa-Clima-Time", "Processo-Feedback-360"],
    "Mudança de cidade": ["Politica-Mobilidade", "Modelo-Trabalho-Remoto"],
    "Questões de saúde": ["Programa-Saude-Mental", "Beneficio-Plano-Saude"],
    "Reestruturação": ["Comite-Reestruturacao", "Processo-Realocacao-Interna"],
    "Baixa performance": ["Sistema-Avaliacao-Performance", "Processo-PIP", "Programa-Capacitacao"],
    "Aposentadoria": ["Politica-Aposentadoria", "Programa-Transicao-Carreira"],
    "Insatisfação com cultura": ["Pesquisa-Clima-Organizacional", "Programa-Cultura-Valores", "Processo-Onboarding"],
}
causa_raiz_ranking = []
for motivo, qtd in motivos_count.items():
    area_pred = deslig[deslig.motivo_desligamento == motivo].area.mode()
    area_pred = area_pred.iloc[0] if len(area_pred) > 0 else "Diversas"
    causa_raiz_ranking.append({
        "causa_raiz_desc": motivo, "area_predominante": area_pred,
        "total_desligamentos": int(qtd), "pct_do_total_voluntario": round(qtd/motivos_count.sum()*100,1),
        "itens_configuracao": CI_MAP.get(motivo, ["Processo-RH-Generico"]),
    })
with open(f"{BASE}/gold/causa_raiz.json", "w", encoding="utf-8") as f:
    json.dump(causa_raiz_ranking, f, ensure_ascii=False, indent=2)
print(f"Causa raiz: {len(causa_raiz_ranking)} causas")

# ----------------------------------------------------------------------
# GOVERNANÇA: planos de ação, 5W2H, RACI, PDCA, PMO
# ----------------------------------------------------------------------
RESPONSAVEIS = ["RH Business Partner", "Liderança de Área", "Comitê de Remuneração", "T&D Corporativo", "RH Estratégico"]
APROVADORES = ["Diretoria de RH", "Diretoria Executiva", "Gerência de Pessoas"]
ACOES = {
    "Falta de plano de carreira": "Lançar trilhas de carreira formais com checkpoints aos 12/36 meses",
    "Proposta salarial melhor": "Executar revisão de faixas salariais por benchmark de mercado",
    "Conflito com liderança": "Programa de desenvolvimento de lideranças com feedback 360",
    "Insatisfação com cultura": "Plano de ação de cultura a partir de pesquisa de clima segmentada",
    "Baixa performance": "Revisar processo de PIP com foco em capacitação antes de desligamento",
    "Reestruturação": "Criar banco de talentos interno para realocação prioritária",
    "Mudança de cidade": "Ampliar política de trabalho remoto/híbrido para áreas elegíveis",
    "Questões de saúde": "Reforçar programa de saúde mental e prevenção de burnout",
    "Aposentadoria": "Estruturar programa de transição de carreira e sucessão",
}
planos_acao, plano_5w2h, matriz_raci = [], [], []
for i, causa in enumerate(causa_raiz_ranking[:10]):
    pid = f"PA{i+1:03d}"
    prioridade = "Alta" if i < 4 else ("Média" if i < 7 else "Baixa")
    horizonte = 30 if i < 4 else (60 if i < 7 else 90)
    responsavel = RESPONSAVEIS[i % len(RESPONSAVEIS)]
    acao = ACOES.get(causa["causa_raiz_desc"], "Plano de ação a definir junto à área")

    planos_acao.append({"id": pid, "causa_raiz": causa["causa_raiz_desc"], "area_foco": causa["area_predominante"],
        "acao_proposta": acao, "horizonte_dias": horizonte, "prioridade": prioridade, "responsavel": responsavel,
        "impacto_estimado_turnover_pp": round(rng.uniform(1.5,5.0),1),
        "status": rng.choice(["Planejado","Em andamento","Em risco"], p=[0.4,0.45,0.15])})

    plano_5w2h.append({"plano_id": pid, "what": acao,
        "why": f"Eliminar/mitigar a causa-raiz '{causa['causa_raiz_desc']}', responsável por {causa['pct_do_total_voluntario']}% das saídas voluntárias, concentradas em {causa['area_predominante']}.",
        "who": responsavel, "where": f"Área {causa['area_predominante']} — implementação coordenada com RH Corporativo.",
        "when": f"Início imediato, conclusão em até {horizonte} dias.",
        "how": f"Diagnóstico detalhado, desenho da solução, piloto em {causa['area_predominante']}, rollout geral.",
        "how_much": round(rng.uniform(15000,65000),0)})

    matriz_raci.append({"plano_id": pid, "causa_raiz": causa["causa_raiz_desc"], "responsavel_R": responsavel,
        "aprovador_A": rng.choice(APROVADORES), "consultado_C": "Liderança de Área", "informado_I": "Diretoria Executiva"})

with open(f"{BASE}/gold/planos_acao.json","w",encoding="utf-8") as f: json.dump(planos_acao,f,ensure_ascii=False,indent=2)
with open(f"{BASE}/gold/plano_5w2h.json","w",encoding="utf-8") as f: json.dump(plano_5w2h,f,ensure_ascii=False,indent=2)
with open(f"{BASE}/gold/matriz_raci.json","w",encoding="utf-8") as f: json.dump(matriz_raci,f,ensure_ascii=False,indent=2)
print(f"Governança: {len(planos_acao)} planos, 5W2H, RACI")

pdca = []
for causa in causa_raiz_ranking[:5]:
    pdca.append({"causa_raiz": causa["causa_raiz_desc"],
        "plan": f"Diagnosticar extensão do problema '{causa['causa_raiz_desc']}' via pesquisa de clima segmentada e entrevistas de desligamento.",
        "do": f"Implementar piloto da ação corretiva em {causa['area_predominante']}, área de maior incidência.",
        "check": "Medir variação de turnover voluntário e engajamento na área-piloto após 60 dias.",
        "act": "Se resultado positivo, expandir para demais áreas; se não, revisar abordagem com a liderança."})
with open(f"{BASE}/gold/pdca.json","w",encoding="utf-8") as f: json.dump(pdca,f,ensure_ascii=False,indent=2)

pmo = [
    {"id":"PMO01","squad":"Squad Trilhas de Carreira","metodologia":"Scrum","sprint_atual":8,"pct_concluido":62,"proxima_entrega":"2026-08-15","status_geral":"No prazo","impacto_kpi":"Turnover Sênior"},
    {"id":"PMO02","squad":"Squad Remuneração Competitiva","metodologia":"Kanban","sprint_atual":5,"pct_concluido":78,"proxima_entrega":"2026-07-30","status_geral":"No prazo","impacto_kpi":"Turnover Tecnologia"},
    {"id":"PMO03","squad":"Squad Liderança Humanizada","metodologia":"Scrum","sprint_atual":11,"pct_concluido":45,"proxima_entrega":"2026-09-20","status_geral":"Em risco","impacto_kpi":"eNPS Geral"},
    {"id":"PMO04","squad":"Squad Onboarding 90 Dias","metodologia":"Kanban","sprint_atual":3,"pct_concluido":30,"proxima_entrega":"2026-10-01","status_geral":"No prazo","impacto_kpi":"Turnover <6m"},
    {"id":"PMO05","squad":"Squad Workforce Planning","metodologia":"Scrum","sprint_atual":6,"pct_concluido":55,"proxima_entrega":"2026-08-25","status_geral":"No prazo","impacto_kpi":"Acuracidade Forecast HC"},
]
with open(f"{BASE}/gold/pmo.json","w",encoding="utf-8") as f: json.dump(pmo,f,ensure_ascii=False,indent=2)
print(f"PDCA: {len(pdca)} ciclos | PMO: {len(pmo)} squads")

# ----------------------------------------------------------------------
# BENCHMARKING — 4 bancos brasileiros
# ----------------------------------------------------------------------
benchmark = {
    "bv": {"nome": "Banco BV", "turnover_anual_pct": 20.0, "enps": 51.6, "fonte": "dados internos (sintéticos)"},
    "concorrentes": [
        {"nome": "Itaú Unibanco", "turnover_anual_pct": 14.5, "enps": 58, "fonte_qualitativa": "Reconhecido pelo GPTW 2025 como líder em retenção de talentos no setor financeiro (dado público verificável)", "valores_estimados": True},
        {"nome": "Bradesco", "turnover_anual_pct": 17.0, "enps": 49, "fonte_qualitativa": "Presente no ranking GPTW Instituições Financeiras 2025; valores numéricos não publicados, estimados para fins de portfólio", "valores_estimados": True},
        {"nome": "Santander Brasil", "turnover_anual_pct": 18.5, "enps": 52, "fonte_qualitativa": "Reconhecido GPTW; cita 33 pontos de aumento no índice de confiança desde 2005 (dado público), turnover/eNPS estimados", "valores_estimados": True},
        {"nome": "Banco do Brasil", "turnover_anual_pct": 12.0, "enps": 47, "fonte_qualitativa": "Estatal, historicamente menor turnover por estabilidade de carreira; valores estimados para fins de portfólio", "valores_estimados": True},
    ],
    "media_mercado_turnover_pct": 16.4,
    "nota_metodologica": "Os números de turnover/eNPS dos concorrentes são ESTIMATIVAS SINTÉTICAS construídas a partir de "
                          "sinais qualitativos públicos (rankings GPTW 2025, reportagens). Nenhum desses bancos divulga "
                          "publicamente seu turnover ou eNPS exato — esses são indicadores internos de RH normalmente "
                          "não publicados. Para benchmarking real, seria necessário assinar pesquisa setorial paga "
                          "(Mercer, Korn Ferry, Aon) ou survey direto com as instituições.",
}
with open(f"{BASE}/gold/benchmark_mercado.json","w",encoding="utf-8") as f:
    json.dump(benchmark, f, ensure_ascii=False, indent=2)
print("Benchmark de mercado salvo (4 bancos + BV)")

print("\n=== GOLD PARTE 2 CONCLUÍDA ===")
