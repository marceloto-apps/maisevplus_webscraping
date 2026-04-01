# TASKS.md

# [TASKS.md](http://tasks.md/) — Módulo 1: Coleta de Dados (Ingestão)

> Breakdown de implementação do M1. Cada task tem escopo, dependências, entregáveis e critério de aceite.
Documentos de referência: `SPECS.md` (especificações), `SCHEMA.md` (DDL).
> 

---

## Índice

1. [Visão Geral](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
2. [Grafo de Dependências](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
3. [Fase 1 — Fundação](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
4. [Fase 2 — Coletores Core](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
5. [Fase 3 — Coletores Secundários](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
6. [Fase 4 — Orquestração](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
7. [Fase 5 — Backfill](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
8. [Fase 6 — Validação e Go-Live](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
9. [Resumo de Estimativas](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)
10. [Checklist Final](https://www.notion.so/TASKS-md-3322ae441a06809d8eebdaa9427aa6a3?pvs=21)

---

## 1. Visão Geral

Fase 1 — Fundação           [5 dias]   T01–T04
Fase 2 — Coletores Core     [9 dias]   T05–T08
Fase 3 — Coletores Sec.     [3 dias]   T09–T11
Fase 4 — Orquestração       [2 dias]   T12–T13
Fase 5 — Backfill           [2.5 dias] T14–T18
Fase 6 — Validação          [2 dias]   T19–T20
─────────────────────────────────────────────
Total                        ~23.5 dias (~5 semanas)

**Convenções:**

- ✅ = critério de aceite da task
- 🔗 = dependência (task que precisa estar concluída)
- 📁 = arquivo(s) entregue(s)
- ⏱️ = estimativa em dias úteis

---

## 2. Grafo de Dependências

```markdown
T01 ─────────────────────────────────────────────────────────────┐
│                                                               │
T02 ──┐                                                          │
│    │                                                          │
T03 ──┤                                                          │
│    │                                                          │
T04 ──┼──── T05 (Football-Data CSV) ──── T14 (Backfill Etapa 1) │
│      │                            │                      │
│     T06 (Footystats) ────────── T15 (Backfill Etapa 2)  │
│      │                            │                      │
│     T07 (Understat) ──────────── T16 (Backfill Etapa 3) │
│      │                            │                      │
│     T08 (FBRef) ─────────────── T17 (Backfill Etapa 4)  │
│      │                            │                      │
│     T09 (FlashScore) ──┐         T18 (Revisão Aliases)  │
│      │                 │          │                      │
│     T10 (Odds API) ───┤          │                      │
│      │                 │          │                      │
│     T11 (API-Football)┤          │                      │
│                       │          │                      │
│                      T12 (Scheduler) ── T19 (Testes)    │
│                       │                  │               │
│                      T13 (Alertas) ──── T20 (Go-Live)   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Fase 1 — Fundação

### T01 — Schema DDL + Extensions + Seeds

⏱️ **2 dias** | 🔗 Nenhuma

**Escopo:**

- Criar banco `maisevplus` com extensions (TimescaleDB, pgcrypto)
- Executar DDL completo conforme `SCHEMA.md`
- Rodar seeds de bookmakers, leagues e seasons
- Criar hypertable `odds_history`
- Criar views, funções e triggers
- Organizar em migration files

**Entregáveis:**

📁 migrations/
├── 001_extensions.sql
├── 002_reference_tables.sql
├── 003_data_tables.sql
├── 004_control_tables.sql
├── 006_indexes.sql
├── 007_views.sql
├── 008_functions_triggers.sql
├── 009_m2_core_engine.sql
└── full_schema.sql.bak
📁 scripts/
└── run_migrations.sh

**Critérios de aceite:**

- ✅ `SELECT COUNT(*) FROM leagues` = 26
- ✅ `SELECT COUNT(*) FROM bookmakers` = 13
- ✅ `SELECT COUNT(*) FROM seasons` = 131
- ✅ `SELECT * FROM timescaledb_information.hypertables` retorna `odds_history`
- ✅ Views `v_today_matches`, `v_closing_odds`, `v_match_full`, `v_ingestion_health`, `v_api_keys_usage` existem
- ✅ Trigger `trg_matches_updated_at` ativo
- ✅ `run_migrations.sh` executa limpo em banco vazio

---

### T02 — Estrutura do Projeto + Config YAMLs

⏱️ **0.5 dia** | 🔗 Nenhuma

**Escopo:**

- Criar estrutura de diretórios conforme `SPECS.md` seção 12.1
- Configurar `pyproject.toml` ou `requirements.txt`
- Criar arquivos YAML de configuração

**Entregáveis:**

📁 src/
├── collectors/
│   ├── **init**.py
│   ├── [base.py](http://base.py/)
│   ├── flashscore/
│   ├── footystats/
│   ├── football_data/
│   ├── fbref/
│   ├── understat/
│   ├── odds_api/
│   └── api_football/
├── normalizer/
├── scheduler/
├── config/
│   ├── sources.yaml
│   ├── bookmakers.yaml
│   ├── leagues.yaml
│   └── markets.yaml
├── alerts/
└── tests/
📁 pyproject.toml (ou requirements.txt)
📁 .env.example

```yaml
# config/leagues.yaml (exemplo parcial)
leagues:
  ENG_PL:
    name: "Premier League"
    country: "England"
    tier: 1
    football_data_code: "E0"
    football_data_type: "main"
    understat_name: "EPL"
    fbref_id: "9"
    xg_source: "understat"
    season_format: "aug_may"
    seasons:
      "2021/2022": { footystats: 6135, fd: "2122" }
      "2022/2023": { footystats: 7704, fd: "2223" }
      "2023/2024": { footystats: 9660, fd: "2324" }
      "2024/2025": { footystats: 12325, fd: "2425" }
      "2025/2026": { footystats: 15050, fd: "2526" }
```

```yaml
# config/markets.yaml
markets:
  full_time:
    1x2:   { line: null, ways: 3 }
    ou:    { lines: [0.5,1.0,1.25,1.5,1.75,2.0,2.25,2.5,2.75,3.0,3.25,3.5,3.75,4.0,4.25,4.5], ways: 2 }
    ah:    { lines: "dynamic_balanced_pm2", ways: 2 }
    dc:    { line: null, ways: 3 }
    dnb:   { line: null, ways: 2 }
    btts:  { line: null, ways: 2 }
  half_time:
    1x2_ht: { line: null, ways: 3 }
    ou_ht:  { lines: [0.5,0.75,1.0,1.25,1.5,1.75,2.0,2.25,2.5], ways: 2 }
    ah_ht:  { lines: "dynamic_balanced", ways: 2 }
```

```yaml
# config/bookmakers.yaml
bookmakers:
  pinnacle:
    display_name: "Pinnacle"
    type: "sharp"
    clv_priority: 1
    flashscore_aliases: ["Pinnacle", "Pinnacle Sports"]
  betfair_ex:
    display_name: "Betfair Exchange"
    type: "exchange"
    clv_priority: 2
    flashscore_aliases: ["Betfair", "Betfair Exchange"]
  bet365:
    display_name: "Bet365"
    type: "retail"
    clv_priority: 3
    flashscore_aliases: ["bet365", "Bet365"]
  # ... demais casas
```

**Critérios de aceite:**

- ✅ `import src.collectors.base` funciona
- ✅ YAMLs carregam sem erro
- ✅ `.env.example` documenta todas as variáveis necessárias

---

### T03 — BaseCollector + Normalizer Core

⏱️ **1.5 dias** | 🔗 T01, T02

**Escopo:**

- Implementar `BaseCollector` (classe abstrata) com `collect()`, `health_check()`, `generate_job_id()`
- Implementar `CollectResult` e `CollectStatus`
- Implementar `TeamResolver` com cache em memória + fallback para `unknown_aliases`
- Implementar `MatchResolver` (resolve via league + teams + data)
- Implementar `BookmakerResolver` (dict estático de aliases)
- Implementar `dedup.py` com `compute_content_hash()` e `insert_odds_if_new()`
- Implementar `odds_normalizer.py` com `calculate_overround()`

**Entregáveis:**

```
📁 src/collectors/base.py
📁 src/normalizer/
├── team_resolver.py
├── match_resolver.py
├── odds_normalizer.py
└── dedup.py
📁 src/tests/
├── test_normalizer.py
└── test_dedup.py
```

**Critérios de aceite:**

- ✅ `TeamResolver.resolve("football_data", "Man United")` → `team_id` ou `None` + registro em `unknown_aliases`
- ✅ `MatchResolver.resolve(league_id, "Arsenal", "Chelsea", "2025-03-29", "footystats")` → `match_id` ou `None`
- ✅ `compute_content_hash()` gera SHA-256 de 64 chars determinístico
- ✅ `insert_odds_if_new()` retorna `False` quando hash igual ao último
- ✅ `calculate_overround(1.95, 3.40, 4.20)` retorna valor correto
- ✅ Testes unitários passam

---

### T04 — Conexão DB + Helpers

⏱️ **1 dia** | 🔗 T01, T02

**Escopo:**

- Pool de conexões `asyncpg`
- Helper para insert, fetch, fetch_val, execute
- Logging estruturado (JSON)
- Função `log_ingestion()` que grava em `ingestion_log`
- Função `send_alert()` placeholder (implementação real em T13)

**Entregáveis:**

```
📁 src/db/
├── __init__.py
├── pool.py
├── helpers.py
└── logger.py
📁 src/alerts/
└── telegram_mini.py    # placeholder: print() por enquanto
```

**Critérios de aceite:**

- ✅ Pool conecta e executa `SELECT 1`
- ✅ `log_ingestion()` grava registro em `ingestion_log` e retorna `log_id`
- ✅ Logger gera JSON com timestamp, level, source, message
- ✅ `send_alert()` não quebra quando Telegram não configurado

---

## 4. Fase 2 — Coletores Core

### T05 — Football-Data CSV Collector

⏱️ **2 dias** | 🔗 T03, T04

**Escopo:**

- Download de CSVs (main: `mmz4281/{season}/{code}.csv`, extra: `new/{code}.csv`)
- Parse com pandas (encoding utf-8/latin-1, `on_bad_lines='skip'`)
- Extrair matches: date, time, home, away, ft, ht, result
- Extrair odds: Pinnacle 1X2, Pinnacle OU 2.5, Bet365 1X2, Bet365 OU 2.5 (onde disponível)
- Gerar `team_aliases_seed.csv` para revisão manual
- Tratar colunas ausentes em extra leagues como NULL
- INSERT em `matches` + `odds_history` (com `is_opening=TRUE`, `is_closing=TRUE`, `source='football_data'`)

**Entregáveis:**

```
📁 src/collectors/football_data/
├── __init__.py
└── csv_collector.py
📁 src/tests/test_football_data.py
📁 output/team_aliases_seed.csv    # Gerado na execução
```

**Lógica de URLs:**

```python
MAIN_URL = "<https://www.football-data.co.uk/mmz4281/{season}/{code}.csv>"
EXTRA_URL = "<https://www.football-data.co.uk/new/{code}.csv>"

# Main: season='2425', code='E0' → .../mmz4281/2425/E0.csv
# Extra: code='BRA' → .../new/BRA.csv (multi-temporada, filtrar por data)
```

**Colunas relevantes do CSV:**

```python
MAIN_COLS = {
    'Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam',
    'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
    'PSH', 'PSD', 'PSA',           # Pinnacle 1X2
    'P>2.5', 'P<2.5',              # Pinnacle OU 2.5
    'B365H', 'B365D', 'B365A',     # Bet365 1X2
    'B365>2.5', 'B365<2.5',        # Bet365 OU 2.5
}
# Extra leagues podem não ter PSH/PSD/PSA nem B365
```

**Critérios de aceite:**

- ✅ Download OK para 26 ligas × 5 temporadas (130+ CSVs)
- ✅ `team_aliases_seed.csv` gerado com ~580 times únicos
- ✅ Matches inseridos com `source='football_data'`
- ✅ Odds com `is_opening=TRUE` e `is_closing=TRUE` (snapshot único do CSV)
- ✅ Extra leagues com colunas ausentes → NULL, sem crash
- ✅ Health check implementado (HEAD request no site)

---

### T06 — Footystats Collector

⏱️ **3 dias** | 🔗 T03, T04

**Escopo:**

- `api_client.py`: httpx async client com key ilimitada, rate limiting, retry
- `matches_collector.py`: endpoint `league-matches?season_id=X`, parse com `FOOTYSTATS_FIELD_MAP`
- `fixtures_collector.py`: calendário de jogos futuros
- `backfill.py`: loop por season_id, enriquece `matches` e insere `match_stats`
- Transformações: `1` → NULL, goals_minutes string → JSONB array, xG negativo → NULL

**Entregáveis:**

```
📁 src/collectors/footystats/
├── __init__.py
├── api_client.py
├── matches_collector.py
├── fixtures_collector.py
└── backfill.py
📁 src/tests/test_footystats.py
```

**Endpoints usados:**

```
GET <https://api.football-data-api.com/league-matches>
    ?key={KEY}&season_id={SEASON_ID}
    &page=1&per_page=500

GET <https://api.football-data-api.com/league-matches>
    ?key={KEY}&season_id={SEASON_ID}
    &date_from={YYYY-MM-DD}&date_to={YYYY-MM-DD}
```

**Critérios de aceite:**

- ✅ Backfill de 1 liga/temporada retorna matches + stats completas
- ✅ `match_stats` com xG, chutes, escanteios, cartões HT/FT, posse
- ✅ `goals_home_minutes` / `goals_away_minutes` como JSONB array
- ✅ Valores `1` convertidos para NULL
- ✅ `footystats_id` linkado em `matches`
- ✅ `fixtures_collector` retorna jogos futuros com kickoff correto (UTC)
- ✅ Health check: request de teste com resposta 200

---

### T07 — Understat Collector

⏱️ **1 dia** | 🔗 T03, T04

**Escopo:**

- Scraper httpx e Regex nativo (sem libs de terceiros) p/ extração de JS variables
- Coletar xG granular para 5 ligas Top 5: EPL, La_Liga, Bundesliga, Serie_A, Ligue_1
- Parse: understat_id, home, away, xg_home, xg_away, date
- INSERT/UPDATE em `match_stats` com `source='understat'`
- Link `understat_id` em `matches`
- Rate limiting: 20 req/60s

**Entregáveis:**

```
📁 src/collectors/understat/
├── __init__.py
└── xg_collector.py
📁 src/tests/test_understat.py
```

**Critérios de aceite:**

- ✅ Coleta xG de 1 liga/temporada com dados corretos
- ✅ `match_stats` com `source='understat'` e xG preenchido
- ✅ `understat_id` linkado em `matches`
- ✅ Rate limiting respeitado (sem 429)
- ✅ Health check funcional

---

### T08 — FBRef Collector

⏱️ **2 dias** | 🔗 T03, T04

**Escopo:**

- `scraper.py`: requests + BeautifulSoup4, rate limiting 10 req/min
- `parser.py`: extrair tabela de scores/fixtures com xG
- Parse: fbref_id, date, home, away, ft_home, ft_away, xg_home, xg_away
- INSERT/UPDATE em `match_stats` com `source='fbref'`
- Link `fbref_id` em `matches`
- Cobrir 19 ligas (todas exceto Top 5 Understat e SCO_L1/L2)

**Entregáveis:**

```
📁 src/collectors/fbref/
├── __init__.py
├── scraper.py
└── parser.py
📁 src/tests/test_fbref.py
```

**URL pattern:**

```
<https://fbref.com/en/comps/{fbref_id}/{season}/schedule/{season}-{comp_name}-Scores-and-Fixtures>
# Ex: <https://fbref.com/en/comps/9/2024-2025/schedule/2024-2025-Premier-League-Scores-and-Fixtures>
```

**Critérios de aceite:**

- ✅ Parse de tabela FBRef retorna matches com xG
- ✅ Rate limiting 10 req/min respeitado
- ✅ `match_stats` com `source='fbref'` e xG preenchido
- ✅ `fbref_id` linkado em `matches`
- ✅ xG vazio → NULL (sem crash)
- ✅ Health check funcional

---

## 5. Fase 3 — Coletores Secundários

### T09 — FlashScore Odds Collector

⏱️ **4 dias** | 🔗 T03, T04

**Escopo:**

- `driver.py`: Selenium undetected-chromedriver, headless, cookie handler
- `selectors.py`: CSS/XPath isolados (fácil manutenção quando HTML mudar)
- `parser.py`: HTML → dict de odds por casa/mercado/linha
- `odds_collector.py`: orquestra navegação → parse → normalização → insert
- 13 casas × 9 mercados (FT: 1x2, ou, ah, dc, dnb, btts | HT: 1x2_ht, ou_ht, ah_ht)
- Linhas dinâmicas: OU FT (16), OU HT (9), AH (balanced ± 2)
- Dedup via `content_hash` + `insert_odds_if_new()`
- Mark `is_opening` no primeiro registro
- Overround calculado

**Entregáveis:**

```
📁 src/collectors/flashscore/
├── __init__.py
├── driver.py
├── selectors.py
├── parser.py
└── odds_collector.py
📁 src/tests/test_flashscore.py
```

**Regras de filtragem:**

```python
# Não inserir odds quando:
SKIP_CONDITIONS = [
    lambda odds: odds in ["-", "", None],       # Indisponível
    lambda odds: float(odds) <= 1.0,            # Sem retorno
]

# Casas aceitas (filtro)
ACCEPTED_BOOKMAKERS = {
    "Pinnacle", "Pinnacle Sports",
    "Betfair", "Betfair Exchange",
    "bet365", "Bet365",
    "1xBet",
    "Betano", "Sportingbet", "Superbet",
    "BetNacional", "Bet Nacional",
    "EstrelaBet", "Estrela Bet",
    "KTO", "7K",
    "F12", "F12.bet",
    "Multibet",
}
```

**Critérios de aceite:**

- ✅ Coleta odds de 1 jogo com 13 casas × 9 mercados
- ✅ Selectors isolados em `selectors.py` (nenhum CSS/XPath hardcoded em outros arquivos)
- ✅ Dedup funciona: 2ª coleta do mesmo jogo sem mudança → 0 inserts novos
- ✅ `is_opening` marcado no primeiro registro de cada combinação
- ✅ Overround calculado corretamente
- ✅ Odds `"-"`, `""`, `"1.00"` filtradas
- ✅ Health check: acessa página de teste no FlashScore

---

### T10 — The Odds API Collector

⏱️ **1 dia** | 🔗 T03, T04

**Escopo:**

- `api_collector.py`: httpx client com multi-key (5 contas)
- Integração com `KeyManager` para rotação
- Endpoints: upcoming odds (Pinnacle, Betfair, Bet365)
- Markets: h2h, spreads, totals
- INSERT em `odds_history` com `source='odds_api'`
- Usado como validação cruzada + fallback de FlashScore

**Entregáveis:**

```
📁 src/collectors/odds_api/
├── __init__.py
└── api_collector.py
📁 src/tests/test_odds_api.py
```

**Critérios de aceite:**

- ✅ Coleta odds de Pinnacle via API
- ✅ Rotação de keys funciona (key 1 esgota → usa key 2)
- ✅ Respeita 500 req/mês por key
- ✅ Health check: request de teste com key ativa

---

### T11 — API-Football Collector

⏱️ **1 dia** | 🔗 T03, T04

**Escopo:**

- `api_collector.py`: httpx client com multi-key (7 contas)
- Integração com `KeyManager`
- Endpoint: lineups por fixture_id
- Parse: formation, players (name, number, pos, grid)
- INSERT em `lineups` com `source='api_football'`
- Retry se `lineups: []` (não confirmada ainda)

**Entregáveis:**

```
📁 src/collectors/api_football/
├── __init__.py
└── api_collector.py
📁 src/tests/test_api_football.py
```

**Critérios de aceite:**

- ✅ Coleta escalação de 1 jogo com formação + jogadores
- ✅ Rotação de 7 keys funciona
- ✅ Respeita 100 req/dia por key
- ✅ `lineups: []` → não insere, agenda retry T-30min
- ✅ Health check funcional

---

## 6. Fase 4 — Orquestração

### T12 — Scheduler + Key Manager

⏱️ **2 dias** | 🔗 T05–T11

**Escopo:**

- `key_manager.py`: rotação multi-key com `get_key()`, `reset_daily()`, `reset_monthly()`
- `jobs.py`: definição de todos os 12 jobs conforme [SPECS.md](http://specs.md/) seção 6.1
- Jobs estáticos (cron): `odds_standard`, `xg_postround`, `fixtures_weekly`, `csv_weekly`, `odds_api_validation`, `health_check`, `reset_daily_keys`
- Jobs dinâmicos (T-X): `schedule_gameday_jobs()` roda 00:30 BRT, agenda `lineups_prematch`, `odds_prematch_30`, `odds_prematch_2`, `results_postmatch`
- `odds_gameday_hourly`: 8h–23h BRT, jogos não iniciados com >35min até kickoff
- `mark_closing_odds()` executado em `results_postmatch`
- Misfire grace time configurado por job

**Entregáveis:**

```
📁 src/scheduler/
├── __init__.py
├── key_manager.py
└── jobs.py
📁 src/tests/test_scheduler.py
```

**Jobs implementados:**

| Job | Tipo | Cron/Trigger | Fonte |
| --- | --- | --- | --- |
| `odds_standard` | cron | `0 6,10,14,20 * * *` BRT | FlashScore |
| `odds_gameday_hourly` | cron | `0 8-23 * * *` BRT | FlashScore |
| `odds_prematch_30` | date | T-30min | FlashScore |
| `odds_prematch_2` | date | T-2min | FlashScore |
| `results_postmatch` | date | T+2h30 | Footystats |
| `xg_postround` | cron | `0 6 * * *` BRT | Understat/FBRef |
| `lineups_prematch` | date | T-60min | API-Football |
| `fixtures_weekly` | cron | `0 5 * * 1` BRT | Footystats |
| `csv_weekly` | cron | `0 4 * * 1` BRT | Football-Data |
| `odds_api_validation` | interval | 3h (dias com jogos) | Odds API |
| `health_check` | interval | 5min | Todas |
| `reset_daily_keys` | cron | `0 0 * * *` UTC | — |

**Critérios de aceite:**

- ✅ `KeyManager.get_key('api_football')` retorna key válida e incrementa `usage_today`
- ✅ `KeyManager.get_key()` lança `NoKeysAvailableError` quando todas esgotadas
- ✅ `reset_daily()` zera `usage_today` para todas as keys
- ✅ `schedule_gameday_jobs()` agenda 4 jobs por jogo (T-60, T-30, T-2, T+2h30)
- ✅ `mark_closing_odds()` marca último registro antes do kickoff como `is_closing=TRUE`
- ✅ Jobs cron disparam nos horários corretos (verificar com 1 ciclo)

---

### T13 — Alertas Telegram

⏱️ **0.5 dia** | 🔗 T04

**Escopo:**

- Implementar `send_alert()` real via Telegram Bot API (httpx)
- Níveis: info (log only), warning, error, critical
- Alertas configuráveis: chat_id, bot_token via `.env`
- Integrar nos pontos de alerta:
    - Alias desconhecido → warning
    - Job falhou após retries → error
    - Key > 80% do limite → warning
    - Todas keys esgotadas → critical
    - Fonte down > 15min → error

**Entregáveis:**

```
📁 src/alerts/
└── telegram_mini.py
```

**Critérios de aceite:**

- ✅ Mensagem chega no Telegram com nível, fonte e detalhes
- ✅ Falha no Telegram não quebra o pipeline (graceful degradation)
- ✅ Rate limiting no envio (máx 20 msg/min para não ser bloqueado)

---

## 7. Fase 5 — Backfill

### T14 — Backfill Etapa 1: Football-Data CSV Seed

⏱️ **0.5 dia** | 🔗 T05

**Escopo:**

- Executar `csv_collector.py` para 26 ligas × 5 temporadas
- Main leagues: 22 ligas × 5 seasons = 110 CSVs
- Extra leagues: 4 ligas × 1 CSV multi-temporada = 4 CSVs
- Gerar `team_aliases_seed.csv`
- Inserir matches e odds históricas (Pinnacle/B365)

**Execução:**

```bash
python -m src.collectors.football_data.csv_collector --mode=backfill --output=output/
```

**Critérios de aceite:**

- ✅ `matches` > 50.000 rows
- ✅ `odds_history` > 200.000 rows (seed com 1X2 + OU 2.5 Pinnacle/B365)
- ✅ `team_aliases_seed.csv` gerado com ~580 times
- ✅ Zero erros no `ingestion_log`

---

### T15 — Backfill Etapa 2: Revisão de Aliases ⏸️

⏱️ **1 dia** (Marcelo) | 🔗 T14

**Escopo:**

- Marcelo revisa `team_aliases_seed.csv`
- Preenche `canonical_name_bet365` e `country` para cada time
- Resultado importado em `teams` + `team_aliases`

**Entregáveis:**

```
📁 output/team_aliases_reviewed.csv
📁 scripts/import_aliases.py
```

**Formato do CSV:**

```
football_data_name,canonical_name_bet365,country,league_code
Man United,Manchester United,England,E0
Man City,Manchester City,England,E0
...
```

**Critérios de aceite:**

- ✅ `teams` ≈ 580 rows
- ✅ `team_aliases` ≈ 580 rows (source='football_data')
- ✅ Zero rows em `unknown_aliases`

---

### T16 — Backfill Etapa 3: Footystats Stats

⏱️ **0.5 dia** | 🔗 T06, T15

**Escopo:**

- Executar `backfill.py` para 26 ligas × 5 temporadas (130 season requests)
- Enriquecer `match_stats` com stats completas
- Atualizar `matches` com HT scores, minutos dos gols, `footystats_id`
- Gerar aliases Footystats → inserir em `team_aliases` (source='footystats')

**Execução:**

```bash
python -m src.collectors.footystats.backfill --all-seasons
```

**Critérios de aceite:**

- ✅ `match_stats` > 50.000 rows com `source='footystats'`
- ✅ xG, chutes, escanteios, cartões preenchidos onde disponível
- ✅ `goals_home_minutes` / `goals_away_minutes` como JSONB
- ✅ `footystats_id` linkado em `matches`
- ✅ Aliases Footystats inseridos em `team_aliases`

---

### T17 — Backfill Etapa 4: xG (Understat + FBRef)

⏱️ **1 dia** (supervisionado) | 🔗 T07, T08, T15

**Escopo:**

- **Understat**: 5 ligas × 5 temporadas = 25 requests. ~3h com rate limiting.
- **FBRef**: 19 ligas × 5 temporadas = 95 pages. ~14h com rate limiting 10 req/min.
- INSERT em `match_stats` com `source='understat'` e `source='fbref'`
- Link `understat_id` e `fbref_id` em `matches`

**Execução:**

```bash
# Understat (~3h)
python -m src.collectors.understat.backfill

# FBRef (~14h, rodar em background)
nohup python -m src.collectors.fbref.scraper --mode=backfill > fbref_backfill.log 2>&1 &
```

**Critérios de aceite:**

- ✅ `match_stats` com `source='understat'`: ~9.500 rows (5 ligas × 5 temporadas × ~380 jogos)
- ✅ `match_stats` com `source='fbref'`: ~48.000 rows (19 ligas × 5 temporadas)
- ✅ Zero 429 errors
- ✅ `understat_id` e `fbref_id` linkados em `matches`

---

### T18 — Aliases Cross-Source (pós-backfill)

⏱️ **0.5 dia** | 🔗 T16, T17

**Escopo:**

- Revisar `unknown_aliases` gerados durante backfill Footystats/Understat/FBRef
- Mapear aliases restantes para `team_aliases`
- Garantir cobertura: ~580 times × 4 fontes (football_data, footystats, understat/fbref)

**Execução:**

```bash
# Exportar pendentes
python -m scripts.export_unknown_aliases > output/unknown_aliases.csv

# Após revisão manual
python -m scripts.import_aliases --file=output/unknown_aliases_resolved.csv
```

**Critérios de aceite:**

- ✅ `unknown_aliases` com `resolved=FALSE`: 0 rows
- ✅ `team_aliases` ≈ 2.300+ rows (580 × 4 fontes)
- ✅ `v_match_full` retorna dados para todas as ligas sem NULL em home_team/away_team

---

## 8. Fase 6 — Validação e Go-Live

### T19 — Testes + Resiliência

⏱️ **1.5 dias** | 🔗 T12, T13, T14–T18

**Escopo:**

- Testes de integração: cada coletor faz coleta real de 1 jogo/liga
- Teste de fallback: simular FlashScore down → Odds API assume
- Teste de retry: simular erro de rede → retry com backoff funciona
- Teste de dedup: coleta duplicada → 0 inserts novos
- Teste de key rotation: esgotar key 1 → key 2 assume
- Teste de `mark_closing_odds()`: verificar que closing está correto
- Rodar dashboard de aceite (`SCHEMA.md` seção 12.1)

**Entregáveis:**

```
📁 src/tests/
├── test_football_data.py
├── test_footystats.py
├── test_understat.py
├── test_fbref.py
├── test_flashscore.py
├── test_odds_api.py
├── test_api_football.py
├── test_normalizer.py
├── test_dedup.py
├── test_scheduler.py
├── test_integration.py         # Testes end-to-end
└── test_fallback.py            # Simulação de falhas
```

**Critérios de aceite:**

- ✅ Todos os testes unitários passam
- ✅ Teste de integração: 6 fontes coletam sem erro
- ✅ Fallback FlashScore → Odds API funciona
- ✅ Retry com backoff funciona (delay progressivo)
- ✅ Dedup funciona (0 duplicatas)
- ✅ Key rotation funciona
- ✅ Dashboard de aceite: todos os checks ✅

---

### T20 — Go-Live: Schedule 48h

⏱️ **2 dias** (monitoramento) | 🔗 T19

**Escopo:**

- Ativar todos os jobs do scheduler
- Monitorar 48h contínuas
- Verificar `v_ingestion_health`: zero `failed`
- Verificar `v_api_keys_usage`: nenhuma key > 80%
- Verificar `v_today_matches`: jogos sendo coletados
- Ajustar rate limits ou timings se necessário

**Monitoramento:**

```sql
-- Rodar a cada 4h durante go-live
SELECT * FROM v_ingestion_health;
SELECT * FROM v_api_keys_usage;
SELECT COUNT(*) FROM unknown_aliases WHERE resolved = FALSE;
```

**Critérios de aceite (M1 completo):**

| # | Critério | Query/Verificação |
| --- | --- | --- |
| 1 | 6 fontes ativas | Health check OK simultâneo |
| 2 | Backfill completo | `matches` > 50.000 rows |
| 3 | Stats preenchidas | `match_stats` > 45.000 rows com xG |
| 4 | Odds históricas | `odds_history` > 300.000 rows |
| 5 | Schedule 48h | `ingestion_log` sem `failed` por 48h |
| 6 | Dedup | Zero duplicatas |
| 7 | Normalização | `unknown_aliases` resolved=FALSE = 0 |
| 8 | Fallback | FlashScore off → Odds API assume |
| 9 | Multi-key | 7+5 keys rotacionando |
| 10 | 13 casas | Pinnacle + Bet365 + 3+ BR coletadas |
| 11 | HT/FT stats | Campos HT preenchidos onde disponível |
| 12 | Minutos gols | JSONB arrays preenchidos |

---

## 9. Resumo de Estimativas

| Fase | Tasks | Dias |
| --- | --- | --- |
| **Fase 1 — Fundação** | T01–T04 | 5 |
| **Fase 2 — Coletores Core** | T05–T08 | 8 |
| **Fase 3 — Coletores Secundários** | T09–T11 | 6 |
| **Fase 4 — Orquestração** | T12–T13 | 2.5 |
| **Fase 5 — Backfill** | T14–T18 | 3.5 |
| **Fase 6 — Validação** | T19–T20 | 3.5 |
|  | **Total** | **~28.5 dias (~6 semanas)** |

> **Nota:** T15 (revisão de aliases) é bloqueante e depende do Marcelo. Se revisão demorar, T09–T13 podem avançar em paralelo.
> 

### Caminho Crítico

```
T01 → T03 → T05 → T14 → T15 (⏸️ Marcelo) → T16 → T17 → T18 → T19 → T20
                                      ↕ paralelo
                    T09, T10, T11 → T12 → T13
```

### Paralelismo Possível

| Período | Em paralelo |
| --- | --- |
| Dias 1–5 | T01 + T02 → T03 + T04 |
| Dias 6–13 | T05 + T06 (core) em sequência, T07 + T08 podem sobrepor |
| Dias 6–13 | T09 (FlashScore, 4 dias) pode iniciar junto com T06 |
| Dias 10–13 | T10 + T11 em paralelo |
| Dia 14 | T14 (backfill seed) |
| Dias 15–16 | T15 (⏸️ aliases) // T12 + T13 em paralelo |
| Dias 17–20 | T16 + T17 (backfill stats + xG) |
| Dia 21 | T18 (aliases cross-source) |
| Dias 22–23 | T19 (testes) |
| Dias 24–28 | T20 (go-live 48h + buffer) |

---

## 10. Checklist Final

```
FUNDAÇÃO
  [x] T01  Schema DDL + seeds executados
  [x] T02  Estrutura do projeto + YAMLs
  [x] T03  BaseCollector + Normalizer
  [x] T04  Conexão DB + helpers

COLETORES CORE
  [x] T05  Football-Data CSV collector
  [x] T06  Footystats collector
  [x] T07  Understat collector
  [ ] T08  FBRef collector

COLETORES SECUNDÁRIOS
  [ ] T09  FlashScore odds collector
  [ ] T10  The Odds API collector
  [ ] T11  API-Football collector

ORQUESTRAÇÃO
  [ ] T12  Scheduler + Key Manager
  [ ] T13  Alertas Telegram

BACKFILL
  [ ] T14  Etapa 1: Football-Data seed
  [ ] T15  Etapa 2: Revisão aliases (Marcelo)
  [ ] T16  Etapa 3: Footystats stats
  [ ] T17  Etapa 4: xG Understat + FBRef
  [ ] T18  Aliases cross-source

VALIDAÇÃO
  [ ] T19  Testes + resiliência
  [ ] T20  Go-live 48h

ACEITE M1
  [ ] Dashboard de aceite: todos ✅
  [ ] Documentação atualizada
  [ ] Handoff para M2
```

---

## 11. Módulo 2: Core Analítico (Concluído)

> **Nota Oficial:** O Módulo 2 (NodeJS Backend Engine, API, Middlewares e Cron Jobs) foi 100% desenvolvido antes do M1 entrar em vigor, possuindo seu próprio roadmap de execução. Segue trilha documental do seu estado de maturidade:

### Resumo das Fases Resolvidas (Status: READY PARA PRODUÇÃO)

**Fase 1: Setup e Ferramentas Base** `[100%]`
- [x] Pool de Conexões assíncronas ao banco construídas de forma global.
- [x] Middlewares centrais implementados (Tratamento `AppError`, ParseId helpers, Validações estritas de schema `Joi`).
- [x] Sistema de Tracking avançado com Winston Logger ativo.

**Fase 2: Core Models** `[100%]`
- [x] `Bankroll.js`: Persistência de extratos integrando PostgreSQL Advisory Locks para resolver race-conditions de usuários em apostas concorrentes.
- [x] `Prediction.js`: Suporte a injeção transacional atômica para salvamento aglomerado sem quebras lógicas.
- [x] `Match.js / Team.js`: Helpers de conversão O(1) com map-cache para Footystats IDs para sync massivo seguro.
- [x] Auth layers e entidades `Odd / League`.

**Fase 3: APIs Fundacionais** `[100%]`
- [x] Segregação em Node Routers (`routes/auth.js` com JWT login tipado e hashes cryptográficos).
- [x] Fallbacks nativos em ausência de Env Vars.

**Fase 4: Predict Engine & Value Bets (Masterpiece)** `[100%]`
- [x] `statsService.js`: Motor Atuarial. Implementa distribuição Bivariada de Poisson dinâmico simulando Matrixes [0..8] gols, cruzando com Overrounds de Casa de Aposta extraídos.
- [x] `kellyService.js`: Gerenciamento e precificação. Retorna o True-Odds e emite relatórios ValueBet cruzando saldos correntes na balança de Kelley com clamps fixados.
- [x] `settlementService.js`: Motor de Liquidação. Compara snapshots "shadow/predict" contra "scores ft-ht", depositando automaticamente o payout na banca e fechando furos transacionais.

**Fase 5: Rotas Administrativas e de Telemetria** `[100%]`
- [x] 9 Sub-Routers criados (`leagues`, `teams`, `matches`, `odds`, `predictions`, `bets`, `bankroll`, `dashboard`).
- [x] Sync Partial Mapping: Otimização N+1 em arrays gigantes limitando dependências seq.
- [x] Dashboard Views: Implementação robusta de time-series combinando PLs diários com `generate_series`.

**Fase 6: Orquestração Final do Cluster M2** `[100%]`
- [x] `app.js`: Master Core isolado blindado com Helmet e limitadores customizados de IPS massivos em rotas Críticas e de Login.
- [x] `scheduler.js`: Relojoeiro operante com bloqueador de instâncias paralelas. Faz triggers automáticos de settlementService pelo node-cron a cada 60min no backend sem interferir a main thread.
- [x] `server.js`: Listen Wrapper com hookings para Graceful Exit protegendo fluxos no-ar de cortes secos (`SIGINT` e `SIGTERM`).

**Fase 7: Deploy VPS e Hooks do Frontend (Mar/2026)** `[Em Andamento]`
- [x] **Infraestrutura VPS:** Migração do Backend para a VPS conectando na porta `5432` nativa (Host Network Mode).
- [x] **Rota 1 (Healthcheck):** End-point `/health` implementado e respondendo corretamente na porta 3000.
- [x] **Rota 2 (Predictions):** End-point `/api/predictions/active` refatorado para ler a model `predictions` (M2 schema) ignorando auth (Rota Pública). Retornos de Matriz validados.
- [x] **Seed Dev Integrado:** Script `seed_dev.js` isolado do DB docker, atualizado para as Specifications do M2.
- [x] **Rota 3 (Auth Login):** Rodar Seed Dev na VPS para injetar Admin e testar geração estática de JWT pelo Postman/cURL.
- [x] **Rota 4 (Dashboard):** Expor sumário financeiro com cruzamentos da `bankroll`.