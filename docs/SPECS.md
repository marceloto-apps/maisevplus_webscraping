# SPECS.md

# [SPECS.md](http://specs.md/) — Módulo 1: Coleta de Dados (Ingestão)

> Especificação técnica completa do M1. Fonte de verdade para implementação.
Documentos complementares: `SCHEMA.md` (DDL + indexes), `TASKS.md` (breakdown de execução).
> 

---

## Índice

1. [Decisões Consolidadas](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
2. [Fontes de Dados](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
3. [Ligas no Escopo](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
4. [Casas de Apostas](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
5. [Mercados e Linhas](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
6. [Schedule de Coleta](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
7. [Contratos de Interface](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
8. [Regras de Negócio](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
9. [Normalização e Dedup](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
10. [Backfill Histórico](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
11. [Resiliência e Fallback](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
12. [Configuração e Estrutura de Código](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
13. [Monitoramento e Alertas](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
14. [Critérios de Aceite](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)
15. [Estimativas](https://www.notion.so/SPECS-md-3322ae441a06805484d9f32c27c3e7e2?pvs=21)

---

## 1. Decisões Consolidadas

| Ponto | Decisão |
| --- | --- |
| Stats/Resultados | Footystats API (key ilimitada) — fonte primária |
| Odds tempo real | FlashScore (Selenium headless) — fonte primária |
| Backfill histórico | [Football-Data.co.uk](http://football-data.co.uk/) (CSV) → Footystats (stats) → Understat/FBRef (xG) |
| xG Top 5 europeias | Understat (granular, por chute) |
| xG demais ligas | FBRef (por jogo) |
| xG fallback | Footystats (básico — SCO_L1, SCO_L2) |
| Escalações | API-Football (7 contas free, 700 req/dia) |
| Validação de odds | The Odds API (5 contas free, 2.500 req/mês) |
| BetExplorer | **Desativada no MVP** |
| CLV (closing line) | Pinnacle → Betfair → Bet365 (Footystats **excluída** — odds compiladas, não de mercado) |
| Período histórico | 5 temporadas + atual: 2021/22 a 2025/26 |
| Total de ligas | **26 ligas, 14 países** |
| Season IDs Footystats | 130/130 mapeados (100%) |
| Nomes canônicos | Bet365 como referência |
| Aliases | Seed via Football-Data CSV → revisão manual (CSV) |
| Campos NULL aceitos | Escanteios HT, Cartões HT |
| Odds Footystats | **Excluídas** (compiladas, não representam odds reais de mercado) |
| Proxies | Não no MVP |
| Timezone | `TIMESTAMPTZ` (UTC interno), conversão BRT na exibição |

---

## 2. Fontes de Dados

### 2.1 Mapa de Responsabilidades

| Fonte | Tipo de Acesso | Responsabilidade Primária | Secundária |
| --- | --- | --- | --- |
| **Footystats API** | HTTP REST (key ilimitada) | Resultados, stats completas (xG, chutes, escanteios, cartões HT/FT, minutos gols), fixtures | — |
| **FlashScore** | Selenium headless | Odds tempo real (13 casas × 9 mercados) | Fallback resultados |
| [**Football-Data.co.uk**](http://football-data.co.uk/) | HTTP (CSV download) | Backfill seed (matches + odds Pinnacle/B365) | — |
| **Understat** | HTTP (lib Python async) | xG granular Top 5 (por chute, por situação de jogo) | — |
| **FBRef** | HTTP (requests + BeautifulSoup4) | xG por jogo (19 ligas adicionais) | Stats avançadas |
| **The Odds API** | HTTP REST (5 keys free) | Validação cruzada de odds (Pinnacle) | Fallback quando FlashScore falha |
| **API-Football** | HTTP REST (7 keys free) | Escalações confirmadas | Fallback fixtures |

### 2.2 Hierarquia de Fallback

RESULTADOS + STATS: Footystats → API-Football → FlashScore → [Football-Data.co.uk](http://football-data.co.uk/)

ODDS TEMPO REAL: FlashScore → The Odds API

ODDS FECHAMENTO (CLV): FlashScore (Pinnacle último snapshot antes do kickoff) → Football-Data (Pinnacle closing odds do CSV histórico)

xG: Understat (5 ligas Top 5) → FBRef (19 ligas adicionais) → Footystats (2 ligas sem cobertura FBRef: SCO_L1, SCO_L2)

ESCALAÇÕES: API-Football → FlashScore

FIXTURES/CALENDÁRIO: Footystats → API-Football

### 2.3 Diagrama de Fontes

```markdown
┌─────────────────────────────────────────────────────────────────────┐
│                        FONTES DE DADOS M1                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐   ODDS TEMPO REAL        ┌──────────────────┐    │
│  │  FlashScore   │ ──────────────────────── │  odds_history    │    │
│  │  (Selenium)   │   13 casas × 9 mercados  │  (hypertable)    │    │
│  └──────────────┘                           └──────────────────┘    │
│         │ fallback                                                  │
│         ▼                                                           │
│  ┌──────────────┐   VALIDAÇÃO CRUZADA                              │
│  │ The Odds API  │   Pinnacle via API                              │
│  │ (5 keys)      │   2.500 req/mês                                 │
│  └──────────────┘                                                   │
│                                                                     │
│  ┌──────────────┐   RESULTADOS + STATS     ┌──────────────────┐    │
│  │  Footystats   │ ──────────────────────── │  matches         │    │
│  │  (API ilimit.) │  xG, gols, chutes,     │  match_stats     │    │
│  └──────────────┘   escanteios, cartões    └──────────────────┘    │
│                      HT/FT, minutos gols                           │
│                                                                     │
│  ┌──────────────┐   BACKFILL SEED          ┌──────────────────┐    │
│  │ Football-Data │ ──────────────────────── │  matches (seed)  │    │
│  │  (CSV)        │  Pinnacle/B365 odds     │  odds_history    │    │
│  └──────────────┘                           └──────────────────┘    │
│                                                                     │
│  ┌──────────────┐   xG DETALHADO           ┌──────────────────┐    │
│  │  Understat    │ ──────────────────────── │  match_stats     │    │
│  │  (Top 5)      │  Por chute, situação    └──────────────────┘    │
│  ├──────────────┤                                                   │
│  │  FBRef        │   xG 19 ligas adicionais                       │
│  │  (HTTP+BS4)   │                                                  │
│  └──────────────┘                                                   │
│                                                                     │
│  ┌──────────────┐   ESCALAÇÕES             ┌──────────────────┐    │
│  │ API-Football  │ ──────────────────────── │  lineups         │    │
│  │ (7 keys)      │                          └──────────────────┘    │
│  └──────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Ligas no Escopo

### 3.1 Tabela Completa — 26 Ligas

### Tier 1 — Main Leagues (17 ligas)

| # | País | Liga | Código | FD Code | FD Type | Understat | FBRef ID | xG Source | Formato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | Premier League | `ENG_PL` | `E0` | main | `EPL` | 9 | understat | Ago–Mai |
| 2 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | Championship | `ENG_CH` | `E1` | main | ❌ | 10 | fbref | Ago–Mai |
| 3 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | League One | `ENG_L1` | `E2` | main | ❌ | 15 | fbref | Ago–Mai |
| 4 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | League Two | `ENG_L2` | `E3` | main | ❌ | 16 | fbref | Ago–Mai |
| 5 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | National League | `ENG_NL` | `EC` | main | ❌ | 58 | fbref | Ago–Mai |
| 6 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | Premiership | `SCO_PL` | `SC0` | main | ❌ | 40 | fbref | Ago–Mai |
| 7 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | Championship | `SCO_CH` | `SC1` | main | ❌ | 69 | fbref | Ago–Mai |
| 8 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | League One | `SCO_L1` | `SC2` | main | ❌ | — | footystats | Ago–Mai |
| 9 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | League Two | `SCO_L2` | `SC3` | main | ❌ | — | footystats | Ago–Mai |
| 10 | 🇩🇪 | Bundesliga | `GER_BL` | `D1` | main | `Bundesliga` | 20 | understat | Ago–Mai |
| 11 | 🇩🇪 | 2. Bundesliga | `GER_B2` | `D2` | main | ❌ | 33 | fbref | Ago–Mai |
| 12 | 🇮🇹 | Serie A | `ITA_SA` | `I1` | main | `Serie_A` | 11 | understat | Ago–Mai |
| 13 | 🇮🇹 | Serie B | `ITA_SB` | `I2` | main | ❌ | 18 | fbref | Ago–Mai |
| 14 | 🇪🇸 | La Liga | `ESP_PD` | `SP1` | main | `La_Liga` | 12 | understat | Ago–Mai |
| 15 | 🇪🇸 | La Liga 2 | `ESP_SD` | `SP2` | main | ❌ | 17 | fbref | Ago–Mai |
| 16 | 🇫🇷 | Ligue 1 | `FRA_L1` | `F1` | main | `Ligue_1` | 13 | understat | Ago–Mai |
| 17 | 🇫🇷 | Ligue 2 | `FRA_L2` | `F2` | main | ❌ | 60 | fbref | Ago–Mai |

### Tier 2 — Europeias Adicionais (5 ligas)

| # | País | Liga | Código | FD Code | FD Type | FBRef ID | xG Source | Formato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18 | 🇳🇱 | Eredivisie | `NED_ED` | `N1` | main | 23 | fbref | Ago–Mai |
| 19 | 🇧🇪 | Pro League | `BEL_PL` | `B1` | main | 37 | fbref | Ago–Mai |
| 20 | 🇵🇹 | Primeira Liga | `POR_PL` | `P1` | main | 32 | fbref | Ago–Mai |
| 21 | 🇹🇷 | Süper Lig | `TUR_SL` | `T1` | main | 26 | fbref | Ago–Mai |
| 22 | 🇬🇷 | Super League | `GRE_SL` | `G1` | main | 27 | fbref | Ago–Mai |

### Tier 3 — Extras (4 ligas)

| # | País | Liga | Código | FD Code | FD Type | FBRef ID | xG Source | Formato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 23 | 🇧🇷 | Brasileirão Série A | `BRA_SA` | `BRA` | extra | 24 | fbref | Abr–Dez |
| 24 | 🇲🇽 | Liga MX | `MEX_LM` | `MEX` | extra | 31 | fbref | Jul–Mai‡ |
| 25 | 🇦🇹 | Bundesliga | `AUT_BL` | `AUT` | extra | 56 | fbref | Jul–Mai |
| 26 | 🇨🇭 | Super League | `SWI_SL` | `SWZ` | extra | 57 | fbref | Jul–Mai |

> ‡ Liga MX opera em formato Apertura/Clausura com playoffs.
> 

**Uso dos tiers:**

- **Tier 1**: todas as fontes, modelagem completa, prioridade no schedule
- **Tier 2**: todas as fontes, modelagem completa, xG via FBRef
- **Tier 3**: todas as fontes, modelagem completa, CSV Football-Data pode ter menos colunas de odds

### 3.2 Cobertura de xG

UNDERSTAT — xG granular por chute (5 ligas):
ENG_PL, ESP_PD, GER_BL, ITA_SA, FRA_L1

FBREF — xG por jogo (19 ligas):
ENG_CH, ENG_L1, ENG_L2, ENG_NL, SCO_PL, SCO_CH
GER_B2, ITA_SB, ESP_SD, FRA_L2
NED_ED, BEL_PL, POR_PL, TUR_SL, GRE_SL
BRA_SA, MEX_LM, AUT_BL, SWI_SL

FOOTYSTATS — xG básico, fallback (2 ligas):
SCO_L1, SCO_L2

### 3.3 Season IDs Footystats — Completo

### England

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| Premier League | `ENG_PL` | 6135 | 7704 | 9660 | 12325 | 15050 |
| Championship | `ENG_CH` | 6089 | 7593 | 9663 | 12451 | 14930 |
| League One | `ENG_L1` | 6017 | 7570 | 9582 | 12446 | 14934 |
| League Two | `ENG_L2` | 6015 | 7574 | 9581 | 12422 | 14935 |
| National League | `ENG_NL` | 6088 | 7729 | 9700 | 12622 | 15657 |

### Scotland

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| Premiership | `SCO_PL` | 5992 | 7494 | 9636 | 12455 | 15000 |
| Championship | `SCO_CH` | 5991 | 7498 | 9637 | 12456 | 15061 |
| League One | `SCO_L1` | 5976 | 7505 | 9639 | 12474 | 14943 |
| League Two | `SCO_L2` | 5974 | 7506 | 9638 | 12453 | 15209 |

### Germany

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| Bundesliga | `GER_BL` | 6192 | 7664 | 9655 | 12529 | 14968 |
| 2. Bundesliga | `GER_B2` | 6020 | 7499 | 9656 | 12528 | 14931 |

### Italy

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| Serie A | `ITA_SA` | 6198 | 7608 | 9697 | 12530 | 15068 |
| Serie B | `ITA_SB` | 6205 | 7864 | 9808 | 12621 | 15632 |

### Spain

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| La Liga | `ESP_PD` | 6211 | 7665 | 9665 | 12316 | 14956 |
| La Liga 2 | `ESP_SD` | 6120 | 7592 | 9675 | 12467 | 15066 |

### France

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| Ligue 1 | `FRA_L1` | 6019 | 7500 | 9674 | 12337 | 14932 |
| Ligue 2 | `FRA_L2` | 6018 | 7501 | 9621 | 12338 | 14954 |

### Netherlands, Belgium, Portugal, Turkey, Greece

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| Eredivisie | `NED_ED` | 5951 | 7482 | 9653 | 12322 | 14936 |
| Pro League | `BEL_PL` | 6079 | 7544 | 9577 | 12137 | 14937 |
| Primeira Liga | `POR_PL` | 6117 | 7731 | 9984 | 12931 | 15115 |
| Süper Lig | `TUR_SL` | 6125 | 7768 | 9913 | 12641 | 14972 |
| Super League | `GRE_SL` | 6282 | 7954 | 9889 | 12734 | 15163 |

### Extras

| Liga | Código | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brasileirão Série A | `BRA_SA` | 5713 | 7097 | 9035 | 11321 | 14231 | 16544 |

| Liga | Código | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
| --- | --- | --- | --- | --- | --- | --- |
| Liga MX | `MEX_LM` | 6038 | 7425 | 9525 | 12136 | 15234 |
| Bundesliga (Áustria) | `AUT_BL` | 6008 | 7890 | 9954 | 12472 | 14923 |
| Super League (Suíça) | `SWI_SL` | 6044 | 7504 | 9580 | 12326 | 15047 |

### 3.4 Estimativas de Volume

| Métrica | Valor |
| --- | --- |
| Total de ligas | **26** |
| Países | **14** |
| Jogos por temporada (estimativa) | ~11.500 |
| Backfill 5 temporadas | **~57.500 jogos** |
| Times únicos (estimativa) | **~580** |
| Aliases para mapear | ~580 × 6 fontes = **~3.480** |
| Season IDs mapeados | **130/130 (100%)** |

---

## 4. Casas de Apostas

| Tier | Casa | Código DB | Tipo | CLV Priority | FlashScore Aliases |
| --- | --- | --- | --- | --- | --- |
| Sharp | Pinnacle | `pinnacle` | sharp | **1** | "Pinnacle", "Pinnacle Sports" |
| Exchange | Betfair Exchange | `betfair_ex` | exchange | **2** | "Betfair", "Betfair Exchange" |
| Retail Int. | Bet365 | `bet365` | retail | **3** | "bet365", "Bet365" |
| Retail Int. | 1xBet | `1xbet` | retail | — | "1xBet" |
| BR Retail | Betano | `betano` | br_retail | — | "Betano" |
| BR Retail | Sportingbet | `sportingbet` | br_retail | — | "Sportingbet" |
| BR Retail | Superbet | `superbet` | br_retail | — | "Superbet" |
| BR Retail | BetNacional | `betnacional` | br_retail | — | "BetNacional", "Bet Nacional" |
| BR Retail | EstrelaBet | `estrela_bet` | br_retail | — | "EstrelaBet", "Estrela Bet" |
| BR Retail | KTO | `kto` | br_retail | — | "KTO" |
| BR Retail | 7K | `7k` | br_retail | — | "7K" |
| BR Retail | F12 | `f12` | br_retail | — | "F12", "F12.bet" |
| BR Retail | Multibet | `multibet` | br_retail | — | "Multibet" |

**Total:** 13 casas

**Prioridade de CLV:** Pinnacle (1) → Betfair Exchange (2) → Bet365 (3). Se Pinnacle indisponível para um jogo, usa Betfair; se ambos indisponíveis, usa Bet365.

---

## 5. Mercados e Linhas

### 5.1 Full-Time (`period = 'ft'`)

| Mercado | `market_type` | `line` | Seleções (`odds_1` / `odds_x` / `odds_2`) | N° Linhas |
| --- | --- | --- | --- | --- |
| 1X2 | `1x2` | `NULL` | Home / Draw / Away | 1 |
| Over/Under | `ou` | 0.5 → 4.5 | Over / — / Under | 16 |
| Asian Handicap | `ah` | 50/50 ± 2 | Home AH / — / Away AH | 5 (dinâmico) |
| Dupla Chance | `dc` | `NULL` | 1X / 12 / X2 | 1 |
| Draw No Bet | `dnb` | `NULL` | Home / — / Away | 1 |
| BTTS | `btts` | `NULL` | Yes / — / No | 1 |

### 5.2 Half-Time (`period = 'ht'`)

| Mercado | `market_type` | `line` | Seleções | N° Linhas |
| --- | --- | --- | --- | --- |
| 1X2 HT | `1x2_ht` | `NULL` | Home / Draw / Away | 1 |
| Over/Under HT | `ou_ht` | 0.5 → 2.5 | Over / — / Under | 9 |
| Asian Handicap HT | `ah_ht` | 50/50 | Home AH / — / Away AH | 1 |

### 5.3 Linhas Over/Under FT

0.5, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5

### 5.4 Linhas Over/Under HT

0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5

### 5.5 Asian Handicap — Lógica da Linha 50/50

```python
def find_balanced_line(ah_odds: list[dict]) -> float:
    """
    Encontra a linha onde a diferença entre odds home/away é mínima.
    Input: [{'line': -0.5, 'home': 1.92, 'away': 1.96}, ...]
    Output: linha cujo |home - away| é mínimo
    """
    best = min(ah_odds, key=lambda x: abs(x['home'] - x['away']))
    return best['line']

def get_ah_lines_to_collect(balanced: float) -> list[float]:
    """Coleta 50/50 + 2 acima (favor home) + 2 abaixo (favor away)."""
    step = 0.25
    return sorted([balanced + (i * step) for i in range(-2, 3)])
```

### 5.6 Convenção de Sinal (AH)

Linha NEGATIVA = handicap contra o home (home precisa vencer por X+)
Linha POSITIVA = handicap a favor do home (home pode perder por até X)

---

## 6. Schedule de Coleta

### 6.1 Jobs Definidos

| Job ID | Cron / Trigger | Fonte | Ação |
| --- | --- | --- | --- |
| `odds_standard` | `0 6,10,14,20 * * *` BRT | FlashScore | Odds de jogos D+1 a D+7 |
| `odds_gameday_hourly` | Dinâmico: 1x/hora (8h–23h BRT, jogos do dia) | FlashScore | Odds de jogos de hoje não iniciados |
| `odds_prematch_30` | Dinâmico: T-30min | FlashScore | Snapshot pré-jogo |
| `odds_prematch_2` | Dinâmico: T-2min | FlashScore | Snapshot final (marca candidato a closing) |
| `results_postmatch` | Dinâmico: T+2h30 | Footystats | Resultado + stats + mark `is_closing` |
| `xg_postround` | `0 6 * * *` BRT | Understat + FBRef | xG da rodada anterior |
| `lineups_prematch` | Dinâmico: T-60min | API-Football | Escalações confirmadas |
| `fixtures_weekly` | `0 5 * * 1` BRT (segundas) | Footystats | Calendário semanal |
| `csv_weekly` | `0 4 * * 1` BRT (segundas) | Football-Data | CSV bulk semanal |
| `odds_api_validation` | A cada 3h (dias com jogos) | The Odds API | Validação cruzada Pinnacle |
| `health_check` | A cada 5min | Todas | Verificação de disponibilidade |
| `reset_daily_keys` | `0 0 * * *` UTC | — | Reseta `usage_today` em `api_keys` |

### 6.2 Volume Estimado

| Período | Jogos/dia |
| --- | --- |
| Meio de semana normal | ~40–60 |
| Final de semana | ~100–150 |
| Pico (todas as ligas jogando) | ~180 |

### 6.3 Priorização

Quando fila cheia (>100 jogos/dia), FlashScore prioriza por tier:

1. **Tier 1** — coleta integral (todos os mercados, todas as linhas)
2. **Tier 2** — coleta integral
3. **Tier 3** — coleta integral, mas pode atrasar se fila estiver cheia

### 6.4 Jobs Dinâmicos (T-X)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import timedelta

scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")

async def schedule_gameday_jobs():
    """Roda 00:30 BRT. Agenda jobs dinâmicos para cada jogo do dia."""
    today_matches = await db.fetch_today_matches()

    for match in today_matches:
        kickoff = match['kickoff']
        match_id = match['match_id']

        # T-60min: escalações
        scheduler.add_job(
            collect_lineups, 'date',
            run_date=kickoff - timedelta(minutes=60),
            args=[match_id],
            id=f"lineups_{match_id}",
            replace_existing=True,
            misfire_grace_time=300
        )

        # T-30min: snapshot pré-jogo
        scheduler.add_job(
            collect_odds_snapshot, 'date',
            run_date=kickoff - timedelta(minutes=30),
            args=[match_id, 'prematch_30'],
            id=f"odds_pre30_{match_id}",
            replace_existing=True,
            misfire_grace_time=120
        )

        # T-2min: snapshot final
        scheduler.add_job(
            collect_odds_snapshot, 'date',
            run_date=kickoff - timedelta(minutes=2),
            args=[match_id, 'prematch_2'],
            id=f"odds_pre2_{match_id}",
            replace_existing=True,
            misfire_grace_time=60
        )

        # T+2h30: resultados + stats + mark closing
        scheduler.add_job(
            collect_postmatch, 'date',
            run_date=kickoff + timedelta(hours=2, minutes=30),
            args=[match_id],
            id=f"results_{match_id}",
            replace_existing=True,
            misfire_grace_time=1800
        )

scheduler.add_job(schedule_gameday_jobs, 'cron', hour=0, minute=30)
```

### 6.5 Odds Gameday Hourly

```python
async def odds_gameday_hourly():
    """Coleta odds de todos os jogos do dia que ainda não começaram."""
    matches = await db.fetch_today_matches_not_started()

    for match in matches:
        kickoff = match['kickoff']
        now = datetime.now(UTC)
        # Evita conflito com prematch_30 (já cobre T-35min em diante)
        if (kickoff - now) > timedelta(minutes=35):
            await collect_all_odds(match['match_id'], job_type='gameday_hourly')

scheduler.add_job(
    odds_gameday_hourly, 'cron',
    hour='8-23', minute=0
)
```

### 6.6 Key Manager

```python
class KeyManager:
    def __init__(self, db):
        self.db = db

    async def get_key(self, service: str) -> str:
        """Retorna key com menor uso que não atingiu limite."""
        keys = await self.db.fetch(
            """SELECT key_id, key_value, usage_today, usage_month,
                      limit_daily, limit_monthly
               FROM api_keys
               WHERE service = $1 AND is_active = TRUE
               ORDER BY usage_today ASC""",
            service
        )

        for key in keys:
            daily_ok = key['limit_daily'] is None or key['usage_today'] < key['limit_daily']
            monthly_ok = key['limit_monthly'] is None or key['usage_month'] < key['limit_monthly']

            if daily_ok and monthly_ok:
                await self.db.execute(
                    """UPDATE api_keys
                       SET usage_today = usage_today + 1,
                           usage_month = usage_month + 1,
                           last_used_at = NOW()
                       WHERE key_id = $1""",
                    key['key_id']
                )
                return key['key_value']

        raise NoKeysAvailableError(f"Todas as keys de {service} atingiram o limite")

    async def reset_daily(self):
        await self.db.execute(
            "UPDATE api_keys SET usage_today = 0, last_reset_at = NOW()"
        )

    async def reset_monthly(self):
        await self.db.execute(
            "UPDATE api_keys SET usage_month = 0"
        )
```

---

## 7. Contratos de Interface

### 7.1 BaseCollector (classe abstrata)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

class CollectStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"

@dataclass
class CollectResult:
    source: str
    job_type: str
    job_id: str
    status: CollectStatus
    started_at: datetime
    finished_at: datetime
    records: List[Dict[str, Any]]
    records_collected: int = 0
    records_new: int = 0
    records_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseCollector(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    async def collect(self, **kwargs) -> CollectResult:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

    def generate_job_id(self, job_type: str) -> str:
        return f"{self.source_name}_{job_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
```

### 7.2 FlashScore Odds Collector

**Input:**

```python
@dataclass
class FlashScoreOddsInput:
    match_id: str               # UUID interno
    flashscore_id: str          # ID FlashScore (ex: "8jQr1kNM")
    markets: List[str]          # ['1x2', 'ou', 'ah', 'dc', 'dnb', 'btts', '1x2_ht', 'ou_ht', 'ah_ht']
    bookmakers_filter: List[str]
```

**Output (cada registro):**

```python
@dataclass
class OddsRecord:
    time: datetime              # UTC
    match_id: str               # UUID interno
    bookmaker_name: str         # Nome raw FlashScore
    market_type: str
    line: Optional[float]
    period: str                 # 'ft' ou 'ht'
    odds_1: Optional[float]
    odds_x: Optional[float]
    odds_2: Optional[float]
    source: str = "flashscore"
```

**Transformação pré-INSERT:**

```python
def transform_odds_record(record: OddsRecord, db) -> dict:
    bookmaker_id = db.resolve_bookmaker(record.bookmaker_name)

    inv_sum = 0
    for odds in [record.odds_1, record.odds_x, record.odds_2]:
        if odds and odds > 1.0:
            inv_sum += 1.0 / odds
    overround = round(inv_sum - 1.0, 4) if inv_sum > 0 else None

    content_hash = compute_hash(
        record.match_id, bookmaker_id, record.market_type,
        record.line, record.period, record.odds_1, record.odds_x, record.odds_2
    )

    return {
        "time": record.time,
        "match_id": record.match_id,
        "bookmaker_id": bookmaker_id,
        "market_type": record.market_type,
        "line": record.line,
        "period": record.period,
        "odds_1": record.odds_1,
        "odds_x": record.odds_x,
        "odds_2": record.odds_2,
        "overround": overround,
        "is_opening": False,   # Determinado via mark_opening()
        "is_closing": False,   # Determinado via mark_closing_odds()
        "source": "flashscore",
        "content_hash": content_hash
    }
```

### 7.3 Footystats Matches Collector

**Input:**

```python
@dataclass
class FootystatsInput:
    season_id: int              # ID Footystats (ex: 15050)
    league_code: str
    date_filter: Optional[str]  # YYYY-MM-DD ou None (backfill)
```

**Output (cada registro):**

```python
@dataclass
class MatchStatsRecord:
    footystats_id: int
    home_name: str
    away_name: str
    kickoff_unix: int
    matchday: Optional[int]
    status: str
    ft_home: Optional[int]
    ft_away: Optional[int]
    ht_home: Optional[int]
    ht_away: Optional[int]
    goals_home_minutes: Optional[str]
    goals_away_minutes: Optional[str]
    xg_home: Optional[float]
    xg_away: Optional[float]
    shots_home: Optional[int]
    shots_away: Optional[int]
    shots_on_target_home: Optional[int]
    shots_on_target_away: Optional[int]
    shots_off_target_home: Optional[int]
    shots_off_target_away: Optional[int]
    possession_home: Optional[float]
    possession_away: Optional[float]
    corners_home_ft: Optional[int]
    corners_away_ft: Optional[int]
    corners_home_ht: Optional[int]
    corners_away_ht: Optional[int]
    yellow_cards_home_ft: Optional[int]
    yellow_cards_away_ft: Optional[int]
    red_cards_home_ft: Optional[int]
    red_cards_away_ft: Optional[int]
    cards_home_ht: Optional[int]
    cards_away_ht: Optional[int]
    source: str = "footystats"
```

**Mapeamento Footystats → DB:**

```python
FOOTYSTATS_FIELD_MAP = {
    "id":                       "footystats_id",
    "date_unix":                "kickoff_unix",
    "home_name":                "home_name",
    "away_name":                "away_name",
    "game_week":                "matchday",
    "status":                   "status",
    "homeGoalCount":            "ft_home",
    "awayGoalCount":            "ft_away",
    "homeHTGoalCount":          "ht_home",
    "awayHTGoalCount":          "ht_away",
    "homeGoals":                "goals_home_minutes",
    "awayGoals":                "goals_away_minutes",
    "team_a_xg":                "xg_home",
    "team_b_xg":                "xg_away",
    "team_a_shots":             "shots_home",
    "team_b_shots":             "shots_away",
    "team_a_shotsOnTarget":     "shots_on_target_home",
    "team_b_shotsOnTarget":     "shots_on_target_away",
    "team_a_shotsOffTarget":    "shots_off_target_home",
    "team_b_shotsOffTarget":    "shots_off_target_away",
    "team_a_possession":        "possession_home",
    "team_b_possession":        "possession_away",
    "team_a_corners":           "corners_home_ft",
    "team_b_corners":           "corners_away_ft",
    "team_a_yellow_cards":      "yellow_cards_home_ft",
    "team_b_yellow_cards":      "yellow_cards_away_ft",
    "team_a_red_cards":         "red_cards_home_ft",
    "team_b_red_cards":         "red_cards_away_ft",
}
```

**Transformações:**

```python
def transform_goals_minutes(raw: str) -> list:
    """'23,67,89' → [23, 67, 89] | '' → None | None → None"""
    if not raw or raw.strip() == "":
        return None
    try:
        return [int(m.strip()) for m in raw.split(",") if m.strip()]
    except (ValueError, AttributeError):
        return None

def transform_footystats_value(field_name: str, raw_value) -> any:
    """Footystats usa -1 para indisponível."""
    if raw_value == -1 or raw_value == "-1":
        return None
    if field_name in ("goals_home_minutes", "goals_away_minutes"):
        return transform_goals_minutes(raw_value)
    if field_name in ("xg_home", "xg_away"):
        try:
            val = float(raw_value)
            return val if val >= 0 else None
        except (TypeError, ValueError):
            return None
    return raw_value
```

### 7.4 Football-Data CSV Collector

**Input:**

```python
@dataclass
class FootballDataInput:
    league_code: str            # 'E0', 'SP1', 'BRA', 'AUT', etc.
    season: str                 # '2425' para 2024/2025 (main) ou None (extra)
    fd_type: str                # 'main' ou 'extra'
    # Main: {base_url}/mmz4281/{season}/{league_code}.csv
    # Extra: {base_url}/new/{league_code}.csv (arquivo único multi-temporada)
```

**Output (cada registro):**

```python
@dataclass
class FootballDataRecord:
    division: str
    date: str                   # DD/MM/YYYY
    time: Optional[str]         # HH:MM
    home_team: str
    away_team: str
    ft_home: int
    ft_away: int
    ft_result: str              # H/D/A
    ht_home: Optional[int]
    ht_away: Optional[int]
    ht_result: Optional[str]
    pinnacle_home: Optional[float]
    pinnacle_draw: Optional[float]
    pinnacle_away: Optional[float]
    pinnacle_ou25_over: Optional[float]
    pinnacle_ou25_under: Optional[float]
    bet365_home: Optional[float]
    bet365_draw: Optional[float]
    bet365_away: Optional[float]
    bet365_ou25_over: Optional[float]
    bet365_ou25_under: Optional[float]
    source: str = "football_data"
```

> **Nota:** CSVs de extra leagues (BRA, MEX, AUT, SWZ) podem ter menos colunas de odds. Colunas ausentes → `NULL`.
> 

### 7.5 Understat xG Collector

**Input:**

```python
@dataclass
class UnderstatInput:
    league_name: str    # 'EPL', 'La_Liga', 'Bundesliga', 'Serie_A', 'Ligue_1'
    season: int         # 2024 para 2024/2025
```

**Output:**

```python
@dataclass
class UnderstatMatchRecord:
    understat_id: int
    home_name: str
    away_name: str
    xg_home: float
    xg_away: float
    ft_home: int
    ft_away: int
    date: str
    source: str = "understat"
```

### 7.6 FBRef Collector

**Input:**

```python
@dataclass
class FBRefInput:
    fbref_comp_id: int  # ID numérico do FBRef (ex: 9 para PL)
    season: str         # '2024-2025'
```

**Output:**

```python
@dataclass
class FBRefMatchRecord:
    home_players: List[Dict[str, Any]]
    away_players: List[Dict[str, Any]]
    aggregated: Dict[str, Any]  # xg_home, xg_away, progressive_passes_home, etc.
    source: str = "fbref"
```

### 7.7 The Odds API Collector

**Input:**

```python
@dataclass
class OddsApiInput:
    sport: str = "soccer"
    regions: str = "eu,uk"
    markets: str = "h2h,spreads,totals"
    bookmakers: str = "pinnacle,betfair,bet365"
```

**Output:**

```python
@dataclass
class OddsApiRecord:
    odds_api_id: str
    sport: str
    home_team: str
    away_team: str
    commence_time: str
    bookmaker: str
    market: str
    outcomes: List[dict]
    last_update: str
    source: str = "odds_api"
```

### 7.8 API-Football Collector

**Input:**

```python
@dataclass
class ApiFootballInput:
    fixture_id: int
```

**Output:**

```python
@dataclass
class LineupRecord:
    api_football_fixture_id: int
    team_name: str
    formation: str
    players: List[dict]
    source: str = "api_football"
```

---

## 8. Regras de Negócio

### 8.1 Determinação de `is_opening`

```python
async def mark_opening(match_id, bookmaker_id, market_type, line, period) -> bool:
    """Primeiro registro para a combinação = opening."""
    exists = await db.fetch_val(
        """SELECT EXISTS(
            SELECT 1 FROM odds_history
            WHERE match_id = $1 AND bookmaker_id = $2 AND market_type = $3
            AND COALESCE(line, 0) = COALESCE($4, 0) AND period = $5
        )""",
        match_id, bookmaker_id, market_type, line, period
    )
    return not exists
```

### 8.2 Determinação de `is_closing`

```python
async def mark_closing_odds(match_id: UUID):
    """
    Roda no job results_postmatch (T+2h30).
    Marca o último registro antes do kickoff como closing.
    """
    kickoff = await db.fetch_val(
        "SELECT kickoff FROM matches WHERE match_id = $1", match_id
    )

    await db.execute("""
        WITH last_before_kickoff AS (
            SELECT DISTINCT ON (bookmaker_id, market_type, COALESCE(line, 0), period)
                ctid
            FROM odds_history
            WHERE match_id = $1 AND time < $2
            ORDER BY bookmaker_id, market_type, COALESCE(line, 0), period, time DESC
        )
        UPDATE odds_history
        SET is_closing = TRUE
        WHERE ctid IN (SELECT ctid FROM last_before_kickoff)
    """, match_id, kickoff)
```

### 8.3 Status de Match

```
scheduled → live → finished
scheduled → postponed → scheduled (reagendado) → live → finished
scheduled → cancelled
```

### 8.4 Tratamento de Valores Especiais

| Fonte | Valor Raw | Significado | Ação |
| --- | --- | --- | --- |
| Footystats | `-1` | Indisponível | → `NULL` |
| Footystats | `""` (vazia) | Sem gols | `goals_*_minutes = NULL` |
| Footystats | `"23,67,89"` | Minutos dos gols | → `[23, 67, 89]` (JSONB) |
| Footystats | xG = `0.00` | xG zero (válido) | Manter `0.00` |
| FlashScore | Odds = `"-"` ou `""` | Não disponível | Não inserir |
| FlashScore | Odds = `"1.00"` | Sem retorno | Não inserir |
| FlashScore | Casa ausente no mercado | Não oferece | Não inserir |
| Football-Data | Coluna vazia / `NaN` | Indisponível | → `NULL` |
| Understat | xG = `None` | Não processado | Não inserir, retry dia seguinte |
| FBRef | xG vazia | Sem dados | → `NULL` |
| The Odds API | Bookmaker ausente | Não cobre o jogo | Não inserir |
| API-Football | `lineups: []` | Não confirmada | Não inserir, retry T-30min |

### 8.5 Overround

```python
def calculate_overround(odds_1, odds_x=None, odds_2=None) -> float:
    """Calcula o overround (margem da casa) a partir das odds."""
    inv_sum = 0.0
    for odds in [odds_1, odds_x, odds_2]:
        if odds is not None and odds > 1.0:
            inv_sum += 1.0 / odds
    return round(inv_sum - 1.0, 4)
```

### 8.6 Content Hash (Dedup)

```python
import hashlib

def compute_content_hash(match_id, bookmaker_id, market_type, line, period,
                          odds_1, odds_x, odds_2) -> str:
    """SHA-256 do conteúdo para deduplicação."""
    parts = [
        str(match_id), str(bookmaker_id), str(market_type),
        str(line if line is not None else "NULL"), str(period),
        f"{odds_1:.4f}" if odds_1 else "NULL",
        f"{odds_x:.4f}" if odds_x else "NULL",
        f"{odds_2:.4f}" if odds_2 else "NULL",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
```

**Lógica de dedup no INSERT:**

```python
async def insert_odds_if_new(record: dict, db) -> bool:
    """Se hash igual ao último registro da mesma combinação → skip. Se diferente → insert."""
    last_hash = await db.fetch_val(
        """SELECT content_hash FROM odds_history
           WHERE match_id = $1 AND bookmaker_id = $2 AND market_type = $3
           AND COALESCE(line, 0) = COALESCE($4, 0) AND period = $5
           ORDER BY time DESC LIMIT 1""",
        record['match_id'], record['bookmaker_id'], record['market_type'],
        record['line'], record['period']
    )
    if last_hash == record['content_hash']:
        return False  # Odds não mudaram → skip
    await db.insert('odds_history', record)
    return True  # Nova entrada registrada
```

---

## 9. Normalização e Dedup

### 9.1 Team Resolver

```python
class TeamResolver:
    def __init__(self, db):
        self.db = db
        self._cache: Dict[tuple, Optional[int]] = {}

    async def resolve(self, source: str, raw_name: str) -> Optional[int]:
        """Resolve nome raw → team_id canônico via cache + DB."""
        key = (source, raw_name.strip())
        if key in self._cache:
            return self._cache[key]

        team_id = await self.db.fetch_val(
            "SELECT team_id FROM team_aliases WHERE source=$1 AND alias_name=$2",
            source, raw_name.strip()
        )
        self._cache[key] = team_id

        if team_id is None:
            # Registra alias desconhecido para revisão
            await self.db.execute(
                """INSERT INTO unknown_aliases (source, raw_name, first_seen)
                   VALUES ($1, $2, NOW())
                   ON CONFLICT (source, raw_name) DO NOTHING""",
                source, raw_name
            )
            await send_alert(f"⚠️ Alias desconhecido: '{raw_name}' ({source})")

        return team_id
```

### 9.2 Match Resolver

```python
class MatchResolver:
    def __init__(self, db, team_resolver: TeamResolver):
        self.db = db
        self.team_resolver = team_resolver

    async def resolve(self, league_id, home_name, away_name,
                      kickoff_date, source) -> Optional[UUID]:
        """Resolve match_id via team aliases + data do jogo."""
        home_id = await self.team_resolver.resolve(source, home_name)
        away_id = await self.team_resolver.resolve(source, away_name)

        if home_id is None or away_id is None:
            return None

        match_id = await self.db.fetch_val(
            """SELECT match_id FROM matches
               WHERE league_id = $1 AND home_team_id = $2 AND away_team_id = $3
               AND kickoff::date = $4""",
            league_id, home_id, away_id, kickoff_date
        )
        return match_id
```

### 9.3 Bookmaker Resolver

```python
BOOKMAKER_ALIASES = {
    "Pinnacle": "pinnacle", "Pinnacle Sports": "pinnacle",
    "bet365": "bet365", "Bet365": "bet365",
    "Betfair Exchange": "betfair_ex", "Betfair": "betfair_ex",
    "1xBet": "1xbet",
    "Betano": "betano",
    "Sportingbet": "sportingbet",
    "Superbet": "superbet",
    "BetNacional": "betnacional", "Bet Nacional": "betnacional",
    "EstrelaBet": "estrela_bet", "Estrela Bet": "estrela_bet",
    "KTO": "kto",
    "7K": "7k",
    "F12.bet": "f12", "F12": "f12",
    "Multibet": "multibet",
}
```

---

## 10. Backfill Histórico

### 10.1 Pipeline Completo

```
ETAPA 1 — Football-Data CSV (seed)
│  ~130 CSVs (26 ligas × 5 temporadas)
│  Main: {base_url}/mmz4281/{season}/{league_code}.csv
│  Extra: {base_url}/new/{league_code}.csv (multi-temporada)
│  Gera: matches + odds_history (Pinnacle/B365 1X2 + OU 2.5 onde disponível)
│  Gera: team_aliases_seed.csv → REVISÃO MANUAL
│  Tempo: ~10 min
│
ETAPA 2 — ⏸️ Revisão de Aliases (Marcelo)
│  CSV com ~580 times × mapeamento canônico (nome Bet365)
│  Tempo: 1–1.5 dias
│
ETAPA 3 — Footystats API (stats completas)
│  26 ligas × 5 temporadas = 130 season requests
│  Enriquece: match_stats (xG, chutes, escanteios, cartões HT/FT, posse)
│  Atualiza: matches (HT scores, minutos gols, footystats_id)
│  Tempo: ~40 min (key ilimitada)
│
ETAPA 4 — Understat (xG granular Top 5)
│  5 ligas × 5 temporadas = 25 requests
│  Tempo: ~3h (rate limiting)
│
ETAPA 5 — FBRef (xG 19 ligas adicionais)
│  19 ligas × 5 temporadas = 95 season pages
│  Rate limit: 10 req/min
│  Tempo: ~14h
│
TOTAL: ~24h supervisionadas (~1.5 dias úteis)
```

### 10.2 Seed de Aliases (geração do CSV)

```python
def generate_alias_seed_csv(csv_dir: str, output_path: str):
    """Gera CSV com todos os times encontrados nos CSVs do Football-Data para revisão manual."""
    records = []
    for csv_file in sorted(Path(csv_dir).glob("*.csv")):
        try:
            df = pd.read_csv(csv_file, encoding='utf-8', on_bad_lines='skip')
        except:
            df = pd.read_csv(csv_file, encoding='latin-1', on_bad_lines='skip')

        if 'HomeTeam' not in df.columns:
            continue

        div = df['Div'].iloc[0] if 'Div' in df.columns else csv_file.stem

        for team in sorted(set(df['HomeTeam'].dropna().unique()) |
                           set(df['AwayTeam'].dropna().unique())):
            records.append({
                'football_data_name': team.strip(),
                'canonical_name_bet365': '',    # Marcelo preenche
                'country': '',                  # Marcelo preenche
                'league_code': div,
            })

    result = pd.DataFrame(records).drop_duplicates(subset=['football_data_name', 'league_code'])
    result.to_csv(output_path, index=False)
```

---

## 11. Resiliência e Fallback

### 11.1 Retry com Exponential Backoff

```python
def retry_with_backoff(max_retries=4, initial_delay=30, max_delay=300, alert_on_failure=True):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        if alert_on_failure:
                            await send_alert(
                                f"❌ {func.__name__} falhou após {max_retries+1} tentativas: {e}",
                                level="error"
                            )
                        raise
                    jitter = delay * 0.1 * (2 * random.random() - 1)
                    await asyncio.sleep(min(delay + jitter, max_delay))
                    delay *= 2
        return wrapper
    return decorator
```

### 11.2 Rate Limits por Fonte

| Fonte | Max Requests | Janela |
| --- | --- | --- |
| FlashScore | 30 req | 60s |
| FBRef | 10 req | 60s |
| Understat | 20 req | 60s |
| Footystats | Ilimitada | — |
| The Odds API | 500 req/mês por key × 5 keys | Mensal |
| API-Football | 100 req/dia por key × 7 keys | Diário |

### 11.3 Regras de Fallback

1. **FlashScore down** → The Odds API assume coleta de odds (Pinnacle/Bet365 apenas)
2. **Footystats down** → API-Football para fixtures; resultados aguardam até Footystats voltar
3. **Understat down** → Retry dia seguinte; xG via FBRef como alternativa (menos granular)
4. **FBRef down** → Footystats xG como fallback (básico)
5. **API-Football down** → FlashScore para escalações (menos confiável)
6. **The Odds API down** → Sem validação cruzada (não bloqueia pipeline)

---

## 12. Configuração e Estrutura de Código

### 12.1 Estrutura de Diretórios

```
src/
├── collectors/
│   ├── __init__.py
│   ├── base.py                       # BaseCollector + CollectResult
│   ├── flashscore/
│   │   ├── __init__.py
│   │   ├── driver.py                 # Selenium + cookie handler
│   │   ├── parser.py                 # HTML → dict
│   │   ├── odds_collector.py         # 13 casas × 9 mercados
│   │   └── selectors.py             # CSS/XPath ISOLADOS (fácil manutenção)
│   ├── footystats/
│   │   ├── __init__.py
│   │   ├── api_client.py             # httpx client
│   │   ├── matches_collector.py      # Resultados + stats
│   │   ├── fixtures_collector.py     # Calendário
│   │   └── backfill.py               # Backfill de temporadas
│   ├── football_data/
│   │   ├── __init__.py
│   │   └── csv_collector.py          # Download + parse + seed aliases
│   ├── fbref/
│   │   ├── __init__.py
│   │   ├── scraper.py                # requests + BS4
│   │   └── parser.py
│   ├── understat/
│   │   ├── __init__.py
│   │   └── xg_collector.py           # lib understat (async)
│   ├── odds_api/
│   │   ├── __init__.py
│   │   └── api_collector.py          # Multi-key (5 contas)
│   └── api_football/
│       ├── __init__.py
│       └── api_collector.py          # Multi-key (7 contas)
├── normalizer/
│   ├── __init__.py
│   ├── team_resolver.py              # alias → team_id canônico
│   ├── match_resolver.py             # Dedup cross-source
│   ├── odds_normalizer.py            # Formato + overround
│   └── dedup.py                      # SHA-256
├── scheduler/
│   ├── __init__.py
│   ├── jobs.py                       # Definição de todos os jobs
│   └── key_manager.py                # Rotação multi-key + reset diário/mensal
├── config/
│   ├── sources.yaml
│   ├── bookmakers.yaml
│   ├── leagues.yaml                  # Liga → IDs por fonte
│   └── markets.yaml                  # Mercados × linhas
├── alerts/
│   └── telegram_mini.py              # Alertas mínimos M1
└── tests/
    ├── test_footystats.py
    ├── test_flashscore.py
    ├── test_normalizer.py
    └── test_dedup.py
```

### 12.2 Tech Stack

| Componente | Tecnologia |
| --- | --- |
| Linguagem | Python 3.11+ |
| HTTP client | `httpx` (async) |
| Scraping FlashScore | Selenium + undetected-chromedriver |
| Scraping FBRef | `requests` + `beautifulsoup4` |
| Understat | `understat` (lib Python async) |
| Banco de dados | PostgreSQL 16 + TimescaleDB |
| Driver DB | `asyncpg` |
| Scheduler | APScheduler (AsyncIOScheduler) |
| Alertas | Telegram Bot API (httpx) |
| CSV parsing | `pandas` |
| Hash | `hashlib` (SHA-256) |

---

## 13. Monitoramento e Alertas

### 13.1 Health Check (a cada 5min)

Verifica disponibilidade de todas as fontes. Alerta via Telegram se:

- Fonte indisponível por >15min
- Key de API atingiu >80% do limite
- Job falhou (status = `failed` no `ingestion_log`)
- Alias desconhecido encontrado

### 13.2 Níveis de Alerta

| Nível | Trigger | Canal |
| --- | --- | --- |
| `info` | Job concluído com sucesso, stats de coleta | Log apenas |
| `warning` | Alias desconhecido, key >80% limite, fonte lenta | Telegram |
| `error` | Job falhou após retries, fonte down >15min | Telegram (urgente) |
| `critical` | Todas as keys esgotadas, banco indisponível | Telegram (urgente) |

---

## 14. Critérios de Aceite

| # | Critério | Métrica |
| --- | --- | --- |
| 1 | 6 fontes ativas | Health check OK simultâneo |
| 2 | Backfill completo | `matches` > 50.000 rows |
| 3 | Stats preenchidas | `match_stats` > 45.000 rows com xG, chutes, escanteios |
| 4 | Odds históricas | `odds_history` > 300.000 rows (seed Football-Data) |
| 5 | Schedule 48h | `ingestion_log` sem `failed` por 48h |
| 6 | Dedup | Zero duplicatas (query de verificação) |
| 7 | Normalização | 100% dos times mapeados (~580 times × 6 fontes) |
| 8 | Fallback | FlashScore off → The Odds API assume |
| 9 | Multi-key | 7 keys API-Football + 5 keys Odds API rotacionando |
| 10 | 13 casas | Pinnacle + Bet365 + 3+ BR coletadas para jogos do dia |
| 11 | HT/FT stats | Campos HT preenchidos onde Footystats disponibiliza |
| 12 | Minutos dos gols | `goals_home_minutes` / `goals_away_minutes` preenchidos |

---

## 15. Estimativas

### 15.1 Tempo de Implementação

| Subtask | Dias |
| --- | --- |
| Schema DDL + indexes + hypertable + seeds | 2 |
| Normalizer (teams, matches, dedup) | 2 |
| Football-Data CSV collector + alias seed CSV | 2 |
| Footystats collector (stats/resultados/fixtures/backfill) | 3 |
| Understat collector + backfill Top 5 | 1 |
| FBRef collector + backfill Tier 2 | 2 |
| FlashScore collector (odds 13 casas × 9 mercados) | 4 |
| The Odds API collector (5 keys) | 1 |
| API-Football collector (7 keys + escalações) | 1 |
| Scheduler (jobs + key rotation + reset diário) | 2 |
| Backfill execução supervisionada | 1.5 |
| Testes + resiliência + alertas Telegram + docs | 2 |
| **Total** | **~23.5 dias (~5 semanas)** |

### 15.2 Riscos e Mitigações

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| FlashScore muda HTML/JS | Alto | Selectors isolados em `selectors.py`; health check detecta em 5min |
| FBRef rate limit mais restritivo | Médio | Backoff adaptativo; backfill em horário de baixa |
| Footystats API instável | Alto | Retry + fallback API-Football para resultados |
| Aliases mal mapeados | Alto | `unknown_aliases` + alerta Telegram + revisão semanal |
| Keys esgotadas no pico | Médio | KeyManager com rotação; alerta a 80% do limite |
| TimescaleDB performance | Baixo | Chunks mensais; compression policy após 3 meses |

---

## Documentos Relacionados

- **`SCHEMA.md`** — DDL completo, indexes, seeds, migrations
- **`TASKS.md`** — Breakdown de implementação, dependências, ordem de execução

---