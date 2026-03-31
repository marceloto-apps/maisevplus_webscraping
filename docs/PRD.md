# PRD.md

# PRD M1 — Coleta de Dados (Ingestão) — v5 DEFINITIVO

> **Documento único e completo do Módulo 1.** Todas as decisões, schemas, contratos, regras de negócio, configs e critérios de aceite. Qualquer decisão não coberta aqui deve ser documentada como adendo antes da implementação.
> 

---

## Índice

1. [Decisões Consolidadas](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
2. [Fontes de Dados](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
3. [Ligas no Escopo](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
4. [Casas de Apostas](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
5. [Mercados e Linhas](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
6. [Schedule de Coleta](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
7. [Schema do Banco de Dados](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
8. [Contratos de Interface por Coletor](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
9. [Regras de Negócio](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
10. [Normalização e Dedup](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
11. [Backfill Histórico](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
12. [Resiliência e Fallback](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
13. [Configuração Selenium](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
14. [Arquivos de Configuração (YAML)](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
15. [Estrutura de Código](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
16. [Diagrama de Sequência](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
17. [Testes](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
18. [Monitoramento e Alertas](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
19. [Interfaces com Outros Módulos](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
20. [Critérios de Aceite](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
21. [Estimativa de Tempo](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)
22. [Riscos e Mitigações](https://www.notion.so/PRD-md-3312ae441a0680f1a0d8e08cf32d2f7e?pvs=21)

---

## 1. Decisões Consolidadas

| Ponto | Decisão |
| --- | --- |
| Stats/Resultados | Footystats API (key ilimitada) — fonte primária |
| Odds tempo real | FlashScore (Selenium) — fonte primária |
| Backfill histórico | [Football-Data.co.uk](http://football-data.co.uk/) (CSV) → Footystats (stats) → Understat/FBRef (xG) |
| xG Top 5 | Understat (granular, por chute) |
| xG demais ligas cobertas | FBRef (por jogo) |
| xG fallback | Footystats (básico, 2 ligas sem FBRef) |
| Escalações | API-Football (7 contas, 700 req/dia) |
| Validação de odds | The Odds API (5 contas, 2.500 req/mês) |
| BetExplorer | Desativada no MVP |
| CLV | Pinnacle → Betfair → Bet365 (Footystats NÃO — odds compiladas) |
| Período histórico | 2021/22 a 2025/26 (5 temporadas + atual) |
| Total de ligas | **26 ligas, 14 países** |
| Season IDs Footystats | **Todos preenchidos (130 IDs)** |
| Aliases | Seed via Football-Data CSV → revisão manual (CSV) |
| Campos NULL | Escanteios HT e Cartões HT aceitos como NULL |
| Proxies | Não no MVP |
| Timezone | TIMESTAMPTZ (UTC interno), conversão BRT na exibição |
| Nomes canônicos | Bet365 como referência |
| Odds Footystats | **Excluídas** (compilado do site, não odds de mercado) |

---

## 2. Fontes de Dados

### 2.1 Mapa de Fontes

```
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

### 2.2 Responsabilidades

| Fonte | Tipo | Responsabilidade Principal | Responsabilidade Secundária |
| --- | --- | --- | --- |
| **Footystats API** | HTTP REST (key ilimitada) | Resultados, stats completas, fixtures | — |
| **FlashScore** | Selenium headless | Odds tempo real (13 casas × 9 mercados) | Fallback de resultados |
| [**Football-Data.co.uk**](http://football-data.co.uk/) | HTTP (CSV) | Backfill histórico (seed matches + odds Pinnacle/B365) | — |
| **FBRef** | HTTP (requests + BS4) | xG para 19 ligas fora do Understat | Stats avançadas |
| **Understat** | HTTP (lib Python async) | xG granular Top 5 (por chute, por situação) | — |
| **The Odds API** | HTTP REST (5 keys grátis) | Validação cruzada de odds | Fallback quando FlashScore falha |
| **API-Football** | HTTP REST (7 keys grátis) | Escalações confirmadas | Fallback fixtures |

### 2.3 Hierarquia de Fallback

```
RESULTADOS + STATS:
  Footystats → API-Football → FlashScore → Football-Data.co.uk

ODDS TEMPO REAL:
  FlashScore → The Odds API

ODDS FECHAMENTO (CLV):
  FlashScore (Pinnacle último snapshot) → Football-Data (Pinnacle CSV)

xG:
  Understat (5 ligas Top) → FBRef (19 ligas adicionais) → Footystats (2 ligas sem FBRef)

ESCALAÇÕES:
  API-Football → FlashScore

FIXTURES/CALENDÁRIO:
  Footystats → API-Football
```

---

## 3. Ligas no Escopo

### 3.1 Tabela Completa — 26 Ligas

### Main Leagues ([Football-Data.co.uk](http://football-data.co.uk/))

| # | País | Liga | Código | FD | Understat | FBRef ID | FBRef xG | Formato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | Premier League | `ENG_PL` | `E0` | `EPL` | 9 | ✅ | Ago–Mai |
| 2 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | Championship | `ENG_CH` | `E1` | ❌ | 10 | ✅ | Ago–Mai |
| 3 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | League One | `ENG_L1` | `E2` | ❌ | 15 | ✅ | Ago–Mai |
| 4 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | League Two | `ENG_L2` | `E3` | ❌ | 16 | ✅ | Ago–Mai |
| 5 | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 | National League | `ENG_NL` | `EC` | ❌ | 58 | ✅ | Ago–Mai |
| 6 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | Premiership | `SCO_PL` | `SC0` | ❌ | 40 | ✅ | Ago–Mai |
| 7 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | Championship | `SCO_CH` | `SC1` | ❌ | 69 | ✅ | Ago–Mai |
| 8 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | League One | `SCO_L1` | `SC2` | ❌ | — | ❌ | Ago–Mai |
| 9 | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 | League Two | `SCO_L2` | `SC3` | ❌ | — | ❌ | Ago–Mai |
| 10 | 🇩🇪 | Bundesliga | `GER_BL` | `D1` | `Bundesliga` | 20 | ✅ | Ago–Mai |
| 11 | 🇩🇪 | 2. Bundesliga | `GER_B2` | `D2` | ❌ | 33 | ✅ | Ago–Mai |
| 12 | 🇮🇹 | Serie A | `ITA_SA` | `I1` | `Serie_A` | 11 | ✅ | Ago–Mai |
| 13 | 🇮🇹 | Serie B | `ITA_SB` | `I2` | ❌ | 18 | ✅ | Ago–Mai |
| 14 | 🇪🇸 | La Liga | `ESP_PD` | `SP1` | `La_Liga` | 12 | ✅ | Ago–Mai |
| 15 | 🇪🇸 | La Liga 2 | `ESP_SD` | `SP2` | ❌ | 17 | ✅ | Ago–Mai |
| 16 | 🇫🇷 | Ligue 1 | `FRA_L1` | `F1` | `Ligue_1` | 13 | ✅ | Ago–Mai |
| 17 | 🇫🇷 | Ligue 2 | `FRA_L2` | `F2` | ❌ | 60 | ✅ | Ago–Mai |
| 18 | 🇳🇱 | Eredivisie | `NED_ED` | `N1` | ❌ | 23 | ✅ | Ago–Mai |
| 19 | 🇧🇪 | Pro League | `BEL_PL` | `B1` | ❌ | 37 | ✅ | Ago–Mai |
| 20 | 🇵🇹 | Primeira Liga | `POR_PL` | `P1` | ❌ | 32 | ✅ | Ago–Mai |
| 21 | 🇹🇷 | Süper Lig | `TUR_SL` | `T1` | ❌ | 26 | ✅ | Ago–Mai |
| 22 | 🇬🇷 | Super League | `GRE_SL` | `G1` | ❌ | 27 | ✅ | Ago–Mai |

### Extra Leagues

| # | País | Liga | Código | FD | Understat | FBRef ID | FBRef xG | Formato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 23 | 🇧🇷 | Brasileirão Série A | `BRA_SA` | `BRA` | ❌ | 24 | ✅ | Abr–Dez |
| 24 | 🇲🇽 | Liga MX | `MEX_LM` | `MEX` | ❌ | 31 | ✅ | Jul–Mai‡ |
| 25 | 🇦🇹 | Bundesliga | `AUT_BL` | `AUT` | ❌ | 56 | ✅ | Jul–Mai |
| 26 | 🇨🇭 | Super League | `SWI_SL` | `SWZ` | ❌ | 57 | ✅ | Jul–Mai |

> ‡ Liga MX opera em formato Apertura/Clausura com playoffs.
> 

### 3.2 Season IDs Footystats — COMPLETO

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

### 3.3 Cobertura de xG

```
UNDERSTAT — xG granular por chute (5 ligas):
  ENG_PL, ESP_PD, GER_BL, ITA_SA, FRA_L1

FBREF — xG por jogo (19 ligas adicionais):
  ENG_CH, ENG_L1, ENG_L2, ENG_NL, SCO_PL, SCO_CH
  GER_B2, ITA_SB, ESP_SD, FRA_L2
  NED_ED, BEL_PL, POR_PL, TUR_SL, GRE_SL
  BRA_SA, MEX_LM, AUT_BL, SWI_SL

FOOTYSTATS — xG básico, fallback (2 ligas sem FBRef):
  SCO_L1, SCO_L2
```

### 3.4 Tiers

```
TIER 1 — Main leagues UK + Top 5 europeias + divisões inferiores (17 ligas)
  ENG_PL, ENG_CH, ENG_L1, ENG_L2, ENG_NL
  SCO_PL, SCO_CH, SCO_L1, SCO_L2
  GER_BL, GER_B2
  ITA_SA, ITA_SB
  ESP_PD, ESP_SD
  FRA_L1, FRA_L2

TIER 2 — Demais europeias (5 ligas)
  NED_ED, BEL_PL, POR_PL, TUR_SL, GRE_SL

TIER 3 — Extras (4 ligas)
  BRA_SA, MEX_LM, AUT_BL, SWI_SL
```

**Uso dos tiers:**

- **Tier 1**: todas as fontes, modelagem completa, prioridade no schedule
- **Tier 2**: todas as fontes, modelagem completa, xG via FBRef
- **Tier 3**: todas as fontes, modelagem completa, xG via FBRef, CSV do Football-Data pode ter menos colunas de odds

### 3.5 Estimativas de Volume

| Métrica | Valor |
| --- | --- |
| Total de ligas | **26** |
| Países | **14** |
| Jogos por temporada (estimativa) | ~11.500 |
| Backfill 5 temporadas | **~57.500 jogos** |
| Times únicos (estimativa) | **~580** |
| Aliases para mapear | ~580 × 6 fontes = **~3.480** |
| Season IDs Footystats mapeados | **130/130 (100%)** |

---

## 4. Casas de Apostas

| Tier | Casa | Código | Tipo | CLV Priority | FlashScore Aliases |
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

---

## 5. Mercados e Linhas

### 5.1 Full-Time

| Mercado | `market_type` | `line` | Seleções (`odds_1` / `odds_x` / `odds_2`) | Linhas |
| --- | --- | --- | --- | --- |
| 1X2 | `1x2` | `NULL` | Home / Draw / Away | 1 |
| Over/Under | `ou` | 0.5→4.5 | Over / — / Under | 16 |
| Asian Handicap | `ah` | 50/50 ± 2 | Home AH / — / Away AH | 5 (dinâmico) |
| Dupla Chance | `dc` | `NULL` | 1X / 12 / X2 | 1 |
| Draw No Bet | `dnb` | `NULL` | Home / — / Away | 1 |
| BTTS | `btts` | `NULL` | Yes / — / No | 1 |

### 5.2 Half-Time

| Mercado | `market_type` | `line` | Seleções | Linhas |
| --- | --- | --- | --- | --- |
| 1X2 HT | `1x2_ht` | `NULL` | Home / Draw / Away | 1 |
| Over/Under HT | `ou_ht` | 0.5→2.5 | Over / — / Under | 9 |
| Asian Handicap HT | `ah_ht` | 50/50 | Home AH / — / Away AH | 1 |

### 5.3 Linhas OU Full-Time

```
0.5, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5
```

### 5.4 Linhas OU Half-Time

```
0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5
```

### 5.5 Asian Handicap — Linha 50/50

```python
def find_balanced_line(ah_odds: list[dict]) -> float:
    """
    Input: [{'line': -0.5, 'home': 1.92, 'away': 1.96}, ...]
    Output: linha cujo |home - away| é mínimo
    """
    best = min(ah_odds, key=lambda x: abs(x['home'] - x['away']))
    return best['line']

def get_ah_lines_to_collect(balanced: float) -> list[float]:
    """50/50 + 2 acima (favor home) + 2 abaixo (favor away)."""
    step = 0.25
    return sorted([balanced + (i * step) for i in range(-2, 3)])
```

### 5.6 Convenções de Sinal (AH)

```
Linha NEGATIVA = handicap contra o home (home precisa vencer por X+)
Linha POSITIVA = handicap a favor do home (home pode perder por até X)
```

---

## 6. Schedule de Coleta

### 6.1 Jobs

| Job ID | Cron/Trigger | Fonte | Ação |
| --- | --- | --- | --- |
| `odds_standard` | `0 6,10,14,20 * * *` BRT | FlashScore | Odds de jogos D+1 a D+7 |
| `odds_gameday_hourly` | Dinâmico: 1x/hora (jogos do dia) | FlashScore | Odds de jogos de hoje |
| `odds_prematch_30` | Dinâmico: T-30min | FlashScore | Snapshot pré-jogo |
| `odds_prematch_2` | Dinâmico: T-2min | FlashScore | Snapshot final |
| `results_postmatch` | Dinâmico: T+2h30 | Footystats | Resultado + stats + mark closing |
| `xg_postround` | `0 6 * * *` BRT | Understat + FBRef | xG da rodada anterior |
| `lineups_prematch` | Dinâmico: T-60min | API-Football | Escalações confirmadas |
| `fixtures_weekly` | `0 5 * * 1` BRT | Footystats | Calendário semanal |
| `csv_weekly` | `0 4 * * 1` BRT | Football-Data | CSV bulk semanal |
| `odds_api_validation` | A cada 3h (dias com jogos) | The Odds API | Validação cruzada Pinnacle |
| `health_check` | A cada 5min | Todas | Verificação de disponibilidade |
| `reset_daily_keys` | `0 0 * * *` UTC | — | Reseta `usage_today` em `api_keys` |

### 6.2 Volume Estimado por Período

| Período | Jogos/dia |
| --- | --- |
| Meio de semana normal | ~40–60 |
| Final de semana | ~100–150 |
| Pico (todas as ligas jogando) | ~180 |

### 6.3 Priorização no Schedule

Quando há muitos jogos (>100/dia), FlashScore prioriza:

1. **Tier 1** — coleta integral (todos os mercados, todas as linhas)
2. **Tier 2** — coleta integral
3. **Tier 3** — coleta integral, mas pode atrasar se fila estiver cheia

### 6.4 Lógica T-X (Jobs dinâmicos)

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

## 7. Schema do Banco de Dados

### 7.1 Tabelas de Referência

```sql
-- ============================================================
-- LEAGUES
-- ============================================================
CREATE TABLE leagues (
    league_id           SERIAL PRIMARY KEY,
    code                VARCHAR(10) UNIQUE NOT NULL,
    name                VARCHAR(100) NOT NULL,
    country             VARCHAR(50) NOT NULL,
    tier                SMALLINT NOT NULL DEFAULT 1,
    season_format       VARCHAR(10) NOT NULL,
    football_data_code  VARCHAR(10),
    football_data_type  VARCHAR(10),       -- 'main' ou 'extra'
    understat_name      VARCHAR(50),
    fbref_id            VARCHAR(20),
    flashscore_path     VARCHAR(100),
    footystats_name     VARCHAR(100),      -- Nome exato no Footystats
    xg_source           VARCHAR(20) DEFAULT 'fbref',  -- 'understat', 'fbref', 'footystats'
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TEAMS
-- ============================================================
CREATE TABLE teams (
    team_id             SERIAL PRIMARY KEY,
    name_canonical      VARCHAR(100) NOT NULL,
    country             VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TEAM ALIASES
-- ============================================================
CREATE TABLE team_aliases (
    alias_id            SERIAL PRIMARY KEY,
    team_id             INTEGER NOT NULL REFERENCES teams(team_id),
    source              VARCHAR(30) NOT NULL,
    alias_name          VARCHAR(100) NOT NULL,
    UNIQUE(source, alias_name)
);

CREATE INDEX idx_team_aliases_lookup ON team_aliases(source, alias_name);

-- ============================================================
-- UNKNOWN ALIASES (para revisão)
-- ============================================================
CREATE TABLE unknown_aliases (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(30) NOT NULL,
    raw_name            VARCHAR(100) NOT NULL,
    first_seen          TIMESTAMPTZ DEFAULT NOW(),
    resolved            BOOLEAN DEFAULT FALSE,
    resolved_team_id    INTEGER REFERENCES teams(team_id),
    UNIQUE(source, raw_name)
);

-- ============================================================
-- SEASONS
-- ============================================================
CREATE TABLE seasons (
    season_id           SERIAL PRIMARY KEY,
    league_id           INTEGER NOT NULL REFERENCES leagues(league_id),
    label               VARCHAR(10) NOT NULL,      -- '2024/2025' ou '2024'
    start_date          DATE NOT NULL,
    end_date            DATE,
    footystats_season_id INTEGER NOT NULL,
    football_data_season VARCHAR(10),               -- '2425' ou null (extras)
    is_current          BOOLEAN DEFAULT FALSE,
    UNIQUE(league_id, label)
);

-- ============================================================
-- BOOKMAKERS
-- ============================================================
CREATE TABLE bookmakers (
    bookmaker_id        SERIAL PRIMARY KEY,
    name                VARCHAR(50) UNIQUE NOT NULL,
    display_name        VARCHAR(50) NOT NULL,
    type                VARCHAR(20) NOT NULL,
    clv_priority        SMALLINT,
    is_active           BOOLEAN DEFAULT TRUE
);

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

-- ============================================================
-- API KEYS
-- ============================================================
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

CREATE INDEX idx_api_keys_service ON api_keys(service, is_active);
```

### 7.2 Matches

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

    flashscore_id       VARCHAR(30),
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

CREATE INDEX idx_matches_kickoff ON matches(kickoff);
CREATE INDEX idx_matches_league_status ON matches(league_id, status);
CREATE INDEX idx_matches_season ON matches(season_id);
CREATE INDEX idx_matches_footystats ON matches(footystats_id) WHERE footystats_id IS NOT NULL;
CREATE INDEX idx_matches_flashscore ON matches(flashscore_id) WHERE flashscore_id IS NOT NULL;
```

### 7.3 Match Stats

```sql
CREATE TABLE match_stats (
    stat_id                 SERIAL PRIMARY KEY,
    match_id                UUID NOT NULL REFERENCES matches(match_id),

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

    corners_home_ht         SMALLINT,       -- Pode ser NULL
    corners_away_ht         SMALLINT,       -- Pode ser NULL
    total_corners_ht        SMALLINT GENERATED ALWAYS AS (
        CASE WHEN corners_home_ht IS NOT NULL AND corners_away_ht IS NOT NULL
             THEN corners_home_ht + corners_away_ht
             ELSE NULL END
    ) STORED,

    yellow_cards_home_ft    SMALLINT,
    yellow_cards_away_ft    SMALLINT,
    red_cards_home_ft       SMALLINT,
    red_cards_away_ft       SMALLINT,

    cards_home_ht           SMALLINT,       -- Pode ser NULL
    cards_away_ht           SMALLINT,       -- Pode ser NULL

    source                  VARCHAR(20) NOT NULL,
    collected_at            TIMESTAMPTZ DEFAULT NOW(),
    raw_json                JSONB,

    UNIQUE(match_id, source)
);

CREATE INDEX idx_match_stats_match ON match_stats(match_id);
```

### 7.4 Odds History (TimescaleDB)

```sql
CREATE TABLE odds_history (
    time                TIMESTAMPTZ NOT NULL,
    match_id            UUID NOT NULL REFERENCES matches(match_id),
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

CREATE UNIQUE INDEX idx_odds_dedup
    ON odds_history(match_id, bookmaker_id, market_type, COALESCE(line, 0), period, content_hash, time);

CREATE INDEX idx_odds_match_market
    ON odds_history(match_id, market_type, bookmaker_id, time DESC);

CREATE INDEX idx_odds_closing
    ON odds_history(match_id, bookmaker_id, market_type)
    WHERE is_closing = TRUE;
```

### 7.5 Lineups

```sql
CREATE TABLE lineups (
    lineup_id           SERIAL PRIMARY KEY,
    match_id            UUID NOT NULL REFERENCES matches(match_id),
    team_id             INTEGER NOT NULL REFERENCES teams(team_id),
    formation           VARCHAR(10),
    players_json        JSONB NOT NULL,
    source              VARCHAR(20) NOT NULL,
    collected_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(match_id, team_id, source)
);
```

### 7.6 Ingestion Log

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
    metadata_json       JSONB
);

CREATE INDEX idx_ingestion_status ON ingestion_log(status, started_at DESC);
CREATE INDEX idx_ingestion_source ON ingestion_log(source, job_type, started_at DESC);
```

---

## 8. Contratos de Interface por Coletor

### 8.1 BaseCollector

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

### 8.2 FlashScore Odds Collector

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

**Transformação antes do INSERT:**

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
        "is_opening": False,
        "is_closing": False,
        "source": "flashscore",
        "content_hash": content_hash
    }
```

### 8.3 Footystats Matches Collector

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

**Mapeamento campo Footystats → coluna DB:**

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

### 8.4 Football-Data CSV Collector

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

> **Nota:** CSVs de extra leagues (BRA, MEX, AUT, SWZ) podem ter menos colunas de odds. O collector trata colunas ausentes como NULL.
> 

### 8.5 Understat xG Collector

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

### 8.6 FBRef Collector

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
    fbref_id: str
    date: str
    home_name: str
    away_name: str
    ft_home: int
    ft_away: int
    xg_home: Optional[float]
    xg_away: Optional[float]
    source: str = "fbref"
```

### 8.7 The Odds API Collector

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

### 8.8 API-Football Collector

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

## 9. Regras de Negócio

### 9.1 Determinação de `is_opening`

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

### 9.2 Determinação de `is_closing`

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

### 9.3 Status de Match

```
scheduled → live → finished
scheduled → postponed → scheduled (reagendado) → live → finished
scheduled → cancelled
```

### 9.4 Tratamento de Valores Especiais

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

### 9.5 Overround

```python
def calculate_overround(odds_1, odds_x=None, odds_2=None) -> float:
    inv_sum = 0.0
    for odds in [odds_1, odds_x, odds_2]:
        if odds is not None and odds > 1.0:
            inv_sum += 1.0 / odds
    return round(inv_sum - 1.0, 4)
```

### 9.6 Content Hash (Dedup)

```python
import hashlib

def compute_content_hash(match_id, bookmaker_id, market_type, line, period,
                          odds_1, odds_x, odds_2) -> str:
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
    """Se hash igual ao último → skip. Se diferente → insert."""
    last_hash = await db.fetch_val(
        """SELECT content_hash FROM odds_history
           WHERE match_id = $1 AND bookmaker_id = $2 AND market_type = $3
           AND COALESCE(line, 0) = COALESCE($4, 0) AND period = $5
           ORDER BY time DESC LIMIT 1""",
        record['match_id'], record['bookmaker_id'], record['market_type'],
        record['line'], record['period']
    )
    if last_hash == record['content_hash']:
        return False
    await db.insert('odds_history', record)
    return True
```

---

## 10. Normalização e Dedup

### 10.1 Team Resolver

```python
class TeamResolver:
    def __init__(self, db):
        self.db = db
        self._cache: Dict[tuple, Optional[int]] = {}

    async def resolve(self, source: str, raw_name: str) -> Optional[int]:
        key = (source, raw_name.strip())
        if key in self._cache:
            return self._cache[key]

        team_id = await self.db.fetch_val(
            "SELECT team_id FROM team_aliases WHERE source=$1 AND alias_name=$2",
            source, raw_name.strip()
        )
        self._cache[key] = team_id

        if team_id is None:
            await self.db.execute(
                """INSERT INTO unknown_aliases (source, raw_name, first_seen)
                   VALUES ($1, $2, NOW())
                   ON CONFLICT (source, raw_name) DO NOTHING""",
                source, raw_name
            )
            await send_alert(f"⚠️ Alias desconhecido: '{raw_name}' ({source})")

        return team_id
```

### 10.2 Match Resolver

```python
class MatchResolver:
    def __init__(self, db, team_resolver: TeamResolver):
        self.db = db
        self.team_resolver = team_resolver

    async def resolve(self, league_id, home_name, away_name,
                      kickoff_date, source) -> Optional[UUID]:
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

### 10.3 Bookmaker Resolver

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

## 11. Backfill Histórico

### 11.1 Pipeline

```
ETAPA 1 — Football-Data CSV (seed)
│  ~130 CSVs (26 ligas × 5 temporadas)
│  Gera: matches + odds_history (Pinnacle/B365 1X2 + OU 2.5 onde disponível)
│  Gera: team_aliases_seed.csv → REVISÃO MANUAL
│  Tempo: ~10 min
│
ETAPA 2 — ⏸️ Revisão de Aliases (Marcelo)
│  CSV com ~580 times × mapeamento canônico
│  Tempo: 1–1.5 dias
│
ETAPA 3 — Footystats API (stats)
│  26 ligas × 5 temporadas = 130 season requests
│  Enriquece: match_stats completas
│  Atualiza: matches (HT, minutos gols, footystats_id)
│  Tempo: ~40 min (key ilimitada)
│
ETAPA 4 — Understat (xG Top 5)
│  5 ligas × 5 temporadas = 25 requests
│  Tempo: ~3h
│
ETAPA 5 — FBRef (xG 19 ligas adicionais)
│  19 ligas × 5 temporadas = 95 season pages
│  Rate limit: 10 req/min
│  Tempo: ~14h
│
TOTAL: ~24h supervisionadas (~1.5 dias)
```

### 11.2 Seed de Aliases (CSV)

```python
def generate_alias_seed_csv(csv_dir: str, output_path: str):
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
                'canonical_name_bet365': '',
                'country': '',
                'league_code': div,
            })

    result = pd.DataFrame(records).drop_duplicates(subset=['football_data_name', 'league_code'])
    result.to_csv(output_path, index=False)
```

---

## 12. Resiliência e Fallback

### 12.1 Retry com Backoff

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

### 12.2 Rate Limiting

```python
RATE_LIMITS = {
    "flashscore":    {"max_requests": 30, "window_seconds": 60},
    "fbref":         {"max_requests": 10, "window_seconds": 60},
    "understat":     {"max_requests": 20, "window_seconds": 60},
    "footystats":    {"max_requests": 60, "window_seconds": 60},
    "odds_api":      {"max_requests": 10, "window_seconds": 60},
    "api_football":  {"max_requests": 10, "window_seconds": 60},
}
```

### 12.3 Inter-Request Delays

```python
INTER_REQUEST_DELAYS = {
    "flashscore":   (2.0, 4.0),
    "fbref":        (6.0, 10.0),
    "understat":    (2.0, 3.0),
    "footystats":   (0.5, 1.0),
}
```

### 12.4 User-Agent Rotation

```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Edg/120.0.0.0",
]
```

---

## 13. Configuração Selenium

### 13.1 Chrome Options

```python
def create_chrome_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument(f"--user-agent={get_random_ua()}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-images")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--lang=en-US")
    options.add_experimental_option("prefs", {"intl.accept_languages": "en-US,en"})

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    })
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(5)
    return driver
```

### 13.2 Wait Conditions

```python
WAIT_CONDITIONS = {
    "flashscore": {
        "page_load":      {"timeout": 15, "condition": (By.CSS_SELECTOR, "div.event__match")},
        "odds_tab_load":  {"timeout": 10, "condition": (By.CSS_SELECTOR, "div.ui-table__row")},
        "market_switch":  {"timeout": 8,  "condition": (By.CSS_SELECTOR, "div.ui-table__row")},
        "cookie_banner":  {"timeout": 5,  "condition": (By.ID, "onetrust-accept-btn-handler")},
    }
}
```

### 13.3 Cookie Handler

```python
class CookieHandler:
    @staticmethod
    def save(driver, source):
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_DIR / f"{source}.pkl", "wb") as f:
            pickle.dump(driver.get_cookies(), f)

    @staticmethod
    def load(driver, source) -> bool:
        cookie_file = COOKIE_DIR / f"{source}.pkl"
        if not cookie_file.exists():
            return False
        with open(cookie_file, "rb") as f:
            for cookie in pickle.load(f):
                cookie.pop('sameSite', None)
                cookie.pop('httpOnly', None)
                try:
                    driver.add_cookie(cookie)
                except:
                    continue
        return True
```

### 13.4 Selenium Pool

```python
class SeleniumPool:
    def __init__(self, max_instances=2):
        self._semaphore = asyncio.Semaphore(max_instances)
        self._drivers = []

    async def acquire(self) -> webdriver.Chrome:
        await self._semaphore.acquire()
        driver = create_chrome_driver()
        self._drivers.append(driver)
        return driver

    async def release(self, driver):
        try: driver.quit()
        except: pass
        if driver in self._drivers: self._drivers.remove(driver)
        self._semaphore.release()
```

### 13.5 FlashScore Selectors (arquivo isolado)

```python
# collectors/flashscore/selectors.py
# ATUALIZAR APENAS ESTE ARQUIVO quando layout mudar.
# Versão: 2026-03-28

SELECTORS = {
    "cookie_accept_btn":        "#onetrust-accept-btn-handler",
    "match_row":                "div.event__match",
    "match_id_attr":            "id",
    "home_team":                "div.event__participant--home",
    "away_team":                "div.event__participant--away",
    "match_time":               "div.event__time",
    "score_home":               "div.event__score--home",
    "score_away":               "div.event__score--away",
    "odds_tab":                 "#detail__tab--odds",
    "odds_bookmaker_row":       "div.ui-table__row",
    "odds_bookmaker_name":      "a.oddsCell__bookmaker",
    "odds_value":               "span.oddsCell__odd",
    "market_1x2":               "a[href*='1x2']",
    "market_ou":                "a[href*='over-under']",
    "market_ah":                "a[href*='asian-handicap']",
    "market_dc":                "a[href*='double-chance']",
    "market_dnb":               "a[href*='draw-no-bet']",
    "market_btts":              "a[href*='both-teams']",
    "market_1x2_ht":            "a[href*='1st-half'][href*='1x2']",
    "market_ou_ht":             "a[href*='1st-half'][href*='over-under']",
    "market_ah_ht":             "a[href*='1st-half'][href*='asian-handicap']",
    "line_selector":            "div.subTabs a",
    "active_line":              "div.subTabs a.active",
}

MARKET_SELECTOR_MAP = {
    "1x2": "market_1x2", "ou": "market_ou", "ah": "market_ah",
    "dc": "market_dc", "dnb": "market_dnb", "btts": "market_btts",
    "1x2_ht": "market_1x2_ht", "ou_ht": "market_ou_ht", "ah_ht": "market_ah_ht",
}
```

---

## 14. Arquivos de Configuração (YAML)

### 14.1 leagues.yaml — COMPLETO COM SEASON IDs

```yaml
leagues:
  # ================================================================
  # ENGLAND (5 ligas)
  # ================================================================
  ENG_PL:
    name: "Premier League"
    country: "England"
    tier: 1
    season_format: "aug_may"
    football_data_code: "E0"
    football_data_type: "main"
    understat_name: "EPL"
    fbref_id: "9"
    xg_source: "understat"
    flashscore_path: "england/premier-league"
    footystats_name: "England Premier League"
    seasons:
      "2021/2022": { start: "2021-08-13", end: "2022-05-22", fd: "2122", us: 2021, fbref: "2021-2022", fs: 6135 }
      "2022/2023": { start: "2022-08-05", end: "2023-05-28", fd: "2223", us: 2022, fbref: "2022-2023", fs: 7704 }
      "2023/2024": { start: "2023-08-11", end: "2024-05-19", fd: "2324", us: 2023, fbref: "2023-2024", fs: 9660 }
      "2024/2025": { start: "2024-08-16", end: "2025-05-25", fd: "2425", us: 2024, fbref: "2024-2025", fs: 12325 }
      "2025/2026": { start: "2025-08-15", end: null, fd: "2526", us: 2025, fbref: "2025-2026", fs: 15050, current: true }

  ENG_CH:
    name: "Championship"
    country: "England"
    tier: 1
    season_format: "aug_may"
    football_data_code: "E1"
    football_data_type: "main"
    understat_name: null
    fbref_id: "10"
    xg_source: "fbref"
    flashscore_path: "england/championship"
    footystats_name: "England Championship"
    seasons:
      "2021/2022": { start: "2021-08-06", end: "2022-05-29", fd: "2122", fs: 6089 }
      "2022/2023": { start: "2022-07-29", end: "2023-05-27", fd: "2223", fs: 7593 }
      "2023/2024": { start: "2023-08-04", end: "2024-05-26", fd: "2324", fs: 9663 }
      "2024/2025": { start: "2024-08-09", end: "2025-05-25", fd: "2425", fs: 12451 }
      "2025/2026": { start: "2025-08-08", end: null, fd: "2526", fs: 14930, current: true }

  ENG_L1:
    name: "League One"
    country: "England"
    tier: 1
    season_format: "aug_may"
    football_data_code: "E2"
    football_data_type: "main"
    understat_name: null
    fbref_id: "15"
    xg_source: "fbref"
    flashscore_path: "england/league-one"
    footystats_name: "England EFL League One"
    seasons:
      "2021/2022": { start: "2021-08-07", end: "2022-04-30", fd: "2122", fs: 6017 }
      "2022/2023": { start: "2022-07-30", end: "2023-05-07", fd: "2223", fs: 7570 }
      "2023/2024": { start: "2023-08-05", end: "2024-05-05", fd: "2324", fs: 9582 }
      "2024/2025": { start: "2024-08-10", end: "2025-05-04", fd: "2425", fs: 12446 }
      "2025/2026": { start: "2025-08-09", end: null, fd: "2526", fs: 14934, current: true }

  ENG_L2:
    name: "League Two"
    country: "England"
    tier: 1
    season_format: "aug_may"
    football_data_code: "E3"
    football_data_type: "main"
    understat_name: null
    fbref_id: "16"
    xg_source: "fbref"
    flashscore_path: "england/league-two"
    footystats_name: "England EFL League Two"
    seasons:
      "2021/2022": { start: "2021-08-07", end: "2022-05-07", fd: "2122", fs: 6015 }
      "2022/2023": { start: "2022-07-30", end: "2023-05-06", fd: "2223", fs: 7574 }
      "2023/2024": { start: "2023-08-05", end: "2024-05-04", fd: "2324", fs: 9581 }
      "2024/2025": { start: "2024-08-10", end: "2025-05-03", fd: "2425", fs: 12422 }
      "2025/2026": { start: "2025-08-09", end: null, fd: "2526", fs: 14935, current: true }

  ENG_NL:
    name: "National League"
    country: "England"
    tier: 1
    season_format: "aug_may"
    football_data_code: "EC"
    football_data_type: "main"
    understat_name: null
    fbref_id: "58"
    xg_source: "fbref"
    flashscore_path: "england/national-league"
    footystats_name: "England National League"
    seasons:
      "2021/2022": { start: "2021-08-21", end: "2022-06-05", fd: "2122", fs: 6088 }
      "2022/2023": { start: "2022-08-06", end: "2023-06-11", fd: "2223", fs: 7729 }
      "2023/2024": { start: "2023-08-05", end: "2024-06-09", fd: "2324", fs: 9700 }
      "2024/2025": { start: "2024-08-10", end: "2025-06-08", fd: "2425", fs: 12622 }
      "2025/2026": { start: "2025-08-09", end: null, fd: "2526", fs: 15657, current: true }

  # ================================================================
  # SCOTLAND (4 ligas)
  # ================================================================
  SCO_PL:
    name: "Premiership"
    country: "Scotland"
    tier: 1
    season_format: "aug_may"
    football_data_code: "SC0"
    football_data_type: "main"
    understat_name: null
    fbref_id: "40"
    xg_source: "fbref"
    flashscore_path: "scotland/premiership"
    footystats_name: "Scotland Premiership"
    seasons:
      "2021/2022": { start: "2021-07-31", end: "2022-05-25", fd: "2122", fs: 5992 }
      "2022/2023": { start: "2022-07-30", end: "2023-05-28", fd: "2223", fs: 7494 }
      "2023/2024": { start: "2023-08-05", end: "2024-05-25", fd: "2324", fs: 9636 }
      "2024/2025": { start: "2024-08-03", end: "2025-05-24", fd: "2425", fs: 12455 }
      "2025/2026": { start: "2025-08-02", end: null, fd: "2526", fs: 15000, current: true }

  SCO_CH:
    name: "Championship"
    country: "Scotland"
    tier: 2
    season_format: "aug_may"
    football_data_code: "SC1"
    football_data_type: "main"
    understat_name: null
    fbref_id: "69"
    xg_source: "fbref"
    flashscore_path: "scotland/championship"
    footystats_name: "Scotland Championship"
    seasons:
      "2021/2022": { start: "2021-07-31", end: "2022-05-06", fd: "2122", fs: 5991 }
      "2022/2023": { start: "2022-07-29", end: "2023-05-12", fd: "2223", fs: 7498 }
      "2023/2024": { start: "2023-08-04", end: "2024-05-03", fd: "2324", fs: 9637 }
      "2024/2025": { start: "2024-08-02", end: "2025-05-02", fd: "2425", fs: 12456 }
      "2025/2026": { start: "2025-08-01", end: null, fd: "2526", fs: 15061, current: true }

  SCO_L1:
    name: "League One"
    country: "Scotland"
    tier: 2
    season_format: "aug_may"
    football_data_code: "SC2"
    football_data_type: "main"
    understat_name: null
    fbref_id: null
    xg_source: "footystats"
    flashscore_path: "scotland/league-one"
    footystats_name: "Scotland League One"
    seasons:
      "2021/2022": { start: "2021-07-31", end: "2022-04-30", fd: "2122", fs: 5976 }
      "2022/2023": { start: "2022-07-30", end: "2023-04-29", fd: "2223", fs: 7505 }
      "2023/2024": { start: "2023-08-05", end: "2024-05-04", fd: "2324", fs: 9639 }
      "2024/2025": { start: "2024-08-03", end: "2025-05-03", fd: "2425", fs: 12474 }
      "2025/2026": { start: "2025-08-02", end: null, fd: "2526", fs: 14943, current: true }

  SCO_L2:
    name: "League Two"
    country: "Scotland"
    tier: 2
    season_format: "aug_may"
    football_data_code: "SC3"
    football_data_type: "main"
    understat_name: null
    fbref_id: null
    xg_source: "footystats"
    flashscore_path: "scotland/league-two"
    footystats_name: "Scotland League Two"
    seasons:
      "2021/2022": { start: "2021-07-31", end: "2022-04-30", fd: "2122", fs: 5974 }
      "2022/2023": { start: "2022-07-30", end: "2023-04-29", fd: "2223", fs: 7506 }
      "2023/2024": { start: "2023-08-05", end: "2024-05-04", fd: "2324", fs: 9638 }
      "2024/2025": { start: "2024-08-03", end: "2025-05-03", fd: "2425", fs: 12453 }
      "2025/2026": { start: "2025-08-02", end: null, fd: "2526", fs: 15209, current: true }

  # ================================================================
  # GERMANY (2 ligas)
  # ================================================================
  GER_BL:
    name: "Bundesliga"
    country: "Germany"
    tier: 1
    season_format: "aug_may"
    football_data_code: "D1"
    football_data_type: "main"
    understat_name: "Bundesliga"
    fbref_id: "20"
    xg_source: "understat"
    flashscore_path: "germany/bundesliga"
    footystats_name: "Germany Bundesliga"
    seasons:
      "2021/2022": { start: "2021-08-13", end: "2022-05-14", fd: "2122", us: 2021, fs: 6192 }
      "2022/2023": { start: "2022-08-05", end: "2023-05-27", fd: "2223", us: 2022, fs: 7664 }
      "2023/2024": { start: "2023-08-18", end: "2024-05-18", fd: "2324", us: 2023, fs: 9655 }
      "2024/2025": { start: "2024-08-23", end: "2025-05-17", fd: "2425", us: 2024, fs: 12529 }
      "2025/2026": { start: "2025-08-15", end: null, fd: "2526", us: 2025, fs: 14968, current: true }

  GER_B2:
    name: "2. Bundesliga"
    country: "Germany"
    tier: 1
    season_format: "aug_may"
    football_data_code: "D2"
    football_data_type: "main"
    understat_name: null
    fbref_id: "33"
    xg_source: "fbref"
    flashscore_path: "germany/2-bundesliga"
    footystats_name: "Germany 2. Bundesliga"
    seasons:
      "2021/2022": { start: "2021-07-23", end: "2022-05-15", fd: "2122", fs: 6020 }
      "2022/2023": { start: "2022-07-15", end: "2023-05-28", fd: "2223", fs: 7499 }
      "2023/2024": { start: "2023-07-28", end: "2024-05-19", fd: "2324", fs: 9656 }
      "2024/2025": { start: "2024-08-02", end: "2025-05-18", fd: "2425", fs: 12528 }
      "2025/2026": { start: "2025-08-01", end: null, fd: "2526", fs: 14931, current: true }

  # ================================================================
  # ITALY (2 ligas)
  # ================================================================
  ITA_SA:
    name: "Serie A"
    country: "Italy"
    tier: 1
    season_format: "aug_may"
    football_data_code: "I1"
    football_data_type: "main"
    understat_name: "Serie_A"
    fbref_id: "11"
    xg_source: "understat"
    flashscore_path: "italy/serie-a"
    footystats_name: "Italy Serie A"
    seasons:
      "2021/2022": { start: "2021-08-21", end: "2022-05-22", fd: "2122", us: 2021, fs: 6198 }
      "2022/2023": { start: "2022-08-13", end: "2023-06-04", fd: "2223", us: 2022, fs: 7608 }
      "2023/2024": { start: "2023-08-19", end: "2024-05-26", fd: "2324", us: 2023, fs: 9697 }
      "2024/2025": { start: "2024-08-17", end: "2025-05-25", fd: "2425", us: 2024, fs: 12530 }
      "2025/2026": { start: "2025-08-16", end: null, fd: "2526", us: 2025, fs: 15068, current: true }

  ITA_SB:
    name: "Serie B"
    country: "Italy"
    tier: 1
    season_format: "aug_may"
    football_data_code: "I2"
    football_data_type: "main"
    understat_name: null
    fbref_id: "18"
    xg_source: "fbref"
    flashscore_path: "italy/serie-b"
    footystats_name: "Italy Serie B"
    seasons:
      "2021/2022": { start: "2021-08-20", end: "2022-05-06", fd: "2122", fs: 6205 }
      "2022/2023": { start: "2022-08-12", end: "2023-05-26", fd: "2223", fs: 7864 }
      "2023/2024": { start: "2023-08-18", end: "2024-05-10", fd: "2324", fs: 9808 }
      "2024/2025": { start: "2024-08-16", end: "2025-05-09", fd: "2425", fs: 12621 }
      "2025/2026": { start: "2025-08-15", end: null, fd: "2526", fs: 15632, current: true }

  # ================================================================
  # SPAIN (2 ligas)
  # ================================================================
  ESP_PD:
    name: "La Liga"
    country: "Spain"
    tier: 1
    season_format: "aug_may"
    football_data_code: "SP1"
    football_data_type: "main"
    understat_name: "La_Liga"
    fbref_id: "12"
    xg_source: "understat"
    flashscore_path: "spain/laliga"
    footystats_name: "Spain La Liga"
    seasons:
      "2021/2022": { start: "2021-08-13", end: "2022-05-22", fd: "2122", us: 2021, fs: 6211 }
      "2022/2023": { start: "2022-08-12", end: "2023-06-04", fd: "2223", us: 2022, fs: 7665 }
      "2023/2024": { start: "2023-08-11", end: "2024-05-26", fd: "2324", us: 2023, fs: 9665 }
      "2024/2025": { start: "2024-08-15", end: "2025-05-25", fd: "2425", us: 2024, fs: 12316 }
      "2025/2026": { start: "2025-08-15", end: null, fd: "2526", us: 2025, fs: 14956, current: true }

  ESP_SD:
    name: "La Liga 2"
    country: "Spain"
    tier: 1
    season_format: "aug_may"
    football_data_code: "SP2"
    football_data_type: "main"
    understat_name: null
    fbref_id: "17"
    xg_source: "fbref"
    flashscore_path: "spain/laliga2"
    footystats_name: "Spain Segunda División"
    seasons:
      "2021/2022": { start: "2021-08-13", end: "2022-05-29", fd: "2122", fs: 6120 }
      "2022/2023": { start: "2022-08-12", end: "2023-06-11", fd: "2223", fs: 7592 }
      "2023/2024": { start: "2023-08-11", end: "2024-06-09", fd: "2324", fs: 9675 }
      "2024/2025": { start: "2024-08-16", end: "2025-06-08", fd: "2425", fs: 12467 }
      "2025/2026": { start: "2025-08-15", end: null, fd: "2526", fs: 15066, current: true }

  # ================================================================
  # FRANCE (2 ligas)
  # ================================================================
  FRA_L1:
    name: "Ligue 1"
    country: "France"
    tier: 1
    season_format: "aug_may"
    football_data_code: "F1"
    football_data_type: "main"
    understat_name: "Ligue_1"
    fbref_id: "13"
    xg_source: "understat"
    flashscore_path: "france/ligue-1"
    footystats_name: "France Ligue 1"
    seasons:
      "2021/2022": { start: "2021-08-06", end: "2022-05-21", fd: "2122", us: 2021, fs: 6019 }
      "2022/2023": { start: "2022-08-05", end: "2023-06-03", fd: "2223", us: 2022, fs: 7500 }
      "2023/2024": { start: "2023-08-11", end: "2024-05-25", fd: "2324", us: 2023, fs: 9674 }
      "2024/2025": { start: "2024-08-16", end: "2025-05-24", fd: "2425", us: 2024, fs: 12337 }
      "2025/2026": { start: "2025-08-08", end: null, fd: "2526", us: 2025, fs: 14932, current: true }

  FRA_L2:
    name: "Ligue 2"
    country: "France"
    tier: 1
    season_format: "aug_may"
    football_data_code: "F2"
    football_data_type: "main"
    understat_name: null
    fbref_id: "60"
    xg_source: "fbref"
    flashscore_path: "france/ligue-2"
    footystats_name: "France Ligue 2"
    seasons:
      "2021/2022": { start: "2021-07-24", end: "2022-05-14", fd: "2122", fs: 6018 }
      "2022/2023": { start: "2022-07-30", end: "2023-06-03", fd: "2223", fs: 7501 }
      "2023/2024": { start: "2023-08-05", end: "2024-05-18", fd: "2324", fs: 9621 }
      "2024/2025": { start: "2024-08-17", end: "2025-05-17", fd: "2425", fs: 12338 }
      "2025/2026": { start: "2025-08-09", end: null, fd: "2526", fs: 14954, current: true }

  # ================================================================
  # NETHERLANDS (1 liga)
  # ================================================================
  NED_ED:
    name: "Eredivisie"
    country: "Netherlands"
    tier: 2
    season_format: "aug_may"
    football_data_code: "N1"
    football_data_type: "main"
    understat_name: null
    fbref_id: "23"
    xg_source: "fbref"
    flashscore_path: "netherlands/eredivisie"
    footystats_name: "Netherlands Eredivisie"
    seasons:
      "2021/2022": { start: "2021-08-13", end: "2022-05-15", fd: "2122", fs: 5951 }
      "2022/2023": { start: "2022-08-05", end: "2023-05-28", fd: "2223", fs: 7482 }
      "2023/2024": { start: "2023-08-11", end: "2024-05-19", fd: "2324", fs: 9653 }
      "2024/2025": { start: "2024-08-09", end: "2025-05-18", fd: "2425", fs: 12322 }
      "2025/2026": { start: "2025-08-08", end: null, fd: "2526", fs: 14936, current: true }

  # ================================================================
  # BELGIUM (1 liga)
  # ================================================================
  BEL_PL:
    name: "Pro League"
    country: "Belgium"
    tier: 2
    season_format: "aug_may"
    football_data_code: "B1"
    football_data_type: "main"
    understat_name: null
    fbref_id: "37"
    xg_source: "fbref"
    flashscore_path: "belgium/jupiler-pro-league"
    footystats_name: "Belgium Pro League"
    seasons:
      "2021/2022": { start: "2021-07-23", end: "2022-05-22", fd: "2122", fs: 6079 }
      "2022/2023": { start: "2022-07-22", end: "2023-06-04", fd: "2223", fs: 7544 }
      "2023/2024": { start: "2023-07-28", end: "2024-05-12", fd: "2324", fs: 9577 }
      "2024/2025": { start: "2024-07-26", end: "2025-05-18", fd: "2425", fs: 12137 }
      "2025/2026": { start: "2025-07-25", end: null, fd: "2526", fs: 14937, current: true }

  # ================================================================
  # PORTUGAL (1 liga)
  # ================================================================
  POR_PL:
    name: "Primeira Liga"
    country: "Portugal"
    tier: 2
    season_format: "aug_may"
    football_data_code: "P1"
    football_data_type: "main"
    understat_name: null
    fbref_id: "32"
    xg_source: "fbref"
    flashscore_path: "portugal/liga-portugal"
    footystats_name: "Portugal Liga NOS"
    seasons:
      "2021/2022": { start: "2021-08-06", end: "2022-05-15", fd: "2122", fs: 6117 }
      "2022/2023": { start: "2022-08-05", end: "2023-05-27", fd: "2223", fs: 7731 }
      "2023/2024": { start: "2023-08-11", end: "2024-05-19", fd: "2324", fs: 9984 }
      "2024/2025": { start: "2024-08-09", end: "2025-05-18", fd: "2425", fs: 12931 }
      "2025/2026": { start: "2025-08-08", end: null, fd: "2526", fs: 15115, current: true }

  # ================================================================
  # TURKEY (1 liga)
  # ================================================================
  TUR_SL:
    name: "Süper Lig"
    country: "Turkey"
    tier: 2
    season_format: "aug_may"
    football_data_code: "T1"
    football_data_type: "main"
    understat_name: null
    fbref_id: "26"
    xg_source: "fbref"
    flashscore_path: "turkey/super-lig"
    footystats_name: "Turkey Süper Lig"
    seasons:
      "2021/2022": { start: "2021-08-16", end: "2022-05-21", fd: "2122", fs: 6125 }
      "2022/2023": { start: "2022-08-05", end: "2023-06-04", fd: "2223", fs: 7768 }
      "2023/2024": { start: "2023-08-11", end: "2024-05-25", fd: "2324", fs: 9913 }
      "2024/2025": { start: "2024-08-09", end: "2025-05-25", fd: "2425", fs: 12641 }
      "2025/2026": { start: "2025-08-08", end: null, fd: "2526", fs: 14972, current: true }

  # ================================================================
  # GREECE (1 liga)
  # ================================================================
  GRE_SL:
    name: "Super League"
    country: "Greece"
    tier: 2
    season_format: "aug_may"
    football_data_code: "G1"
    football_data_type: "main"
    understat_name: null
    fbref_id: "27"
    xg_source: "fbref"
    flashscore_path: "greece/super-league"
    footystats_name: "Greece Super League"
    seasons:
      "2021/2022": { start: "2021-08-21", end: "2022-05-15", fd: "2122", fs: 6282 }
      "2022/2023": { start: "2022-08-19", end: "2023-05-20", fd: "2223", fs: 7954 }
      "2023/2024": { start: "2023-08-25", end: "2024-05-12", fd: "2324", fs: 9889 }
      "2024/2025": { start: "2024-08-17", end: "2025-05-11", fd: "2425", fs: 12734 }
      "2025/2026": { start: "2025-08-16", end: null, fd: "2526", fs: 15163, current: true }

  # ================================================================
  # EXTRAS
  # ================================================================
  BRA_SA:
    name: "Brasileirão Série A"
    country: "Brazil"
    tier: 3
    season_format: "apr_dec"
    football_data_code: "BRA"
    football_data_type: "extra"
    understat_name: null
    fbref_id: "24"
    xg_source: "fbref"
    flashscore_path: "brazil/serie-a"
    footystats_name: "Brazil Serie A"
    seasons:
      "2021": { start: "2021-05-29", end: "2021-12-09", fd: null, fs: 5713 }
      "2022": { start: "2022-04-09", end: "2022-11-13", fd: null, fs: 7097 }
      "2023": { start: "2023-04-15", end: "2023-12-06", fd: null, fs: 9035 }
      "2024": { start: "2024-04-13", end: "2024-12-08", fd: null, fs: 11321 }
      "2025": { start: "2025-03-29", end: null, fd: null, fs: 14231, current: true }
      "2026": { start: "2026-04-01", end: null, fd: null, fs: 16544 }

  MEX_LM:
    name: "Liga MX"
    country: "Mexico"
    tier: 3
    season_format: "jul_may"
    football_data_code: "MEX"
    football_data_type: "extra"
    understat_name: null
    fbref_id: "31"
    xg_source: "fbref"
    flashscore_path: "mexico/liga-mx"
    footystats_name: "Mexico Liga MX"
    seasons:
      "2021/2022": { start: "2021-07-22", end: "2022-05-29", fd: null, fs: 6038 }
      "2022/2023": { start: "2022-07-01", end: "2023-05-28", fd: null, fs: 7425 }
      "2023/2024": { start: "2023-07-01", end: "2024-05-26", fd: null, fs: 9525 }
      "2024/2025": { start: "2024-07-05", end: "2025-05-25", fd: null, fs: 12136 }
      "2025/2026": { start: "2025-07-04", end: null, fd: null, fs: 15234, current: true }

  AUT_BL:
    name: "Bundesliga"
    country: "Austria"
    tier: 3
    season_format: "jul_may"
    football_data_code: "AUT"
    football_data_type: "extra"
    understat_name: null
    fbref_id: "56"
    xg_source: "fbref"
    flashscore_path: "austria/bundesliga"
    footystats_name: "Austria Bundesliga"
    seasons:
      "2021/2022": { start: "2021-07-23", end: "2022-05-22", fd: null, fs: 6008 }
      "2022/2023": { start: "2022-07-22", end: "2023-05-28", fd: null, fs: 7890 }
      "2023/2024": { start: "2023-07-28", end: "2024-05-26", fd: null, fs: 9954 }
      "2024/2025": { start: "2024-07-26", end: "2025-05-25", fd: null, fs: 12472 }
      "2025/2026": { start: "2025-07-25", end: null, fd: null, fs: 14923, current: true }

  SWI_SL:
    name: "Super League"
    country: "Switzerland"
    tier: 3
    season_format: "jul_may"
    football_data_code: "SWZ"
    football_data_type: "extra"
    understat_name: null
    fbref_id: "57"
    xg_source: "fbref"
    flashscore_path: "switzerland/super-league"
    footystats_name: "Switzerland Super League"
    seasons:
      "2021/2022": { start: "2021-07-24", end: "2022-05-22", fd: null, fs: 6044 }
      "2022/2023": { start: "2022-07-16", end: "2023-05-28", fd: null, fs: 7504 }
      "2023/2024": { start: "2023-07-22", end: "2024-05-25", fd: null, fs: 9580 }
      "2024/2025": { start: "2024-07-20", end: "2025-05-24", fd: null, fs: 12326 }
      "2025/2026": { start: "2025-07-19", end: null, fd: null, fs: 15047, current: true }
```

### 14.2 bookmakers.yaml

```yaml
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

  1xbet:
    display_name: "1xBet"
    type: "retail"
    flashscore_aliases: ["1xBet"]

  betano:
    display_name: "Betano"
    type: "br_retail"
    flashscore_aliases: ["Betano"]

  sportingbet:
    display_name: "Sportingbet"
    type: "br_retail"
    flashscore_aliases: ["Sportingbet"]

  superbet:
    display_name: "Superbet"
    type: "br_retail"
    flashscore_aliases: ["Superbet"]

  betnacional:
    display_name: "BetNacional"
    type: "br_retail"
    flashscore_aliases: ["BetNacional", "Bet Nacional"]

  estrela_bet:
    display_name: "EstrelaBet"
    type: "br_retail"
    flashscore_aliases: ["EstrelaBet", "Estrela Bet"]

  kto:
    display_name: "KTO"
    type: "br_retail"
    flashscore_aliases: ["KTO"]

  7k:
    display_name: "7K"
    type: "br_retail"
    flashscore_aliases: ["7K"]

  f12:
    display_name: "F12"
    type: "br_retail"
    flashscore_aliases: ["F12", "F12.bet"]

  multibet:
    display_name: "Multibet"
    type: "br_retail"
    flashscore_aliases: ["Multibet"]
```

### 14.3 markets.yaml

```yaml
markets:
  full_time:
    - type: "1x2"
      period: "ft"
      lines: null
      selections: ["home", "draw", "away"]
      n_ways: 3

    - type: "ou"
      period: "ft"
      lines: [0.5, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5]
      selections: ["over", "under"]
      n_ways: 2

    - type: "ah"
      period: "ft"
      lines: "dynamic_balanced_pm2"
      selections: ["home", "away"]
      n_ways: 2

    - type: "dc"
      period: "ft"
      lines: null
      selections: ["1X", "12", "X2"]
      n_ways: 3

    - type: "dnb"
      period: "ft"
      lines: null
      selections: ["home", "away"]
      n_ways: 2

    - type: "btts"
      period: "ft"
      lines: null
      selections: ["yes", "no"]
      n_ways: 2

  half_time:
    - type: "1x2_ht"
      period: "ht"
      lines: null
      selections: ["home", "draw", "away"]
      n_ways: 3

    - type: "ou_ht"
      period: "ht"
      lines: [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]
      selections: ["over", "under"]
      n_ways: 2

    - type: "ah_ht"
      period: "ht"
      lines: "dynamic_balanced"
      selections: ["home", "away"]
      n_ways: 2
```

---

## 15. Estrutura de Código

```
src/
├── collectors/
│   ├── __init__.py
│   ├── base.py                       # BaseCollector + CollectResult
│   ├── flashscore/
│   │   ├── __init__.py
│   │   ├── driver.py                 # create_chrome_driver + CookieHandler + SeleniumPool
│   │   ├── parser.py                 # HTML → OddsRecord[]
│   │   ├── odds_collector.py         # FlashScoreOddsCollector(BaseCollector)
│   │   └── selectors.py             # CSS/XPath ISOLADOS
│   ├── footystats/
│   │   ├── __init__.py
│   │   ├── api_client.py             # FootystatsClient (httpx)
│   │   ├── matches_collector.py      # FootystatsMatchesCollector(BaseCollector)
│   │   ├── fixtures_collector.py
│   │   └── backfill.py
│   ├── football_data/
│   │   ├── __init__.py
│   │   ├── csv_collector.py          # Download + parse (main + extra)
│   │   └── alias_seed.py             # generate_alias_seed_csv()
│   ├── fbref/
│   │   ├── __init__.py
│   │   ├── scraper.py                # requests + BS4
│   │   └── parser.py
│   ├── understat/
│   │   ├── __init__.py
│   │   └── xg_collector.py
│   ├── odds_api/
│   │   ├── __init__.py
│   │   └── api_collector.py
│   └── api_football/
│       ├── __init__.py
│       └── api_collector.py
├── normalizer/
│   ├── __init__.py
│   ├── team_resolver.py
│   ├── match_resolver.py
│   ├── bookmaker_resolver.py
│   ├── odds_normalizer.py
│   └── dedup.py
├── scheduler/
│   ├── __init__.py
│   ├── jobs.py
│   ├── key_manager.py
│   └── gameday.py
├── backfill/
│   ├── __init__.py
│   └── runner.py
├── config/
│   ├── leagues.yaml
│   ├── bookmakers.yaml
│   ├── markets.yaml
│   └── loader.py
├── alerts/
│   └── telegram.py
├── db/
│   ├── __init__.py
│   ├── connection.py                 # asyncpg pool
│   └── queries.py
└── tests/
    ├── unit/
    │   ├── test_dedup.py
    │   ├── test_team_resolver.py
    │   ├── test_odds_normalizer.py
    │   ├── test_transform_footystats.py
    │   ├── test_transform_football_data.py
    │   └── test_key_manager.py
    ├── integration/
    │   ├── test_footystats_collector.py
    │   ├── test_flashscore_collector.py
    │   ├── test_understat_collector.py
    │   ├── test_fbref_collector.py
    │   ├── test_odds_api_collector.py
    │   └── test_backfill_pipeline.py
    └── conftest.py
```

---

## 16. Diagrama de Sequência

### 16.1 Coleta de Odds (FlashScore)

```
Scheduler        FlashScore        Normalizer        DB           Telegram
   │              Collector                            │
   │── trigger ─────►│                                │
   │                  │── acquire driver (Pool)        │
   │                  │── load cookies                 │
   │                  │── navigate to match             │
   │                  │── wait for odds table           │
   │                  │                                │
   │                  │ [FOR each market]              │
   │                  │   │── click market tab          │
   │                  │   │── wait load                 │
   │                  │   │ [FOR each line if OU/AH]   │
   │                  │   │   │── click line            │
   │                  │   │   │── parse → OddsRecord[]  │
   │                  │   │── random_delay()            │
   │                  │                                │
   │                  │── CollectResult ───────────►│   │
   │                  │                            │   │
   │                  │         │── resolve bookmaker ──►│
   │                  │         │── resolve match ──────►│
   │                  │         │── compute hash         │
   │                  │         │── dedup check ────────►│
   │                  │         │ [IF new] INSERT ──────►│
   │                  │         │ [IF skip] count++      │
   │                  │                                  │
   │                  │── release driver (Pool)          │
   │◄── log result ───│                                  │
   │── INSERT ingestion_log ────────────────────────────►│
   │ [IF failed] send_alert ────────────────────────────────►│
```

### 16.2 Pós-Jogo (Footystats + Closing)

```
Scheduler        Footystats        Normalizer        DB
   │              Collector                            │
   │── T+2h30 ─────►│                                │
   │                  │── GET league-matches?date=X    │
   │                  │◄── JSON                        │
   │                  │ [FOR each match]               │
   │                  │   │── transform values          │
   │                  │   │── resolve teams ───────────►│
   │                  │   │── resolve match ───────────►│
   │                  │   │── UPDATE matches ──────────►│
   │                  │   │── UPSERT match_stats ──────►│
   │                  │── mark_closing_odds() ─────────►│
   │◄── log result ───│                                │
```

### 16.3 Backfill Pipeline

```
BackfillRunner
   │── ETAPA 1: Football-Data CSV (~130 CSVs) → matches + odds_history seed
   │── ETAPA 2: ⏸️ Marcelo revisa aliases CSV
   │── ETAPA 3: Footystats API (130 season requests) → match_stats
   │── ETAPA 4: Understat (5 ligas × 5 temp) → xG granular
   │── ETAPA 5: FBRef (19 ligas × 5 temp) → xG
   │── LOG final + alerta ✅
```

---

## 17. Testes

### 17.1 Testes Unitários

| Teste | Arquivo | Validação |
| --- | --- | --- |
| Hash determinístico | `test_dedup.py` | Mesmo input → mesmo hash |
| Hash com NULL | `test_dedup.py` | `line=None` gera hash consistente |
| Overround 3-way | `test_odds_normalizer.py` | (2.10/3.40/3.50) → ≈0.058 |
| Overround 2-way | `test_odds_normalizer.py` | (1.90/2.00) → ≈0.026 |
| Team resolve hit | `test_team_resolver.py` | Alias conhecido → team_id |
| Team resolve miss | `test_team_resolver.py` | Desconhecido → None + unknown_aliases |
| Goals minutes parse | `test_transform_footystats.py` | `"23,67,89"` → `[23, 67, 89]` |
| Goals minutes empty | `test_transform_footystats.py` | `""` → `None` |
| Goals minutes None | `test_transform_footystats.py` | `None` → `None` |
| Footystats -1 | `test_transform_footystats.py` | `-1` → `None` |
| Footystats xG string | `test_transform_footystats.py` | `"1.45"` → `1.45` |
| Football-Data NaN | `test_transform_football_data.py` | `NaN` → `None` |
| Football-Data date | `test_transform_football_data.py` | `"25/12/2024"` + `"15:00"` → datetime |
| Key rotation | `test_key_manager.py` | 7 keys, 100 req → distribui |
| Key exhaustion | `test_key_manager.py` | Limite atingido → erro |
| AH balanced | `test_odds_normalizer.py` | 8 linhas → mais equilibrada |
| AH range | `test_odds_normalizer.py` | balanced=-0.75 → [-1.25...-0.25] |
| Config loader | `test_config.py` | 26 ligas carregadas, 130 season IDs ≠ null |

### 17.2 Testes de Integração

| Teste | Arquivo | Validação |
| --- | --- | --- |
| Footystats 1 temp | `test_footystats_collector.py` | GET → parse → campos preenchidos |
| Footystats -1 | `test_footystats_collector.py` | -1 → NULL no banco |
| FlashScore 1 jogo | `test_flashscore_collector.py` | Navega → parse → odds Pinnacle |
| FlashScore cookie | `test_flashscore_collector.py` | 1a vez aceita; 2a reutiliza |
| FlashScore selector quebrado | `test_flashscore_collector.py` | → FAILED + alerta |
| Understat 1 liga | `test_understat_collector.py` | → xG por jogo |
| FBRef 1 liga | `test_fbref_collector.py` | → xG por jogo |
| Odds API | `test_odds_api_collector.py` | → odds Pinnacle |
| Dedup e2e | `test_dedup.py` | 2x insert mesma odd → 1 registro |
| Backfill mini | `test_backfill_pipeline.py` | 1 liga × 1 temp → matches + stats + odds |
| Match resolver cross | `test_backfill_pipeline.py` | 2 fontes → mesmo match_id |
| is_opening | `test_dedup.py` | 1o insert → True; 2o → False |
| is_closing | `test_dedup.py` | mark_closing → último antes kickoff |

### 17.3 Fixtures ([conftest.py](http://conftest.py/))

```python
@pytest.fixture
async def test_db():
    pool = await asyncpg.create_pool(
        "postgresql://test:test@localhost:5432/maisevplus_test"
    )
    async with pool.acquire() as conn:
        await conn.execute(open("sql/schema.sql").read())
    yield pool
    async with pool.acquire() as conn:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    await pool.close()

@pytest.fixture
def sample_footystats_response():
    return {
        "id": 123456, "date_unix": 1711900800,
        "home_name": "Arsenal", "away_name": "Chelsea",
        "game_week": 30, "status": "complete",
        "homeGoalCount": 2, "awayGoalCount": 1,
        "homeHTGoalCount": 1, "awayHTGoalCount": 0,
        "homeGoals": "23,67", "awayGoals": "55",
        "team_a_xg": 2.14, "team_b_xg": 0.87,
        "team_a_shots": 15, "team_b_shots": 8,
        "team_a_shotsOnTarget": 7, "team_b_shotsOnTarget": 3,
        "team_a_shotsOffTarget": 8, "team_b_shotsOffTarget": 5,
        "team_a_possession": 58.3, "team_b_possession": 41.7,
        "team_a_corners": 7, "team_b_corners": 3,
        "team_a_yellow_cards": 2, "team_b_yellow_cards": 3,
        "team_a_red_cards": 0, "team_b_red_cards": 0,
    }
```

---

## 18. Monitoramento e Alertas

### 18.1 Health Checks

| Check | Frequência | Alerta se |
| --- | --- | --- |
| Selenium Pool | 5 min | Nenhuma instância disponível por 10min |
| Footystats API | 5 min | HTTP 5xx ou timeout 3x seguidas |
| Último sucesso/fonte | 15 min | Nenhum success nas últimas 2h |
| Records/hora | 1h | 0 novos quando havia jogos |
| DB connection pool | 5 min | Pool exausto |
| Disk usage | 1h | > 80% |
| Unknown aliases | 1h | Novos não resolvidos |
| API keys usage | 6h | Qualquer key > 80% do limite |

### 18.2 Telegram

```python
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def send_alert(message: str, level: str = "warning"):
    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}
    text = f"{emoji.get(level, '📢')} *M1 — Ingestão*\\n{message}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"<https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage>",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
            )
    except:
        pass
```

---

## 19. Interfaces com Outros Módulos

### 19.1 M1 → M2 (Feature Engineering)

| Tabela | Uso |
| --- | --- |
| `matches` | Variáveis target + temporal |
| `match_stats` | Features de performance |
| `odds_history` | Features de mercado |
| `leagues`, `teams`, `seasons` | Dimensões |

### 19.2 M1 → M4 (Value Identification)

| Tabela | Uso |
| --- | --- |
| `odds_history` (último snapshot) | Cálculo de EV |
| `odds_history` (série temporal) | Detecção de steam moves |
| `odds_history` WHERE `is_closing` | CLV tracking |
| `bookmakers` | Cluster sharp/retail |

### 19.3 M1 → M6 (Execution)

| Tabela | Uso |
| --- | --- |
| `odds_history` (mais recente) | Line shopping: onde apostar |

### 19.4 M1 → M9 (Backtesting)

| Tabela | Uso |
| --- | --- |
| `matches` (histórico) | Simulação de resultados |
| `odds_history` (backfill) | Simulação de apostas |
| `match_stats` (histórico) | Backtest de modelos |

---

## 20. Critérios de Aceite

| # | Critério | Verificação |
| --- | --- | --- |
| 1 | 6 fontes ativas | `SELECT source, MAX(started_at) FROM ingestion_log WHERE status='success' GROUP BY source` — todas < 24h |
| 2 | Backfill matches | `SELECT COUNT(*) FROM matches` > 50.000 |
| 3 | Backfill stats | `SELECT COUNT(*) FROM match_stats` > 45.000 |
| 4 | Backfill odds | `SELECT COUNT(*) FROM odds_history` > 250.000 |
| 5 | Stats completas | xG + chutes + escanteios FT preenchidos para >95% dos jogos finished |
| 6 | Schedule 48h | 0 `failed` em `ingestion_log` por 48h |
| 7 | Dedup | Zero duplicatas (query GROUP BY HAVING count > 1) |
| 8 | Normalização | `SELECT COUNT(*) FROM unknown_aliases WHERE resolved=FALSE` = 0 |
| 9 | Fallback | FlashScore off → The Odds API assume (teste manual) |
| 10 | Multi-key | Keys rotacionando dentro dos limites |
| 11 | 13 casas | Pinnacle + Bet365 + ≥3 BR coletadas para jogos do dia |
| 12 | is_opening/closing | Marcados corretamente para jogos finished |
| 13 | Alertas | Telegram notifica quando scraper falha 3x |
| 14 | 26 ligas | Todas com pelo menos 1 temporada em `seasons` + jogos em `matches` |
| 15 | xG cobertura | 24 ligas com xG (Understat + FBRef), 2 ligas com Footystats fallback |
| 16 | Season IDs | 130 season IDs carregados, todos ≠ null |

---

## 21. Estimativa de Tempo

| # | Subtask | Dias | Dependência |
| --- | --- | --- | --- |
| 1 | Schema DDL + indexes + hypertable + seeds | 2 | M0 |
| 2 | Config files (YAML 26 ligas + 130 seasons) + loader | 1.5 | — |
| 3 | Normalizer (Team, Match, Bookmaker, dedup) | 2 | Schema |
| 4 | Football-Data CSV collector + alias seed (~130 CSVs) | 2.5 | Schema + Normalizer |
| 5 | **⏸️ Revisão aliases** (Marcelo, ~580 times) | 1.5 | #4 |
| 6 | Import aliases + Footystats collector + backfill (26 ligas) | 3 | #5 |
| 7 | Understat collector + backfill Top 5 | 1 | Schema + Normalizer |
| 8 | FBRef collector + backfill 19 ligas | 2 | Schema + Normalizer |
| 9 | FlashScore collector (Selenium + 13 casas × 9 mercados) | 4 | Schema + Normalizer + Pool |
| 10 | The Odds API collector (5 keys) | 1 | KeyManager |
| 11 | API-Football collector (7 keys) | 1 | KeyManager |
| 12 | KeyManager (multi-key rotation + reset) | 1 | — |
| 13 | Scheduler (todos os jobs + gameday dinâmico) | 2 | Coletores |
| 14 | Alertas Telegram | 0.5 | — |
| 15 | Testes unitários + integração | 2 | Tudo |
| 16 | Backfill execução supervisionada (~24h) | 1.5 | Tudo |
|  | **Total** | **~29 dias úteis (~6 semanas)** |  |

### Caminho Crítico

```
Schema(2d) → Normalizer(2d) → Football-Data(2.5d) → ⏸️ Aliases(1.5d) → Footystats(3d) → Scheduler(2d) → Testes(2d) → Backfill(1.5d)
                                                                        ↗ FlashScore(4d) ↗
                                                        KeyManager(1d) → Odds API(1d) ──↗
                                                                       → API-Football(1d)↗
                                                        Understat(1d) ────────────────↗
                                                        FBRef(2d) ────────────────────↗
                                                        Config(1.5d) ─────────────────↗
```

---

## 22. Riscos e Mitigações

| # | Risco | Prob | Impacto | Mitigação |
| --- | --- | --- | --- | --- |
| 1 | FlashScore muda selectors | **Alta** | Médio | `selectors.py` isolado; alerta automático; The Odds API fallback |
| 2 | CAPTCHA/bloqueio FlashScore | Média | Alto | Rate limiting; UA rotation; delay humanizado; proxies pós-MVP |
| 3 | Footystats HT indisponível | Média | Baixo | NULL aceito; GENERATED com NULL handling |
| 4 | Footystats retorna -1 | **Certa** | Baixo | Transform → NULL antes do INSERT |
| 5 | FBRef não cobre SCO_L1/SCO_L2 | **Certa** | Baixo | xG via Footystats (básico) |
| 6 | Football-Data extras têm menos odds | **Certa** | Baixo | Colunas ausentes → NULL; odds real-time via FlashScore |
| 7 | API-Football bloqueia multi-conta | Baixa | Médio | 3 contas reserva; IPs diferentes |
| 8 | The Odds API 2.500 req insuficientes | Média | Baixo | Priorizar Pinnacle; upgrade $30/mês se necessário |
| 9 | Aliases não resolvidos | **Alta** (início) | Alto | `unknown_aliases` + alerta Telegram; pipeline skip + log |
| 10 | 580 times para mapear | **Certa** | Médio | CSV bem formatado; revisão incremental por liga |
| 11 | Volume FlashScore (180 jogos/dia pico) | Média | Médio | Priorização por tier; 2 instâncias Selenium |
| 12 | FBRef backfill 14h | **Certa** | Baixo | Rate limit respeitado; roda overnight |

---

> **FIM DO PRD M1 v5 DEFINITIVO26 ligas · 14 países · 130 season IDs · 13 casas · 9 mercados · 6 fontes · Zero nulls no config.**
>