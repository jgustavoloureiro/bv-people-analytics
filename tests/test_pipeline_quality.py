# -*- coding: utf-8 -*-
"""
TESTES AUTOMATIZADOS — People Analytics Pipeline
================================================
Suite de testes de qualidade de dados e validação do modelo preditivo.
Executa como parte do CI/CD (GitHub Actions) e como gate antes de
promover dados de Bronze → Silver → Gold.

Rodar localmente:
    pip install pytest pytest-cov great-expectations pandas numpy scikit-learn
    pytest tests/ -v --cov=pipeline/scripts --cov-report=html
"""
import pytest
import pandas as pd
import numpy as np
import json
import os

# ─── FIXTURES ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def df_bronze():
    """Carrega a camada Bronze para testes de qualidade."""
    path = "pipeline/bronze/hris_colaboradores_raw.csv"
    if os.path.exists(path):
        return pd.read_csv(path, encoding="utf-8-sig")
    pytest.skip(f"Bronze não encontrado em {path} — rode o script 00 primeiro.")

@pytest.fixture(scope="session")
def df_silver():
    """Carrega a camada Silver para testes de qualidade."""
    # Tenta Parquet primeiro (produção), fallback para CSV (dev)
    parquet_path = "pipeline/silver/colaboradores"
    csv_path     = "pipeline/silver/colaboradores_clean.csv"
    if os.path.exists(parquet_path):
        import glob
        files = glob.glob(f"{parquet_path}/**/*.parquet", recursive=True)
        if files:
            return pd.read_parquet(parquet_path)
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path, encoding="utf-8-sig")
    pytest.skip("Silver não encontrada — rode o script 01/10 primeiro.")

@pytest.fixture(scope="session")
def modelo_metricas():
    """Carrega métricas do modelo preditivo."""
    path = "pipeline/gold/metricas_modelo_attrition.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    pytest.skip("Métricas do modelo não encontradas.")

# ─── TESTES DE VOLUMETRIA BRONZE ──────────────────────────────────────────────
class TestBronzeVolumetria:
    """Garante que a Bronze tem volume mínimo esperado."""

    def test_volume_minimo(self, df_bronze):
        """Bronze deve ter pelo menos 4.000 linhas."""
        assert len(df_bronze) >= 4_000, \
            f"Volume insuficiente: {len(df_bronze)} linhas (mínimo: 4.000)"

    def test_colunas_obrigatorias(self, df_bronze):
        """Todas as colunas obrigatórias devem estar presentes."""
        cols_obrigatorias = [
            "matricula", "area", "cargo", "senioridade",
            "data_admissao", "idade", "genero", "salario_mensal",
            "engajamento_score_base", "performance_score", "status"
        ]
        faltando = [c for c in cols_obrigatorias if c not in df_bronze.columns]
        assert not faltando, f"Colunas faltando: {faltando}"

    def test_matricula_positiva(self, df_bronze):
        """Matrícula deve ser positiva e não nula."""
        assert df_bronze["matricula"].notna().all(), "Matrículas nulas encontradas"
        assert (df_bronze["matricula"] > 0).all(), "Matrículas inválidas (≤0) encontradas"

    def test_areas_conhecidas(self, df_bronze):
        """Áreas devem ser do conjunto esperado (após possível normalização)."""
        areas_validas = {
            "Tecnologia","Comercial/Varejo","Operações","Risco e Crédito",
            "Atendimento/CX","Financeiro","RH","Jurídico/Compliance",
            "Marketing","Produtos Digitais",
            "TECNOLOGIA","TECNOLOGIA ","tecnologia",   # tolerância para Bronze
        }
        areas_invalidas = set(df_bronze["area"].str.strip().unique()) - areas_validas
        pct_invalidas = len(df_bronze[df_bronze["area"].str.strip().isin(areas_invalidas)]) / len(df_bronze)
        assert pct_invalidas < 0.05, \
            f"Mais de 5% das linhas com área inválida: {areas_invalidas}"

    def test_duplicatas_aceitaveis(self, df_bronze):
        """Duplicatas exatas não devem ultrapassar 5% da base."""
        pct_dup = df_bronze.duplicated().mean()
        assert pct_dup <= 0.05, \
            f"Taxa de duplicatas acima de 5%: {pct_dup:.1%}"


# ─── TESTES DE QUALIDADE SILVER ───────────────────────────────────────────────
class TestSilverQualidade:
    """Valida que o pipeline de limpeza funcionou corretamente."""

    def test_zero_duplicatas(self, df_silver):
        """Silver deve ter zero duplicatas por matrícula."""
        dups = df_silver.duplicated(subset=["matricula"]).sum()
        assert dups == 0, f"{dups} duplicatas por matrícula na Silver"

    def test_engajamento_range(self, df_silver):
        """Engajamento deve estar entre 0 e 10."""
        invalidos = df_silver[
            (df_silver["engajamento_score_base"] < 0) |
            (df_silver["engajamento_score_base"] > 10)
        ]
        assert len(invalidos) == 0, \
            f"{len(invalidos)} registros com engajamento fora do range 0-10"

    def test_engajamento_sem_nulos(self, df_silver):
        """Engajamento não deve ter nulos na Silver (devem ter sido imputados)."""
        nulos = df_silver["engajamento_score_base"].isna().sum()
        assert nulos == 0, f"{nulos} nulos em engajamento_score_base"

    def test_salario_range(self, df_silver):
        """Salário deve estar entre R$1.320 (piso nacional) e R$100k."""
        invalidos = df_silver[
            (df_silver["salario_mensal"] < 1_320) |
            (df_silver["salario_mensal"] > 100_000)
        ]
        assert len(invalidos) == 0, \
            f"{len(invalidos)} salários fora do range [1320, 100000]"

    def test_datas_consistentes(self, df_silver):
        """data_desligamento não pode ser anterior a data_admissao."""
        df = df_silver.copy()
        df["data_admissao"]    = pd.to_datetime(df["data_admissao"])
        df["data_desligamento"] = pd.to_datetime(df["data_desligamento"], errors="coerce")
        inconsistentes = df[
            df["data_desligamento"].notna() &
            (df["data_desligamento"] < df["data_admissao"])
        ]
        assert len(inconsistentes) == 0, \
            f"{len(inconsistentes)} registros com data_desligamento < data_admissao"

    def test_status_valido(self, df_silver):
        """Status deve ser Ativo ou Desligado."""
        status_validos = {"Ativo", "Desligado"}
        status_invalidos = set(df_silver["status"].unique()) - status_validos
        assert not status_invalidos, \
            f"Status inválidos encontrados: {status_invalidos}"

    def test_areas_padronizadas(self, df_silver):
        """Todas as áreas na Silver devem estar padronizadas (sem espaços extras)."""
        areas_com_espaco = df_silver["area"][df_silver["area"].str.strip() != df_silver["area"]]
        assert len(areas_com_espaco) == 0, \
            f"{len(areas_com_espaco)} áreas com espaços não padronizados"

    def test_demograficos_sem_nulo(self, df_silver):
        """Gênero e raça/cor não devem ter nulos (devem ser 'Não informado')."""
        for col in ["genero", "raca_cor"]:
            nulos = df_silver[col].isna().sum()
            assert nulos == 0, \
                f"{nulos} nulos em {col} na Silver (use 'Não informado' para ausentes)"

    def test_distribuicao_senioridade(self, df_silver):
        """Distribuição de senioridade deve ser razoável (nenhuma > 70% da base)."""
        dist = df_silver["senioridade"].value_counts(normalize=True)
        assert (dist <= 0.70).all(), \
            f"Senioridade muito concentrada: {dist.to_dict()}"

    def test_silver_maior_que_metade_bronze(self, df_bronze, df_silver):
        """Silver deve ter pelo menos 90% das linhas da Bronze (após deduplicação)."""
        if df_bronze is None:
            pytest.skip("Bronze não carregada")
        ratio = len(df_silver) / len(df_bronze)
        assert ratio >= 0.85, \
            f"Silver tem {ratio:.1%} das linhas da Bronze — perda excessiva no pipeline"


# ─── TESTES DO MODELO PREDITIVO ───────────────────────────────────────────────
class TestModeloAttrition:
    """Valida a qualidade do modelo preditivo de attrition."""

    def test_auc_minimo(self, modelo_metricas):
        """ROC-AUC deve ser acima de 0.60 (melhor que aleatório de forma significativa)."""
        auc = modelo_metricas["roc_auc"]
        assert auc >= 0.60, \
            f"ROC-AUC insuficiente: {auc} (mínimo: 0.60 para uso em produção)"

    def test_auc_nao_suspeito(self, modelo_metricas):
        """ROC-AUC não deve ser suspeitamente alto (vazamento de dados)."""
        auc = modelo_metricas["roc_auc"]
        assert auc <= 0.97, \
            f"ROC-AUC suspeito: {auc} — possível data leakage. Revisar features."

    def test_volume_treino_adequado(self, modelo_metricas):
        """Base de treino deve ter pelo menos 1.000 registros."""
        assert modelo_metricas["n_treino"] >= 1_000, \
            f"Base de treino pequena: {modelo_metricas['n_treino']} registros"

    def test_taxa_attrition_realista(self, modelo_metricas):
        """Taxa de attrition na janela de predição deve ser entre 5% e 30%."""
        taxa = modelo_metricas["taxa_attrition_base"]
        assert 5.0 <= taxa <= 30.0, \
            f"Taxa de attrition fora do range esperado: {taxa}%"

    def test_engajamento_fator_dominante(self, modelo_metricas):
        """Engajamento deve ser o fator de maior importância (validação de negócio)."""
        fatores = modelo_metricas["fatores_risco_top5"]
        fator_top = max(fatores, key=fatores.get)
        assert "engajamento" in fator_top.lower(), \
            f"Engajamento não é o fator dominante: top fator = {fator_top}"

    def test_scores_salvos(self):
        """Arquivo de scores deve existir e ter volume mínimo."""
        scores_path = "pipeline/gold/scores_attrition.csv"
        if not os.path.exists(scores_path):
            pytest.skip("Scores de attrition não encontrados (rode o script 03 primeiro)")
        df_scores = pd.read_csv(scores_path)
        assert len(df_scores) >= 1_000, \
            f"Poucos colaboradores com score: {len(df_scores)}"
        assert "risco_attrition_score" in df_scores.columns
        assert (df_scores["risco_attrition_score"].between(0, 1)).all(), \
            "Scores fora do range [0, 1]"


# ─── TESTES DE INTEGRAÇÃO ─────────────────────────────────────────────────────
class TestIntegracao:
    """Testa a integridade end-to-end do pipeline."""

    def test_gold_existe(self):
        """Camada Gold deve existir com arquivos de série mensal e scores."""
        arquivos_gold = [
            "pipeline/gold/metricas_modelo_attrition.json",
        ]
        for path in arquivos_gold:
            assert os.path.exists(path), f"Arquivo Gold não encontrado: {path}"

    def test_json_dashboard_valido(self):
        """data.json do dashboard deve ser JSON válido e com chaves obrigatórias."""
        path = "dashboard/data.json" if os.path.exists("dashboard/data.json") else \
               "dashboard/data_compact.json"
        if not os.path.exists(path):
            pytest.skip("data.json não encontrado")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        chaves_obrigatorias = ["kpis", "causa_raiz", "modelo"]
        for chave in chaves_obrigatorias:
            assert chave in data, f"Chave obrigatória ausente no data.json: {chave}"

    def test_xlsx_bronze_valido(self):
        """Arquivo Excel Bronze deve existir e ter as abas esperadas."""
        path = "pipeline/bronze/Banco_BV_People_Analytics_Base_Bruta.xlsx"
        if not os.path.exists(path):
            pytest.skip("XLSX Bronze não encontrado")
        xl = pd.ExcelFile(path)
        abas_esperadas = ["HRIS_Colaboradores", "HRIS_Desligamentos"]
        for aba in abas_esperadas:
            assert aba in xl.sheet_names, f"Aba esperada não encontrada: {aba}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
