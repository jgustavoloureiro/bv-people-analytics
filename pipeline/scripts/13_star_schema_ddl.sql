-- =============================================================================
-- MODELAGEM DIMENSIONAL — PEOPLE ANALYTICS DATA WAREHOUSE
-- =============================================================================
-- Star Schema para o DW de People Analytics do Banco BV
-- Compatível com: AWS Redshift, Azure Synapse Analytics, Databricks SQL
--
-- Arquitetura:
--   - Fato: fct_desligamento, fct_headcount_mensal
--   - Dimensões: dim_colaborador, dim_data, dim_area, dim_motivo
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- SCHEMA
-- ─────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS people_analytics;


-- ─────────────────────────────────────────────────────────────────────────────
-- DIM_DATA
-- Dimensão calendário completa (grain: dia)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS people_analytics.dim_data (
    sk_data             INT         NOT NULL,       -- surrogate key (YYYYMMDD)
    data_completa       DATE        NOT NULL,
    ano                 SMALLINT    NOT NULL,
    semestre            SMALLINT    NOT NULL,
    trimestre           SMALLINT    NOT NULL,
    mes                 SMALLINT    NOT NULL,
    nome_mes            VARCHAR(20) NOT NULL,
    semana_ano          SMALLINT    NOT NULL,
    dia_mes             SMALLINT    NOT NULL,
    dia_semana          SMALLINT    NOT NULL,       -- 1=Dom ... 7=Sáb
    nome_dia_semana     VARCHAR(20) NOT NULL,
    e_fim_de_semana     BOOLEAN     NOT NULL,
    e_feriado_nacional  BOOLEAN     NOT NULL DEFAULT FALSE,
    competencia         CHAR(7)     NOT NULL,       -- YYYY-MM
    CONSTRAINT pk_dim_data PRIMARY KEY (sk_data)
)
SORTKEY (data_completa);    -- Redshift: melhora performance de range scans


-- ─────────────────────────────────────────────────────────────────────────────
-- DIM_AREA
-- Estrutura organizacional do banco
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS people_analytics.dim_area (
    sk_area             SMALLINT    NOT NULL,
    area                VARCHAR(50) NOT NULL,
    diretoria           VARCHAR(50),
    vice_presidencia    VARCHAR(50),
    centro_de_custo     VARCHAR(20),
    classificacao_risco VARCHAR(20),   -- Alta/Média/Baixa rotatividade histórica
    CONSTRAINT pk_dim_area PRIMARY KEY (sk_area)
);

INSERT INTO people_analytics.dim_area VALUES
  (1, 'Tecnologia',           'Diretoria de Tecnologia', 'VP de Tecnologia e Dados', 'CC-TI-001', 'Média'),
  (2, 'Comercial/Varejo',     'Diretoria Comercial',     'VP Comercial',              'CC-COM-001', 'Alta'),
  (3, 'Operações',            'Diretoria de Operações',  'VP Operações',              'CC-OPS-001', 'Média'),
  (4, 'Risco e Crédito',      'Diretoria de Risco',      'VP de Risco',               'CC-RSC-001', 'Baixa'),
  (5, 'Atendimento/CX',       'Diretoria de CX',         'VP de Clientes',            'CC-CX-001',  'Alta'),
  (6, 'Financeiro',           'Diretoria Financeira',    'CFO',                       'CC-FIN-001', 'Baixa'),
  (7, 'RH',                   'Diretoria de Pessoas',    'VP de Pessoas',             'CC-RH-001',  'Baixa'),
  (8, 'Jurídico/Compliance',  'Diretoria Jurídica',      'VP Jurídico',               'CC-JUR-001', 'Baixa'),
  (9, 'Marketing',            'Diretoria de Marketing',  'VP de Marketing',           'CC-MKT-001', 'Média'),
  (10,'Produtos Digitais',    'Diretoria Digital',       'VP Digital',                'CC-DIG-001', 'Média');


-- ─────────────────────────────────────────────────────────────────────────────
-- DIM_COLABORADOR (SCD Tipo 2)
-- Histórico de mudanças de cargo/área/senioridade
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS people_analytics.dim_colaborador (
    sk_colaborador      BIGINT      NOT NULL,       -- surrogate key
    nk_matricula        INT         NOT NULL,       -- natural key
    cargo               VARCHAR(80) NOT NULL,
    senioridade         VARCHAR(30) NOT NULL,
    sk_area             SMALLINT    NOT NULL,
    genero              VARCHAR(30),
    raca_cor            VARCHAR(30),
    cidade              VARCHAR(50),
    faixa_etaria        VARCHAR(20),               -- 18-24, 25-34, 35-44, 45-54, 55+
    faixa_salarial      VARCHAR(20),               -- Até 5k, 5-10k, 10-20k, 20k+
    -- SCD Tipo 2: controle de versão
    data_inicio_vigencia    DATE    NOT NULL,
    data_fim_vigencia       DATE,                  -- NULL = registro atual
    e_registro_atual        BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT pk_dim_colaborador PRIMARY KEY (sk_colaborador),
    CONSTRAINT fk_dim_colab_area FOREIGN KEY (sk_area) REFERENCES people_analytics.dim_area(sk_area)
)
DISTKEY (nk_matricula)     -- Redshift: distribui dados por matrícula
SORTKEY (nk_matricula, data_inicio_vigencia);


-- ─────────────────────────────────────────────────────────────────────────────
-- DIM_MOTIVO_SAIDA
-- Taxonomia de motivos de desligamento (RCA)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS people_analytics.dim_motivo_saida (
    sk_motivo           SMALLINT    NOT NULL,
    motivo              VARCHAR(100)NOT NULL,
    categoria_rca       VARCHAR(50) NOT NULL,
    tipo_desligamento   VARCHAR(20) NOT NULL,       -- Voluntário / Involuntário
    e_retencao_possivel BOOLEAN     NOT NULL,       -- A empresa poderia ter evitado?
    CONSTRAINT pk_dim_motivo PRIMARY KEY (sk_motivo)
);

INSERT INTO people_analytics.dim_motivo_saida VALUES
  (1, 'Proposta salarial melhor',     'Remuneração e Benefícios',      'Voluntário',   TRUE),
  (2, 'Falta de plano de carreira',   'Crescimento e Desenvolvimento', 'Voluntário',   TRUE),
  (3, 'Conflito com liderança',       'Gestão e Liderança',            'Voluntário',   TRUE),
  (4, 'Mudança de cidade',            'Flexibilidade e Trabalho',      'Voluntário',   FALSE),
  (5, 'Questões de saúde',            'Bem-Estar',                     'Voluntário',   FALSE),
  (6, 'Reestruturação',               'Clima e Cultura',               'Involuntário', FALSE),
  (7, 'Baixa performance',            'Performance',                   'Involuntário', TRUE),
  (8, 'Aposentadoria',                'Ciclo de Vida',                 'Voluntário',   FALSE),
  (9, 'Insatisfação com cultura',     'Clima e Cultura',               'Voluntário',   TRUE);


-- ─────────────────────────────────────────────────────────────────────────────
-- FCT_DESLIGAMENTO
-- Tabela fato: cada linha = 1 desligamento
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS people_analytics.fct_desligamento (
    sk_desligamento     BIGINT      NOT NULL,
    sk_colaborador      BIGINT      NOT NULL,
    sk_area             SMALLINT    NOT NULL,
    sk_motivo           SMALLINT    NOT NULL,
    sk_data_deslig      INT         NOT NULL,       -- FK dim_data
    sk_data_admissao    INT         NOT NULL,       -- FK dim_data
    -- Métricas
    tempo_casa_dias     INT,
    tempo_casa_meses    INT,
    salario_na_saida    DECIMAL(10,2),
    engajamento_ultimo  DECIMAL(4,2),
    performance_ultimo  DECIMAL(3,2),
    custo_estimado_turnover DECIMAL(12,2),          -- 1.5x salário mensal (premissa de mercado)
    -- Flags analíticas
    e_early_turnover    BOOLEAN,                   -- saiu em < 6 meses
    e_late_turnover     BOOLEAN,                   -- saiu em > 48 meses
    e_top_talent        BOOLEAN,                   -- estava no box 3x3 (9-Box)
    CONSTRAINT pk_fct_deslig PRIMARY KEY (sk_desligamento),
    CONSTRAINT fk_fct_deslig_colab  FOREIGN KEY (sk_colaborador) REFERENCES people_analytics.dim_colaborador(sk_colaborador),
    CONSTRAINT fk_fct_deslig_area   FOREIGN KEY (sk_area)        REFERENCES people_analytics.dim_area(sk_area),
    CONSTRAINT fk_fct_deslig_motivo FOREIGN KEY (sk_motivo)      REFERENCES people_analytics.dim_motivo_saida(sk_motivo),
    CONSTRAINT fk_fct_deslig_dt_d   FOREIGN KEY (sk_data_deslig) REFERENCES people_analytics.dim_data(sk_data),
    CONSTRAINT fk_fct_deslig_dt_a   FOREIGN KEY (sk_data_admissao) REFERENCES people_analytics.dim_data(sk_data)
)
DISTKEY (sk_area)
SORTKEY (sk_data_deslig, sk_area);


-- ─────────────────────────────────────────────────────────────────────────────
-- FCT_HEADCOUNT_MENSAL
-- Snapshot mensal de headcount por área/senioridade (grain: mês × área × senioridade)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS people_analytics.fct_headcount_mensal (
    sk_headcount        BIGINT      NOT NULL,
    sk_area             SMALLINT    NOT NULL,
    competencia         CHAR(7)     NOT NULL,       -- YYYY-MM
    senioridade         VARCHAR(30) NOT NULL,
    -- Métricas
    headcount           INT         NOT NULL,
    admissoes           INT         NOT NULL DEFAULT 0,
    desligamentos       INT         NOT NULL DEFAULT 0,
    desligamentos_vol   INT         NOT NULL DEFAULT 0,
    turnover_mensal_pct DECIMAL(5,2),
    engajamento_medio   DECIMAL(4,2),
    salario_medio       DECIMAL(10,2),
    performance_medio   DECIMAL(4,2),
    enps                DECIMAL(5,1),
    custo_folha         DECIMAL(14,2),
    CONSTRAINT pk_fct_hc PRIMARY KEY (sk_headcount),
    CONSTRAINT fk_fct_hc_area FOREIGN KEY (sk_area) REFERENCES people_analytics.dim_area(sk_area)
)
DISTKEY (sk_area)
SORTKEY (competencia, sk_area);


-- ─────────────────────────────────────────────────────────────────────────────
-- VIEWS ANALÍTICAS
-- Exemplos de views prontas para consumo no Power BI / Tableau / Metabase
-- ─────────────────────────────────────────────────────────────────────────────

-- Turnover LTM (últimos 12 meses) por área
CREATE OR REPLACE VIEW people_analytics.vw_turnover_ltm_area AS
SELECT
    a.area,
    a.classificacao_risco,
    SUM(f.desligamentos)                                        AS total_desligamentos,
    SUM(f.desligamentos_vol)                                    AS desligamentos_voluntarios,
    AVG(f.headcount)                                            AS headcount_medio,
    ROUND(
        SUM(f.desligamentos)::DECIMAL / NULLIF(AVG(f.headcount), 0) * 100, 1
    )                                                           AS turnover_ltm_pct,
    ROUND(
        SUM(f.desligamentos_vol)::DECIMAL / NULLIF(SUM(f.desligamentos), 0) * 100, 1
    )                                                           AS pct_voluntario
FROM people_analytics.fct_headcount_mensal f
JOIN people_analytics.dim_area a ON f.sk_area = a.sk_area
WHERE f.competencia >= TO_CHAR(DATEADD(MONTH, -12, CURRENT_DATE), 'YYYY-MM')
GROUP BY 1, 2
ORDER BY turnover_ltm_pct DESC;


-- 9-Box Grid: distribuição de colaboradores ativos
CREATE OR REPLACE VIEW people_analytics.vw_nine_box_atual AS
SELECT
    a.area,
    c.senioridade,
    CASE
        WHEN c.faixa_salarial IN ('10-20k','20k+') AND c.senioridade = 'Liderança' THEN 3
        WHEN c.senioridade = 'Sênior/Especialista'                                  THEN 2
        ELSE 1
    END AS perf_box,
    CASE
        WHEN c.faixa_etaria IN ('25-34','35-44')   THEN 3
        WHEN c.faixa_etaria IN ('18-24','45-54')   THEN 2
        ELSE 1
    END AS pot_box,
    COUNT(*)   AS headcount
FROM people_analytics.dim_colaborador c
JOIN people_analytics.dim_area a        ON c.sk_area = a.sk_area
WHERE c.e_registro_atual = TRUE
GROUP BY 1, 2, 3, 4
ORDER BY 1, perf_box DESC, pot_box DESC;


-- Custo estimado de turnover por área (LTM)
CREATE OR REPLACE VIEW people_analytics.vw_custo_turnover_ltm AS
SELECT
    a.area,
    SUM(f.custo_estimado_turnover)   AS custo_total_turnover,
    COUNT(*)                          AS total_desligamentos,
    AVG(f.custo_estimado_turnover)    AS custo_medio_por_desligamento
FROM people_analytics.fct_desligamento f
JOIN people_analytics.dim_data d        ON f.sk_data_deslig = d.sk_data
JOIN people_analytics.dim_area a        ON f.sk_area = a.sk_area
WHERE d.data_completa >= DATEADD(MONTH, -12, CURRENT_DATE)
GROUP BY 1
ORDER BY custo_total_turnover DESC;
