# SPECS.md

# [SPECS.md](http://specs.md/) — Módulo 1: Coleta de Dados (Ingestão)

> Especificação técnica completa do M1 atualizada conforme ciclo atual de desenvolvimento.
Fonte de verdade para implementação e estado da infraestrutura.
Documentos complementares: `SCHEMA.md` (DDL + indexes), `TASKS.md` (breakdown de execução).

---

## Índice

1. [Decisões Consolidadas (Atualizado)](#1-decisoes-consolidadas-atualizado)
2. [Fontes de Dados (Revisão Pós-Discovery)](#2-fontes-de-dados-revisao-pos-discovery)
3. [Ligas no Escopo](#3-ligas-no-escopo)
4. [Casas de Apostas e Mercados](#4-casas-de-apostas-e-mercados)
5. [Schedule de Coleta e Orquestração](#5-schedule-de-coleta-e-orquestracao)
6. [Resolução Dinâmica de Aliases (CLI)](#6-resolucao-dinamica-de-aliases-cli)
7. [Foco Estratégico Atual: O Backfill](#7-foco-estrategico-atual-o-backfill)

---

## 1. Decisões Consolidadas (Atualizado)

| Ponto | Decisão Consolidada |
| --- | --- |
| **Resultados Base** | Footystats API (key ilimitada) — Responsável por popular a base de matches e as competições ao longo do tempo. |
| **Estatísticas Detalhadas** | API-Football — Oficialmente assumiu o lugar do Understat e FBRef. Cobre `match_stats` avançadas, Lineups, Eventos (Gols/Cartões) e Players. Alta cobertura (7 chaves × 100/dia = 700 req/dia no limit básico, e chaves VIP 7500/dia). |
| **Odds Tempo Real e Handi.** | Flashscore (Camoufox headless + VPN proxy) — Odds API descontinuada. Flashscore (Camoufox) é a fonte única de odds. |
| Período histórico | 5 temporadas fechadas + atual em andamento: 2021/22 a 2025/26. |
| Total de ligas | **51 ligas em 32 países**, subdivididas em Tiers priorizados. |
| Casas Primárias (CLV) | Pinnacle (1) → Betfair (2) → Bet365 (3). Mais ~10 casas BR e Internacionais em captura complementar no Flashscore. |
| Resumo do Refatoramento | Understat e FBRef suspensos devido à complexidade fragmentada. Odds API descontinuada. Flashscore (Camoufox) é a fonte única de odds. |

---

## 2. Fontes de Dados (Revisão Pós-Discovery)

### 2.1 Mapa Atual de Responsabilidades

| Fonte | Tipo de Acesso | Cobertura | Status no Backfill |
| --- | --- | --- | --- |
| **Footystats** | API REST (No Lim.) | Partidas, Schedules Calendários (Fixtures), Placar HT/FT. | **100% Concluído.** Seed fundamental gerada. |
| **API-Football** | API REST (Multi-Keys)| xG, Chutes a gol/fora, Posse de Bola, Escanteios, Passes. Escalações Completas, Perf. por Jogador, Timeline de Eventos. | **Rodando Pesado.** Múltiplos scripts coletando anos anteriores regressivamente. |
| **Flashscore** | Camoufox (Playwright) | Histórico massivo de Odds (1x2, O/U, Asian Hand., BTTS) pré-live e closing line para cálculo atuarial. | **Rodando.** `run_flashscore_backfill.py` rotaciona pelas ligas preenchendo as Odds. |

### 2.2 Diagrama de Ingestão Revisado

```markdown
┌─────────────────────────────────────────────────────────────┐
│                     FONTES DE DADOS M1                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐   ODDS CLV / PRÉ-LIVE  ┌───────────────┐  │
│  │  Flashscore  │ ────────────────────── │odds_history   │  │
│  │  (Camoufox)  │                        │(hypertable)   │  │
│  └──────────────┘                        └───────────────┘  │
│                                                             │
│  ┌──────────────┐   PARTIDAS / RESULT    ┌───────────────┐  │
│  │  Footystats  │ ────────────────────── │matches        │  │
│  │  (REST API)  │   Cria a seed base     └───────────────┘  │
│  └──────────────┘                                           │
│                                                             │
│  ┌──────────────┐   ESTATÍSTICAS MASSIVAS┌───────────────┐  │
│  │ API-Football │ ────────────────────── │match_stats    │  │
│  │ (REST / VIP) │   xG, passes, lineups, │match_events   │  │
│  └──────────────┘   players, incidents   │lineups        │  │
│                                          └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Ligas no Escopo (Manutenção 51 Ligas)

### Tier 1 — Main Leagues
Inglaterra (PL, CH, L1, L2, NL), Alemanha (BL, B2), Itália (SA, SB), França (L1, L2), Espanha (PD, SD), Escócia (PL, CH, L1, L2).
*Todos cobertos unificadamente agora via API-Football e Flashscore, simplificando o map.*

### Tier 2 e Tier 3 — Europeias Extras, Américas, Ásia, Ligas A-B
Holanda (ED), Bélgica (PL), Portugal (PL), Turquia (SL), Grécia (SL), Suécia (Allsvenskan, Superettan), Finlândia (Veikkausliiga, Ykkösliiga), Noruega (Eliteserien, OBOS-ligaen), Irlanda (Premier Division).
Brasil (Série A, Série B), México (Liga MX), Argentina## 5. Schedule de Coleta e Orquestração

### Lógica Produtiva (Daily)
A orquestração utiliza uma **grade rígida no APScheduler** configurada em `src/scheduler/orchestrator.py` dividindo os backfills e rastreamentos diários em janelas horárias desencontradas para contornar sobreposições.
Janelas notáveis Flashscore:
- **Tracking Prematch:** Rastreamentos divididos em 3 execuções diárias com limites estritos de runtime:
  - **06:20 BRT** (Max 1h50m de duração)
  - **13:50 BRT** (Max 1h50m de duração)
  - **21:20 BRT** (Max 2h30m de duração)
- **Backfill Múltiplo:** 5 janelas cadenciadas de *Historical Backfill* (`00:45`, `08:20`, `11:05`, `15:50`, `18:35`).
- **Validação de Layout:** O script `scripts/check_flashscore_integrity.py` roda diariamente às `03:00 BRT` para testar os seletores do DOM do Flashscore contra a Premier League. Se falhar, envia um alerta **CRITICAL** no Telegram contendo o trecho do HTML que quebrou e um prompt pré-formatado pronto para cópia/correção via IA.
- **Cleaner de Status:** O script `scripts/run_flashscore_scheduled_cleaner.py` roda diariamente às `04:20 BRT` buscando partidas marcadas como `'scheduled'` com kickoff no passado (janela > 3h) para atualizá-las diretamente a partir de suas páginas de detalhes.
- **Cluster Discovery:** O script `scripts/run_flashscore_discovery_fixtures.py` roda diariamente às `05:15 BRT` e associa IDs de jogos futuros. Ele divide as ligas em 2 clusters de forma determinística (par/ímpar por dia do ano) e executa apenas para ligas que não tiveram discovery nas últimas 40 horas.
- **Watchdog de Backfill:** O script `scripts/check_backfill_status.py` roda de hora em hora (via APScheduler) e inspeciona se o backfill sequencial está ativo. Se inativo, ele determina se o encerramento ocorreu por finalização natural das ligas e temporadas pendentes (com 100% dos aliases normalizados e 0 partidas a processar) ou devido a um erro, notificando com alertas ricos no Telegram. Ele também valida o status do serviço systemd e a existência de processos ativos no sistema operacional.
- **Limites Globais:** O runtime de todos os crawlers acoplados ao Flashscore usam limite temporal hard guardado pelo orchestrator de **160 minutos (2h40m)**, e um soft timeout interno do script de **155 minutos (~2.58h)** para desligamento suave e sem travamentos no sistema OS, garantindo no mínimo 5 minutos de idle state antes da próxima janela.

Em paralelo, a rotina `schedule_gameday_jobs` (acionada `00:30 BRT`) orquestra coletas on-demand ao longo do dia para as *partidas confirmadas daquele ciclo* (T-60, T-30, etc).

### Gestão Limites (API-Football)
O cluster tem keys espalhadas geridas no `KeyManager`. Se é limite diário (ex: 7000 req), o sistema paralisa e hiberna via exception, relatando no Telegram e reiniciando na virada do cronjob a meia noite UTC.

---

## 6. Resolução Dinâmica de Aliases (CLI)

Historicamente, os times têm nomes erráticos entre as fontes (ex: "Manchester United" vs "Man United").
A infra resolve isso hoje com:
- `resolve_apifootball_aliases.py`
- `resolve_flashscore_aliases.py`

**Lógica interna:**
1. Hit na API ou Raspagem para pegar os 'Raw Names'.
2. Lookup no BD `team_aliases`. Achou? Mapeia o ID.
3. Não achou? Aplica Regex/Fuzzy Match (`difflib Ratio > 0.8`).
4. Autoresolveu confiavelmente? Grava de volta silencioso.
5. Inconclusivo? Renderiza CLI Interativa, exibe Top 5 candidatos ao programador, e pede input [1], [2], [M]anual.
Zero perda de histórico.

---

## 7. Foco Estratégico Atual: O Backfill

A etapa vigente do projeto consiste em robustecer a base de dados utilizando scripts arquitetados exclusivamente para englobar os dados parados no passado (temporadas encerradas de 21/22 a 24/25).

### 7.1. API-Football Backfill (`run_apifootball_backfill.py`)
- O script `run_apifootball_backfill.py` rastreia ligas descendentes (2025 -> 2024 -> 2021).
- Usa `JSON states` para retomar operações se crashar.
- Verifica modularmente: Falta a stat? (Hit). Faltam Eventos? (Hit). Não resgata payload duplicado.
- Há a subferramenta `run_apifootball_stats_only.py` desenhada sutilmente para tapar "buracos" esparsos onde o collect de endpoints statistics falhou no passado isoladamente, filtrando puramente via `blocked_shots_home IS NULL`.

### 7.2. Flashscore Backfill (`run_flashscore_backfill.py`)
- Filtra jogos terminados `status = 'finished'` contendo `flashscore_id` e cuja flag boolean `scraping_flashscore` é falsa/nula.
- Interfere num Chromium isolado rodando o wrapper `FlashscoreOddsCollector` via `xvfb-run`. Injeta o dump de odds brutas históricas na bucket TimescaleDB. Modera IPs entre requests.
- Desliga graciosamente ao atingir 155 minutos de operação constante (`--timeout-hours 2.58`). Monitorado na nova tabela `scraping_health`.

### 7.3. Flashscore Complementary (`run_flashscore_complementary.py`)
- Um braço cirúrgico do backfill voltado apenas a suprir lacunas dos mercados ("btts", "1x2", "dc", "dnb" e "stats") em partidas que outrora extraíram com sucesso *apenas* "ah" (Asian Handicap) e "ou".
- Opera sobre tabela fila `fc_complementary_queue` populada com base em exports estáticos JSON de segurança, não tocando em dados regulares. Upsert usa `COALESCE` para não sobrepor outras estatísticas pré-existentes limpas.

### 7.4. Limpeza de Status Passados e Monitoramento de Layout
- **Cleaner de Status (`run_flashscore_scheduled_cleaner.py`):** Realiza uma varredura direta via URL de detalhes dos jogos (`https://www.flashscore.com/match/{id}/`) para corrigir partidas travadas como `'scheduled'` que já ocorreram, identificando placares finais, do primeiro tempo, ou adiamentos/cancelamentos.
- **Validador de Integridade (`check_flashscore_integrity.py`):** Script autônomo que testa seletores DOM do Flashscore diariamente, emitindo alertas imediatos no Telegram caso alguma classe CSS tenha sido modificada, facilitando auto-correção via IA.

**Mapeamento e Progresso:** Prioridade MÁXIMA nestes pipelines. Qualquer novo desenvolvimento que não seja para fix de selectors nesses scripts não agregará valor neste subciclo, portanto manter atenção concentrada em estabilidade de runtime nesses arquivos pesados.