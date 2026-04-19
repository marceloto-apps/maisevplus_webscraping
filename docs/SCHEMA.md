# SCHEMA.md

# [SCHEMA.md](http://schema.md/) — Módulo 1: Coleta de Dados (Ingestão)

> DDL completo do banco de dados M1. Fonte de verdade para criação, seeds e indexes.
Documentos relacionados: `SPECS.md` (especificações), `TASKS.md` (implementação).
> 

---

## Índice

1. [Pré-requisitos](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
2. [Ordem de Criação](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
3. [Extensions](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
4. [Tabelas de Referência](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
5. [Tabelas de Dados](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
6. [Tabelas de Controle](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
7. [Seeds](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
8. [Indexes Consolidados](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
9. [TimescaleDB Policies](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
10. [Views Auxiliares](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
11. [Funções Utilitárias](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
12. [Queries de Verificação](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)
13. [Notas de Implementação](https://www.notion.so/SCHEMA-md-3322ae441a0680dcb035e961b0be88d4?pvs=21)

---

## 1. Pré-requisitos

| Componente | Versão Mínima |
| --- | --- |
| PostgreSQL | 16+ |
| TimescaleDB | 2.13+ |
| Extension `pgcrypto` | Incluída no PG 16 |

```sql
SELECT version();
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';
```

---

## 2. Ordem de Criação

```
1.  Extensions
2.  leagues
3.  teams
4.  team_aliases
5.  unknown_aliases
6.  seasons
7.  bookmakers
8.  api_keys
9.  matches
10. match_stats
11. odds_history  (+ hypertable)
12. lineups
13. ingestion_log
14. Seeds (leagues, bookmakers, seasons)
15. Indexes
16. Views
17. Funções e triggers
```

---

## 3. Extensions

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

---

## 4. Tabelas de Referência

### 4.1 leagues

```sql
CREATE TABLE leagues (
    league_id           SERIAL PRIMARY KEY,
    code                VARCHAR(10) UNIQUE NOT NULL,
    name                VARCHAR(100) NOT NULL,
    country             VARCHAR(50) NOT NULL,
    tier                SMALLINT NOT NULL DEFAULT 1,
    season_format       VARCHAR(10) NOT NULL,
    football_data_code  VARCHAR(10),
    football_data_type  VARCHAR(10),
    understat_name      VARCHAR(50),
    fbref_id            VARCHAR(20),
    betexplorer_path    VARCHAR(100),
    footystats_name     VARCHAR(100),
    xg_source           VARCHAR(20) DEFAULT 'fbref',
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE leagues IS '26 ligas, 14 países.';
COMMENT ON COLUMN leagues.tier IS '1=Main UK+Top5, 2=Europeias adicionais, 3=Extras';
COMMENT ON COLUMN leagues.football_data_type IS 'main=mmz4281/{season}/{code}.csv | extra=new/{code}.csv';
COMMENT ON COLUMN leagues.xg_source IS 'understat (Top5), fbref (19 ligas), footystats (SCO_L1/L2)';
```

### 4.2 teams

```sql
CREATE TABLE teams (
    team_id             SERIAL PRIMARY KEY,
    name_canonical      VARCHAR(100) NOT NULL,
    country             VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE teams IS 'Nome canônico = referência Bet365. ~580 times.';
```

### 4.3 team_aliases

```sql
CREATE TABLE team_aliases (
    alias_id            SERIAL PRIMARY KEY,
    team_id             INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    source              VARCHAR(30) NOT NULL,
    alias_name          VARCHAR(100) NOT NULL,
    UNIQUE(source, alias_name)
);

COMMENT ON TABLE team_aliases IS 'Cross-source: nome raw → team_id. ~3.480 aliases.';
```

### 4.4 unknown_aliases

```sql
CREATE TABLE unknown_aliases (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(30) NOT NULL,
    raw_name            VARCHAR(100) NOT NULL,
    league_code         VARCHAR(10),
    first_seen          TIMESTAMPTZ DEFAULT NOW(),
    resolved            BOOLEAN DEFAULT FALSE,
    resolved_team_id    INTEGER REFERENCES teams(team_id),
    resolved_at         TIMESTAMPTZ,
    UNIQUE(source, raw_name)
);

COMMENT ON TABLE unknown_aliases IS 'Aliases pendentes de revisão manual. Alerta via Telegram.';
```

### 4.5 seasons

```sql
CREATE TABLE seasons (
    season_id           SERIAL PRIMARY KEY,
    league_id           INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    label               VARCHAR(10) NOT NULL,
    start_date          DATE NOT NULL,
    end_date            DATE,
    footystats_season_id INTEGER NOT NULL,
    football_data_season VARCHAR(10),
    is_current          BOOLEAN DEFAULT FALSE,
    UNIQUE(league_id, label)
);

COMMENT ON TABLE seasons IS '~131 registros (26 ligas × 5 temporadas + BRA_SA com 6).';
```

### 4.6 bookmakers

```sql
CREATE TABLE bookmakers (
    bookmaker_id        SERIAL PRIMARY KEY,
    name                VARCHAR(50) UNIQUE NOT NULL,
    display_name        VARCHAR(50) NOT NULL,
    type                VARCHAR(20) NOT NULL,
    clv_priority        SMALLINT,
    is_active           BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE bookmakers IS '13 casas. CLV: 1=Pinnacle, 2=Betfair, 3=Bet365.';
```

### 4.7 api_keys

```sql
CREATE TABLE api_keys (
    key_id              SERIAL PRIMARY KEY,
    service             VARCHAR(30) NOT NULL,
    key_label           VARCHAR(50) NOT NULL,
    key_value           VARCHAR(200) NOT NULL,
    email               VARCHAR(100),
    usage_today         INTEGER DEFAULT 0,
    usage_month         INTEGER DEFAULT 0,
    limit_daily         INTEGER,
    limit_monthly       INTEGER,
    is_active           BOOLEAN DEFAULT TRUE,
    last_used_at        TIMESTAMPTZ,
    last_reset_at       TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE api_keys IS '7 keys API-Football (100/dia) + 5 keys Odds API (500/mês).';
```

---

## 5. Tabelas de Dados

### 5.1 matches

```sql
CREATE TABLE matches (
    match_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id           INTEGER NOT NULL REFERENCES seasons(season_id),
    league_id           INTEGER NOT NULL REFERENCES leagues(league_id),
    home_team_id        INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id        INTEGER NOT NULL REFERENCES teams(team_id),
    kickoff             TIMESTAMPTZ NOT NULL,
    matchday            SMALLINT,

    ft_home             SMALLINT,
    ft_away             SMALLINT,
    ht_home             SMALLINT,
    ht_away             SMALLINT,
    goals_home_minutes  JSONB,
    goals_away_minutes  JSONB,

    status              VARCHAR(20) DEFAULT 'scheduled',

    betexplorer_id       VARCHAR(30),
    football_data_id    VARCHAR(30),
    fbref_id            VARCHAR(30),
    understat_id        VARCHAR(30),
    footystats_id       INTEGER,
    odds_api_id         VARCHAR(50),
    api_football_id     INTEGER,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(league_id, home_team_id, away_team_id, kickoff::date)
);

COMMENT ON TABLE matches IS '~57.500 rows backfill + ~11.500/temporada.';
COMMENT ON COLUMN matches.goals_home_minutes IS '[23, 67, 89]. NULL se sem gols.';
COMMENT ON COLUMN matches.status IS 'scheduled | live | finished | postponed | cancelled';
```

### 5.2 match_stats

```sql
CREATE TABLE match_stats (
    stat_id                 SERIAL PRIMARY KEY,
    match_id                UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,

    xg_home                 NUMERIC(5,2),
    xg_away                 NUMERIC(5,2),
    xga_home                NUMERIC(5,2),
    xga_away                NUMERIC(5,2),

    shots_home              SMALLINT,
    shots_away              SMALLINT,
    shots_on_target_home    SMALLINT,
    shots_on_target_away    SMALLINT,
    shots_off_target_home   SMALLINT,
    shots_off_target_away   SMALLINT,

    possession_home         NUMERIC(4,1),
    possession_away         NUMERIC(4,1),

    corners_home_ft         SMALLINT,
    corners_away_ft         SMALLINT,
    total_corners_ft        SMALLINT GENERATED ALWAYS AS (corners_home_ft + corners_away_ft) STORED,

    corners_home_ht         SMALLINT,
    corners_away_ht         SMALLINT,
    total_corners_ht        SMALLINT GENERATED ALWAYS AS (
        CASE WHEN corners_home_ht IS NOT NULL AND corners_away_ht IS NOT NULL
             THEN corners_home_ht + corners_away_ht
             ELSE NULL END
    ) STORED,

    yellow_cards_home_ft    SMALLINT,
    yellow_cards_away_ft    SMALLINT,
    red_cards_home_ft       SMALLINT,
    red_cards_away_ft       SMALLINT,

    cards_home_ht           SMALLINT,
    cards_away_ht           SMALLINT,

    source                  VARCHAR(20) NOT NULL,
    collected_at            TIMESTAMPTZ DEFAULT NOW(),
    raw_json                JSONB,

    UNIQUE(match_id, source)
);

COMMENT ON TABLE match_stats IS 'Múltiplas fontes por jogo (footystats + understat/fbref). FK simples para matches.';
```

### 5.3 odds_history (TimescaleDB hypertable)

```sql
CREATE TABLE odds_history (
    time                TIMESTAMPTZ NOT NULL,
    match_id            UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    bookmaker_id        INTEGER NOT NULL REFERENCES bookmakers(bookmaker_id),
    market_type         VARCHAR(10) NOT NULL,
    line                NUMERIC(5,2),
    period              VARCHAR(5) DEFAULT 'ft',

    odds_1              NUMERIC(8,4),
    odds_x              NUMERIC(8,4),
    odds_2              NUMERIC(8,4),

    overround           NUMERIC(6,4),
    is_opening          BOOLEAN DEFAULT FALSE,
    is_closing          BOOLEAN DEFAULT FALSE,

    source              VARCHAR(20) NOT NULL,
    collect_job_id      VARCHAR(50),
    content_hash        CHAR(64) NOT NULL
);

SELECT create_hypertable('odds_history', 'time', chunk_time_interval => INTERVAL '1 month');

COMMENT ON TABLE odds_history IS 'Hypertable TimescaleDB, chunks mensais. >300k rows backfill.';
COMMENT ON COLUMN odds_history.content_hash IS 'SHA-256 para dedup. Igual ao último → skip.';
COMMENT ON COLUMN odds_history.is_closing IS 'Marcado por mark_closing_odds() no job T+2h30.';
```

### 5.4 lineups

```sql
CREATE TABLE lineups (
    lineup_id           SERIAL PRIMARY KEY,
    match_id            UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    team_id             INTEGER NOT NULL REFERENCES teams(team_id),
    formation           VARCHAR(10),
    players_json        JSONB NOT NULL,
    source              VARCHAR(20) NOT NULL,
    collected_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(match_id, team_id, source)
);

COMMENT ON TABLE lineups IS 'Escalações via API-Football (T-60min).';
```

---

## 6. Tabelas de Controle

### 6.1 ingestion_log

```sql
CREATE TABLE ingestion_log (
    log_id              SERIAL PRIMARY KEY,
    job_id              VARCHAR(50) NOT NULL,
    source              VARCHAR(20) NOT NULL,
    job_type            VARCHAR(30) NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    status              VARCHAR(15) NOT NULL,
    records_collected   INTEGER DEFAULT 0,
    records_new         INTEGER DEFAULT 0,
    records_skipped     INTEGER DEFAULT 0,
    error_message       TEXT,
    metadata_json       JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ingestion_log IS 'Log de jobs. Critério de aceite: sem failed por 48h.';
```

### 6.2 fc_complementary_queue

```sql
CREATE TABLE IF NOT EXISTS fc_complementary_queue (
    match_id UUID PRIMARY KEY,
    flashscore_id VARCHAR(50),
    kickoff TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'pending',
    attempts INT DEFAULT 0,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE fc_complementary_queue IS 'Fila idempotente e apartada para suprir buracos de AH/OU no Flashscore. Injetada por payload JSON estático para segurança.';
```

---

## 7. Seeds

> [!WARNING]
> **Nota de Implementação (M2):** O seed inicial para desenvolvimento local mudou da abordagem via SQL (antigo `005_seeds.sql`) para o script Node.js idempotente `backend/scripts/seed_dev.js`. Este script impede execuções e sobrescritas acidentais em produção, inserindo usuários, bancas mocks e chaves criptográficas de forma segura. O backup das queries puras de mock M1 foi mantido em `full_schema.sql.bak`. As queries SQL estáticas abaixo servem apenas como documentação de referência das entidades originais inseridas.
> 

### 7.1 Bookmakers

```sql
INSERT INTO bookmakers (name, display_name, type, clv_priority) VALUES
    ('pinnacle',     'Pinnacle',         'sharp',      1),
    ('betfair_ex',   'Betfair Exchange', 'exchange',   2),
    ('bet365',       'Bet365',           'retail',     3),
    ('1xbet',        '1xBet',            'retail',     NULL),
    ('betano',       'Betano',           'br_retail',  NULL),
    ('sportingbet',  'Sportingbet',      'br_retail',  NULL),
    ('superbet',     'Superbet',         'br_retail',  NULL),
    ('betnacional',  'BetNacional',      'br_retail',  NULL),
    ('estrela_bet',  'EstrelaBet',       'br_retail',  NULL),
    ('kto',          'KTO',              'br_retail',  NULL),
    ('7k',           '7K',               'br_retail',  NULL),
    ('f12',          'F12',              'br_retail',  NULL),
    ('multibet',     'Multibet',         'br_retail',  NULL);
```

### 7.2 Leagues

```sql
-- TIER 1 (17 ligas)
INSERT INTO leagues (code, name, country, tier, season_format, football_data_code, football_data_type, understat_name, fbref_id, xg_source) VALUES
    ('ENG_PL', 'Premier League',    'England',  1, 'aug_may', 'E0',  'main', 'EPL',        '9',  'understat'),
    ('ENG_CH', 'Championship',      'England',  1, 'aug_may', 'E1',  'main', NULL,         '10', 'fbref'),
    ('ENG_L1', 'League One',        'England',  1, 'aug_may', 'E2',  'main', NULL,         '15', 'fbref'),
    ('ENG_L2', 'League Two',        'England',  1, 'aug_may', 'E3',  'main', NULL,         '16', 'fbref'),
    ('ENG_NL', 'National League',   'England',  1, 'aug_may', 'EC',  'main', NULL,         '34', 'fbref'),
    ('SCO_PL', 'Premiership',       'Scotland', 1, 'aug_may', 'SC0', 'main', NULL,         '40', 'fbref'),
    ('SCO_CH', 'Championship',      'Scotland', 1, 'aug_may', 'SC1', 'main', NULL,         '72', 'fbref'),
    ('SCO_L1', 'League One',        'Scotland', 1, 'aug_may', 'SC2', 'main', NULL,         NULL, 'footystats'),
    ('SCO_L2', 'League Two',        'Scotland', 1, 'aug_may', 'SC3', 'main', NULL,         NULL, 'footystats'),
    ('GER_BL', 'Bundesliga',        'Germany',  1, 'aug_may', 'D1',  'main', 'Bundesliga', '20', 'understat'),
    ('GER_B2', '2. Bundesliga',     'Germany',  1, 'aug_may', 'D2',  'main', NULL,         '33', 'fbref'),
    ('ITA_SA', 'Serie A',           'Italy',    1, 'aug_may', 'I1',  'main', 'Serie_A',    '11', 'understat'),
    ('ITA_SB', 'Serie B',           'Italy',    1, 'aug_may', 'I2',  'main', NULL,         '18', 'fbref'),
    ('ESP_PD', 'La Liga',           'Spain',    1, 'aug_may', 'SP1', 'main', 'La_Liga',    '12', 'understat'),
    ('ESP_SD', 'La Liga 2',         'Spain',    1, 'aug_may', 'SP2', 'main', NULL,         '17', 'fbref'),
    ('FRA_L1', 'Ligue 1',          'France',   1, 'aug_may', 'F1',  'main', 'Ligue_1',    '13', 'understat'),
    ('FRA_L2', 'Ligue 2',          'France',   1, 'aug_may', 'F2',  'main', NULL,         '60', 'fbref');

-- TIER 2 (5 ligas)
INSERT INTO leagues (code, name, country, tier, season_format, football_data_code, football_data_type, understat_name, fbref_id, xg_source) VALUES
    ('NED_ED', 'Eredivisie',     'Netherlands', 2, 'aug_may', 'N1', 'main', NULL, '23', 'fbref'),
    ('BEL_PL', 'Pro League',     'Belgium',     2, 'aug_may', 'B1', 'main', NULL, '37', 'fbref'),
    ('POR_PL', 'Primeira Liga',  'Portugal',    2, 'aug_may', 'P1', 'main', NULL, '32', 'fbref'),
    ('TUR_SL', 'Süper Lig',     'Turkey',      2, 'aug_may', 'T1', 'main', NULL, '26', 'fbref'),
    ('GRE_SL', 'Super League',   'Greece',      2, 'aug_may', 'G1', 'main', NULL, '27', 'fbref');

-- TIER 3 (4 ligas)
INSERT INTO leagues (code, name, country, tier, season_format, football_data_code, football_data_type, understat_name, fbref_id, xg_source) VALUES
    ('BRA_SA', 'Brasileirão Série A', 'Brazil',      3, 'apr_dec', 'BRA', 'extra', NULL, '24', 'fbref'),
    ('MEX_LM', 'Liga MX',            'Mexico',      3, 'jul_may', 'MEX', 'extra', NULL, '31', 'fbref'),
    ('AUT_BL', 'Bundesliga',         'Austria',     3, 'jul_may', 'AUT', 'extra', NULL, '56', 'fbref'),
    ('SWI_SL', 'Super League',       'Switzerland', 3, 'jul_may', 'SWZ', 'extra', NULL, '57', 'fbref');
```

### 7.3 Seasons

```sql
-- ============================================================
-- England
-- ============================================================
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='ENG_PL'), '2021/2022', '2021-08-13', '2022-05-22', 6135,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_PL'), '2022/2023', '2022-08-05', '2023-05-28', 7704,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_PL'), '2023/2024', '2023-08-11', '2024-05-19', 9660,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_PL'), '2024/2025', '2024-08-16', '2025-05-25', 12325, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_PL'), '2025/2026', '2025-08-16', NULL,         15050, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='ENG_CH'), '2021/2022', '2021-08-07', '2022-05-29', 6089,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_CH'), '2022/2023', '2022-07-29', '2023-05-27', 7593,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_CH'), '2023/2024', '2023-08-04', '2024-05-04', 9663,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_CH'), '2024/2025', '2024-08-09', '2025-05-03', 12451, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_CH'), '2025/2026', '2025-08-09', NULL,         14930, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='ENG_L1'), '2021/2022', '2021-08-07', '2022-04-30', 6017,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L1'), '2022/2023', '2022-07-30', '2023-05-07', 7570,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L1'), '2023/2024', '2023-08-05', '2024-04-27', 9582,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L1'), '2024/2025', '2024-08-10', '2025-04-26', 12446, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L1'), '2025/2026', '2025-08-09', NULL,         14934, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='ENG_L2'), '2021/2022', '2021-08-07', '2022-04-30', 6015,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L2'), '2022/2023', '2022-07-30', '2023-05-06', 7574,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L2'), '2023/2024', '2023-08-05', '2024-04-27', 9581,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L2'), '2024/2025', '2024-08-10', '2025-04-26', 12422, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_L2'), '2025/2026', '2025-08-09', NULL,         14935, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='ENG_NL'), '2021/2022', '2021-08-21', '2022-06-05', 6088,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_NL'), '2022/2023', '2022-08-06', '2023-06-11', 7729,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_NL'), '2023/2024', '2023-08-05', '2024-06-02', 9700,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_NL'), '2024/2025', '2024-08-10', '2025-06-01', 12622, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ENG_NL'), '2025/2026', '2025-08-09', NULL,         15657, '2526', TRUE);

-- ============================================================
-- Scotland
-- ============================================================
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='SCO_PL'), '2021/2022', '2021-07-24', '2022-05-25', 5992,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_PL'), '2022/2023', '2022-07-30', '2023-05-28', 7494,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_PL'), '2023/2024', '2023-08-05', '2024-05-19', 9636,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_PL'), '2024/2025', '2024-08-03', '2025-05-25', 12455, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_PL'), '2025/2026', '2025-08-02', NULL,         15000, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='SCO_CH'), '2021/2022', '2021-07-31', '2022-05-06', 5991,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_CH'), '2022/2023', '2022-07-29', '2023-05-05', 7498,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_CH'), '2023/2024', '2023-08-04', '2024-05-03', 9637,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_CH'), '2024/2025', '2024-08-03', '2025-05-02', 12456, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_CH'), '2025/2026', '2025-08-02', NULL,         15061, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='SCO_L1'), '2021/2022', '2021-07-31', '2022-04-30', 5976,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L1'), '2022/2023', '2022-07-30', '2023-04-29', 7505,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L1'), '2023/2024', '2023-08-05', '2024-04-27', 9639,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L1'), '2024/2025', '2024-08-03', '2025-04-26', 12474, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L1'), '2025/2026', '2025-08-02', NULL,         14943, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='SCO_L2'), '2021/2022', '2021-07-31', '2022-04-30', 5974,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L2'), '2022/2023', '2022-07-30', '2023-04-29', 7506,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L2'), '2023/2024', '2023-08-05', '2024-04-27', 9638,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L2'), '2024/2025', '2024-08-03', '2025-04-26', 12453, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='SCO_L2'), '2025/2026', '2025-08-02', NULL,         15209, '2526', TRUE);

-- ============================================================
-- Germany
-- ============================================================
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='GER_BL'), '2021/2022', '2021-08-13', '2022-05-14', 6192,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_BL'), '2022/2023', '2022-08-05', '2023-05-27', 7664,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_BL'), '2023/2024', '2023-08-18', '2024-05-18', 9655,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_BL'), '2024/2025', '2024-08-23', '2025-05-17', 12529, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_BL'), '2025/2026', '2025-08-22', NULL,         14968, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='GER_B2'), '2021/2022', '2021-07-23', '2022-05-15', 6020,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_B2'), '2022/2023', '2022-07-15', '2023-05-28', 7499,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_B2'), '2023/2024', '2023-07-28', '2024-05-19', 9656,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_B2'), '2024/2025', '2024-08-02', '2025-05-18', 12528, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GER_B2'), '2025/2026', '2025-08-01', NULL,         14931, '2526', TRUE);

-- ============================================================
-- Italy
-- ============================================================
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='ITA_SA'), '2021/2022', '2021-08-21', '2022-05-22', 6198,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SA'), '2022/2023', '2022-08-13', '2023-06-04', 7608,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SA'), '2023/2024', '2023-08-19', '2024-05-26', 9697,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SA'), '2024/2025', '2024-08-17', '2025-05-25', 12530, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SA'), '2025/2026', '2025-08-16', NULL,         15068, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='ITA_SB'), '2021/2022', '2021-08-20', '2022-05-29', 6205,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SB'), '2022/2023', '2022-08-12', '2023-06-09', 7864,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SB'), '2023/2024', '2023-08-18', '2024-05-24', 9808,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SB'), '2024/2025', '2024-08-16', '2025-05-23', 12621, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ITA_SB'), '2025/2026', '2025-08-15', NULL,         15632, '2526', TRUE);

-- ============================================================
-- Spain
-- ============================================================
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='ESP_PD'), '2021/2022', '2021-08-13', '2022-05-22', 6211,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_PD'), '2022/2023', '2022-08-12', '2023-06-04', 7665,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_PD'), '2023/2024', '2023-08-11', '2024-05-26', 9665,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_PD'), '2024/2025', '2024-08-15', '2025-05-25', 12316, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_PD'), '2025/2026', '2025-08-15', NULL,         14956, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='ESP_SD'), '2021/2022', '2021-08-14', '2022-05-29', 6120,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_SD'), '2022/2023', '2022-08-12', '2023-06-10', 7592,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_SD'), '2023/2024', '2023-08-17', '2024-06-02', 9675,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_SD'), '2024/2025', '2024-08-16', '2025-05-31', 12467, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='ESP_SD'), '2025/2026', '2025-08-15', NULL,         15066, '2526', TRUE);

-- ============================================================
-- France
-- ============================================================
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='FRA_L1'), '2021/2022', '2021-08-06', '2022-05-21', 6019,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L1'), '2022/2023', '2022-08-05', '2023-06-03', 7500,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L1'), '2023/2024', '2023-08-11', '2024-05-19', 9674,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L1'), '2024/2025', '2024-08-16', '2025-05-18', 12337, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L1'), '2025/2026', '2025-08-08', NULL,         14932, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='FRA_L2'), '2021/2022', '2021-07-24', '2022-05-21', 6018,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L2'), '2022/2023', '2022-07-30', '2023-06-03', 7501,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L2'), '2023/2024', '2023-08-04', '2024-05-18', 9621,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L2'), '2024/2025', '2024-08-16', '2025-05-17', 12338, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='FRA_L2'), '2025/2026', '2025-08-08', NULL,         14954, '2526', TRUE);

-- ============================================================
-- Tier 2
-- ============================================================
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='NED_ED'), '2021/2022', '2021-08-13', '2022-05-15', 5951,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='NED_ED'), '2022/2023', '2022-08-05', '2023-05-28', 7482,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='NED_ED'), '2023/2024', '2023-08-11', '2024-05-19', 9653,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='NED_ED'), '2024/2025', '2024-08-09', '2025-05-18', 12322, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='NED_ED'), '2025/2026', '2025-08-08', NULL,         14936, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='BEL_PL'), '2021/2022', '2021-07-23', '2022-05-22', 6079,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='BEL_PL'), '2022/2023', '2022-07-22', '2023-06-04', 7544,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='BEL_PL'), '2023/2024', '2023-07-21', '2024-05-26', 9577,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='BEL_PL'), '2024/2025', '2024-07-26', '2025-05-25', 12137, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='BEL_PL'), '2025/2026', '2025-07-25', NULL,         14937, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='POR_PL'), '2021/2022', '2021-08-06', '2022-05-15', 6117,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='POR_PL'), '2022/2023', '2022-08-05', '2023-05-28', 7731,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='POR_PL'), '2023/2024', '2023-08-11', '2024-05-19', 9984,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='POR_PL'), '2024/2025', '2024-08-09', '2025-05-18', 12931, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='POR_PL'), '2025/2026', '2025-08-08', NULL,         15115, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='TUR_SL'), '2021/2022', '2021-08-16', '2022-05-21', 6125,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='TUR_SL'), '2022/2023', '2022-08-05', '2023-05-28', 7768,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='TUR_SL'), '2023/2024', '2023-08-11', '2024-05-26', 9913,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='TUR_SL'), '2024/2025', '2024-08-09', '2025-05-25', 12641, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='TUR_SL'), '2025/2026', '2025-08-08', NULL,         14972, '2526', TRUE),

    ((SELECT league_id FROM leagues WHERE code='GRE_SL'), '2021/2022', '2021-08-21', '2022-05-15', 6282,  '2122', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GRE_SL'), '2022/2023', '2022-08-19', '2023-05-21', 7954,  '2223', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GRE_SL'), '2023/2024', '2023-08-25', '2024-05-12', 9889,  '2324', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GRE_SL'), '2024/2025', '2024-08-17', '2025-05-11', 12734, '2425', FALSE),
    ((SELECT league_id FROM leagues WHERE code='GRE_SL'), '2025/2026', '2025-08-16', NULL,         15163, '2526', TRUE);

-- ============================================================
-- Tier 3: Extras
-- ============================================================

-- Brasileirão (6 temporadas, formato por ano)
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='BRA_SA'), '2021', '2021-05-29', '2021-12-09', 5713,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='BRA_SA'), '2022', '2022-04-09', '2022-11-13', 7097,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='BRA_SA'), '2023', '2023-04-15', '2023-12-06', 9035,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='BRA_SA'), '2024', '2024-04-13', '2024-12-08', 11321, NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='BRA_SA'), '2025', '2025-03-29', NULL,         14231, NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='BRA_SA'), '2026', '2026-04-04', NULL,         16544, NULL, TRUE);

-- Liga MX
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='MEX_LM'), '2021/2022', '2021-07-22', '2022-05-29', 6038,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='MEX_LM'), '2022/2023', '2022-07-01', '2023-05-28', 7425,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='MEX_LM'), '2023/2024', '2023-07-01', '2024-05-26', 9525,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='MEX_LM'), '2024/2025', '2024-07-05', '2025-05-25', 12136, NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='MEX_LM'), '2025/2026', '2025-07-04', NULL,         15234, NULL, TRUE);

-- Bundesliga Áustria
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='AUT_BL'), '2021/2022', '2021-07-23', '2022-05-22', 6008,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='AUT_BL'), '2022/2023', '2022-07-22', '2023-05-28', 7890,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='AUT_BL'), '2023/2024', '2023-07-28', '2024-05-26', 9954,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='AUT_BL'), '2024/2025', '2024-07-26', '2025-05-25', 12472, NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='AUT_BL'), '2025/2026', '2025-07-25', NULL,         14923, NULL, TRUE);

-- Super League Suíça
INSERT INTO seasons (league_id, label, start_date, end_date, footystats_season_id, football_data_season, is_current) VALUES
    ((SELECT league_id FROM leagues WHERE code='SWI_SL'), '2021/2022', '2021-07-24', '2022-05-29', 6044,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='SWI_SL'), '2022/2023', '2022-07-16', '2023-06-04', 7504,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='SWI_SL'), '2023/2024', '2023-07-22', '2024-05-25', 9580,  NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='SWI_SL'), '2024/2025', '2024-07-20', '2025-05-25', 12326, NULL, FALSE),
    ((SELECT league_id FROM leagues WHERE code='SWI_SL'), '2025/2026', '2025-07-19', NULL,         15047, NULL, TRUE);
```

---

## 8. Indexes Consolidados

```sql
-- TEAM ALIASES
CREATE INDEX idx_team_aliases_lookup ON team_aliases(source, alias_name);

-- UNKNOWN ALIASES
CREATE INDEX idx_unknown_aliases_pending ON unknown_aliases(resolved, source) WHERE resolved = FALSE;

-- SEASONS
CREATE INDEX idx_seasons_league ON seasons(league_id);
CREATE INDEX idx_seasons_current ON seasons(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_seasons_footystats ON seasons(footystats_season_id);

-- API KEYS
CREATE INDEX idx_api_keys_service ON api_keys(service, is_active);

-- MATCHES
CREATE INDEX idx_matches_kickoff ON matches(kickoff);
CREATE INDEX idx_matches_league_status ON matches(league_id, status);
CREATE INDEX idx_matches_season ON matches(season_id);
CREATE INDEX idx_matches_footystats ON matches(footystats_id) WHERE footystats_id IS NOT NULL;
CREATE INDEX idx_matches_betexplorer ON matches(betexplorer_id) WHERE betexplorer_id IS NOT NULL;
CREATE INDEX idx_matches_status_kickoff ON matches(status, kickoff) WHERE status = 'scheduled';

-- MATCH STATS
CREATE INDEX idx_match_stats_match ON match_stats(match_id);
CREATE INDEX idx_match_stats_source ON match_stats(source);

-- ODDS HISTORY (hypertable)
CREATE UNIQUE INDEX idx_odds_dedup
    ON odds_history(match_id, bookmaker_id, market_type, COALESCE(line, 0), period, content_hash, time);
CREATE INDEX idx_odds_match_market
    ON odds_history(match_id, market_type, bookmaker_id, time DESC);
CREATE INDEX idx_odds_closing
    ON odds_history(match_id, bookmaker_id, market_type) WHERE is_closing = TRUE;
CREATE INDEX idx_odds_source_job
    ON odds_history(source, collect_job_id);

-- LINEUPS
CREATE INDEX idx_lineups_match ON lineups(match_id);

-- INGESTION LOG
CREATE INDEX idx_ingestion_status ON ingestion_log(status, started_at DESC);
CREATE INDEX idx_ingestion_source ON ingestion_log(source, job_type, started_at DESC);
CREATE INDEX idx_ingestion_job_id ON ingestion_log(job_id);
```

---

## 9. TimescaleDB Policies

### 9.1 Compression (pós-MVP)

```sql
-- ⚠️ NÃO executar no MVP. Aplicar quando sistema estável.

ALTER TABLE odds_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'match_id, bookmaker_id, market_type',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('odds_history', INTERVAL '3 months');
```

### 9.2 Retention (pós-MVP)

```sql
-- ⚠️ NÃO ativar. Manter todo o histórico.
-- SELECT add_retention_policy('odds_history', INTERVAL '7 years');
```

### 9.3 Verificação de Chunks

```sql
SELECT
    hypertable_name,
    chunk_name,
    range_start,
    range_end,
    pg_size_pretty(total_bytes) AS size
FROM timescaledb_information.chunks
WHERE hypertable_name = 'odds_history'
ORDER BY range_start;
```

---

## 10. Views Auxiliares

### 10.1 Jogos de Hoje

```sql
CREATE OR REPLACE VIEW v_today_matches AS
SELECT
    m.match_id,
    m.kickoff,
    m.status,
    m.league_id,
    l.code AS league_code,
    l.tier,
    th.name_canonical AS home_team,
    ta.name_canonical AS away_team,
    m.betexplorer_id,
    m.footystats_id,
    m.api_football_id
FROM matches m
JOIN leagues l ON l.league_id = m.league_id
JOIN teams th ON th.team_id = m.home_team_id
JOIN teams ta ON ta.team_id = m.away_team_id
WHERE m.kickoff::date = CURRENT_DATE
  AND m.status IN ('scheduled', 'live')
ORDER BY l.tier, m.kickoff;
```

### 10.2 Closing Odds (CLV)

```sql
CREATE OR REPLACE VIEW v_closing_odds AS
SELECT
    oh.match_id,
    m.kickoff,
    m.league_id,
    oh.bookmaker_id,
    b.name AS bookmaker_name,
    b.clv_priority,
    oh.market_type,
    oh.line,
    oh.period,
    oh.odds_1,
    oh.odds_x,
    oh.odds_2,
    oh.overround,
    oh.time AS closing_time
FROM odds_history oh
JOIN matches m ON m.match_id = oh.match_id
JOIN bookmakers b ON b.bookmaker_id = oh.bookmaker_id
WHERE oh.is_closing = TRUE
ORDER BY oh.match_id, b.clv_priority NULLS LAST;
```

### 10.3 Match Full — xG por Fonte

```sql
CREATE OR REPLACE VIEW v_match_full AS
SELECT
    m.match_id,
    m.season_id,
    m.kickoff,
    m.status,
    l.code AS league_code,
    l.name AS league_name,
    l.tier,
    l.xg_source AS xg_primary_source,
    s.label AS season_label,
    th.name_canonical AS home_team,
    ta.name_canonical AS away_team,
    m.ft_home,
    m.ft_away,
    m.ht_home,
    m.ht_away,
    m.goals_home_minutes,
    m.goals_away_minutes,

    -- xG por fonte
    fs.xg_home AS xg_home_footystats,
    fs.xg_away AS xg_away_footystats,
    us.xg_home AS xg_home_understat,
    us.xg_away AS xg_away_understat,
    fb.xg_home AS xg_home_fbref,
    fb.xg_away AS xg_away_fbref,

    -- xG best: prioridade da liga → fallback cascata
    COALESCE(
        CASE l.xg_source
            WHEN 'understat'  THEN us.xg_home
            WHEN 'fbref'      THEN fb.xg_home
            WHEN 'footystats' THEN fs.xg_home
        END,
        us.xg_home, fb.xg_home, fs.xg_home
    ) AS xg_home_best,
    COALESCE(
        CASE l.xg_source
            WHEN 'understat'  THEN us.xg_away
            WHEN 'fbref'      THEN fb.xg_away
            WHEN 'footystats' THEN fs.xg_away
        END,
        us.xg_away, fb.xg_away, fs.xg_away
    ) AS xg_away_best,

    -- Stats (footystats primário, fbref fallback)
    COALESCE(fs.shots_home, fb.shots_home)                     AS shots_home,
    COALESCE(fs.shots_away, fb.shots_away)                     AS shots_away,
    COALESCE(fs.shots_on_target_home, fb.shots_on_target_home) AS shots_on_target_home,
    COALESCE(fs.shots_on_target_away, fb.shots_on_target_away) AS shots_on_target_away,
    COALESCE(fs.possession_home, fb.possession_home)           AS possession_home,
    COALESCE(fs.possession_away, fb.possession_away)           AS possession_away,
    fs.corners_home_ft,
    fs.corners_away_ft,
    fs.total_corners_ft,
    fs.corners_home_ht,
    fs.corners_away_ht,
    fs.total_corners_ht,
    fs.yellow_cards_home_ft,
    fs.yellow_cards_away_ft,
    fs.red_cards_home_ft,
    fs.red_cards_away_ft,
    fs.cards_home_ht,
    fs.cards_away_ht

FROM matches m
JOIN leagues l  ON l.league_id = m.league_id
JOIN seasons s  ON s.season_id = m.season_id
JOIN teams th   ON th.team_id  = m.home_team_id
JOIN teams ta   ON ta.team_id  = m.away_team_id
LEFT JOIN match_stats fs ON fs.match_id = m.match_id AND fs.source = 'footystats'
LEFT JOIN match_stats us ON us.match_id = m.match_id AND us.source = 'understat'
LEFT JOIN match_stats fb ON fb.match_id = m.match_id AND fb.source = 'fbref';

COMMENT ON VIEW v_match_full IS 'xG de todas as fontes + xg_*_best resolvido por prioridade da liga. Interface principal para M2.';
```

### 10.4 Saúde da Ingestão

```sql
CREATE OR REPLACE VIEW v_ingestion_health AS
SELECT
    source,
    job_type,
    COUNT(*) FILTER (WHERE status = 'success')  AS success_count,
    COUNT(*) FILTER (WHERE status = 'partial')  AS partial_count,
    COUNT(*) FILTER (WHERE status = 'failed')   AS failed_count,
    MAX(finished_at) AS last_success_at,
    MAX(finished_at) FILTER (WHERE status = 'failed') AS last_failure_at,
    ROUND(AVG(records_new) FILTER (WHERE status IN ('success', 'partial'))) AS avg_records_new
FROM ingestion_log
WHERE started_at > NOW() - INTERVAL '48 hours'
GROUP BY source, job_type
ORDER BY source, job_type;
```

### 10.5 Uso de API Keys

```sql
CREATE OR REPLACE VIEW v_api_keys_usage AS
SELECT
    service,
    key_label,
    usage_today,
    limit_daily,
    CASE WHEN limit_daily IS NOT NULL
        THEN ROUND(100.0 * usage_today / limit_daily, 1)
        ELSE NULL
    END AS pct_daily_used,
    usage_month,
    limit_monthly,
    CASE WHEN limit_monthly IS NOT NULL
        THEN ROUND(100.0 * usage_month / limit_monthly, 1)
        ELSE NULL
    END AS pct_monthly_used,
    is_active,
    last_used_at
FROM api_keys
ORDER BY service, key_label;
```

---

## 11. Funções Utilitárias

### 11.1 Trigger updated_at

```sql
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_matches_updated_at
    BEFORE UPDATE ON matches
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_timestamp();
```

### 11.2 Reset Diário de Keys

```sql
CREATE OR REPLACE FUNCTION fn_reset_daily_api_keys()
RETURNS void AS $$
BEGIN
    UPDATE api_keys SET usage_today = 0, last_reset_at = NOW();
END;
$$ LANGUAGE plpgsql;
```

### 11.3 Reset Mensal de Keys

```sql
CREATE OR REPLACE FUNCTION fn_reset_monthly_api_keys()
RETURNS void AS $$
BEGIN
    UPDATE api_keys SET usage_month = 0;
END;
$$ LANGUAGE plpgsql;
```

---

## 12. Queries de Verificação

### 12.1 Dashboard de Aceite

```sql
SELECT '1. matches_total' AS check, COUNT(*) AS value,
    CASE WHEN COUNT(*) > 50000 THEN '✅' ELSE '❌' END AS result
FROM matches
UNION ALL
SELECT '2. stats_with_xg', COUNT(*),
    CASE WHEN COUNT(*) > 45000 THEN '✅' ELSE '❌' END
FROM match_stats WHERE xg_home IS NOT NULL
UNION ALL
SELECT '3. odds_total', COUNT(*),
    CASE WHEN COUNT(*) > 300000 THEN '✅' ELSE '❌' END
FROM odds_history
UNION ALL
SELECT '4. odds_duplicates', COUNT(*),
    CASE WHEN COUNT(*) = 0 THEN '✅' ELSE '❌' END
FROM (
    SELECT match_id, bookmaker_id, market_type, COALESCE(line, 0), period, content_hash, time
    FROM odds_history
    GROUP BY 1,2,3,4,5,6,7 HAVING COUNT(*) > 1
) d
UNION ALL
SELECT '5. unmapped_aliases', COUNT(*),
    CASE WHEN COUNT(*) = 0 THEN '✅' ELSE '⚠️' END
FROM unknown_aliases WHERE resolved = FALSE
UNION ALL
SELECT '6. failed_jobs_48h', COUNT(*),
    CASE WHEN COUNT(*) = 0 THEN '✅' ELSE '❌' END
FROM ingestion_log WHERE status = 'failed' AND started_at > NOW() - INTERVAL '48 hours'
ORDER BY 1;
```

### 12.2 Cobertura por Liga

```sql
SELECT
    l.code, l.tier,
    COUNT(m.match_id) AS matches,
    COUNT(ms.stat_id) AS stats,
    COUNT(ms.stat_id) FILTER (WHERE ms.xg_home IS NOT NULL) AS with_xg,
    ROUND(100.0 * COUNT(ms.stat_id) / NULLIF(COUNT(m.match_id), 0), 1) AS stats_pct
FROM leagues l
LEFT JOIN matches m ON m.league_id = l.league_id
LEFT JOIN match_stats ms ON ms.match_id = m.match_id
GROUP BY l.code, l.tier
ORDER BY l.tier, l.code;
```

### 12.3 Odds por Casa

```sql
SELECT
    b.display_name, b.type,
    COUNT(*) AS total_odds,
    COUNT(DISTINCT oh.match_id) AS matches_covered
FROM odds_history oh
JOIN bookmakers b ON b.bookmaker_id = oh.bookmaker_id
GROUP BY b.display_name, b.type
ORDER BY total_odds DESC;
```

### 12.4 Verificação de Seasons

```sql
SELECT
    l.code, s.label, s.footystats_season_id, s.football_data_season,
    s.is_current, COUNT(m.match_id) AS matches_loaded
FROM seasons s
JOIN leagues l ON l.league_id = s.league_id
LEFT JOIN matches m ON m.season_id = s.season_id
GROUP BY l.code, s.label, s.footystats_season_id, s.football_data_season, s.is_current
ORDER BY l.code, s.label;
```

---

## 13. Notas de Implementação

### 13.1 Decisões de Design

| Decisão | Justificativa |
| --- | --- |
| UUID `match_id` | Evita conflitos cross-source. `gen_random_uuid()`. |
| SERIAL demais PKs | Tabelas de referência — mais eficiente. |
| `TIMESTAMPTZ` everywhere | UTC interno. BRT na exibição. |
| Sem particionamento em `matches` | ~57.500 rows no backfill + ~11.500/ano. Volume não justifica complexidade de FKs compostas nos coletores. Index em `season_id` resolve as queries. Reavaliar se ultrapassar 500k rows. |
| Hypertable apenas `odds_history` | Única tabela time-series com volume relevante. |
| Chunks mensais | ~25k odds/mês. Balanceia granularidade e overhead. |
| `content_hash` CHAR(64) | SHA-256 fixo. Eficiente para comparações. |
| Colunas GENERATED (`total_corners_*`) | Consistência garantida pelo PG. |
| `ON DELETE CASCADE` em FKs de dados | Match removido → stats/odds/lineups vão junto. |
| `raw_json` em `match_stats` | Reprocessamento sem re-coletar. |
| `end_date NULL` em temporadas correntes | Atualizado quando termina. |

### 13.2 Migrations

```
migrations/
├── 001_extensions.sql
├── 002_reference_tables.sql
├── 003_data_tables.sql
├── 004_control_tables.sql
├── 006_indexes.sql
├── 007_views.sql
├── 008_functions_triggers.sql
├── 009_m2_core_engine.sql
└── full_schema.sql.bak
```

### 13.3 Estimativas de Tamanho

| Tabela | Rows (pós-backfill) | Tamanho |
| --- | --- | --- |
| `leagues` | 26 | < 1 KB |
| `teams` | ~580 | < 100 KB |
| `team_aliases` | ~3.480 | < 500 KB |
| `seasons` | ~131 | < 50 KB |
| `bookmakers` | 13 | < 1 KB |
| `matches` | ~57.500 | ~30 MB |
| `match_stats` | ~57.500 × 1-2 fontes | ~50 MB |
| `odds_history` | >300k (seed) → ~2M (1 ano) | ~200 MB → ~1.5 GB |
| `lineups` | ~11.500/temporada | ~50 MB |
| `ingestion_log` | ~50k/ano | ~20 MB |
| **Total (1 ano)** |  | **~2 GB** |

### 13.4 Backup

```bash
# Completo
pg_dump -Fc -f backup_m1_$(date +%Y%m%d).dump maisevplus

# Restore
pg_restore -d maisevplus backup_m1_20260329.dump

# Somente schema
pg_dump -Fc --schema-only -f schema_m1.dump maisevplus
```