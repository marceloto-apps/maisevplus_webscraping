# TASKS.md

# [TASKS.md](http://tasks.md/) — Módulo 1: Coleta de Dados (Ingestão)

> Breakdown de implementação do M1. Cada task tem escopo, dependências, entregáveis e critério de aceite.
Documentos de referência: `SPECS.md` (especificações), `SCHEMA.md` (DDL).

---

## Índice

1. [Visão Geral](#1-visao-geral)
2. [Grafo de Dependências](#2-grafo-de-dependencias)
3. [Fase 1 — Fundação](#3-fase-1--fundacao)
4. [Fase 2 — Coletores Principais](#4-fase-2--coletores-principais)
5. [Fase 3 — Orquestração](#5-fase-3--orquestracao)
6. [Fase 4 — Backfill (Status Atual)](#6-fase-4--backfill-status-atual)
7. [Fase 5 — Validação e Go-Live](#7-fase-5--validacao-e-go-live)
8. [Checklist Final](#8-checklist-final)

---

## 1. Visão Geral

Fase 1 — Fundação           [CONCLUÍDO] T01–T04
Fase 2 — Coletores Main     [CONCLUÍDO] T05–T07
Fase 3 — Orquestração       [CONCLUÍDO] T08–T09
Fase 4 — Backfill           [EM ANDAMENTO] T10–T14
Fase 5 — Validação          [PENDENTE] T15–T16
─────────────────────────────────────────────
*Status: Foco total atual na Fase 4 (Backfill máximo da base).*

**Convenções:**

- ✅ = critério de aceite da task
- 🔗 = dependência (task que precisa estar concluída)
- 📁 = arquivo(s) entregue(s)

---

## 2. Grafo de Dependências

```markdown
T01 ─────────────────────────────────────────────────────────────┐
│                                                               │
T02 ──┐                                                          │
│    │                                                          │
T03 ──┤                                                          │
│    │                                                          │
T04 ──┼──── T05 (FootyStats) ──────── T10 (Backfill FootyStats) │
│      │                            │                      │
│     T06 (Flashscore Odds) ────── T11 (Backfill Flashscore) │
│      │                            │                      │
│     T07 (API-Football) ───────── T12 (Backfill API-Foot)   │
│                                   │                      │
│                                  T13 (Resolução Aliases) │
│                                   │                      │
│     T08 (Scheduler) ──────────── T15 (Testes / Validação)│
│      │                            │                      │
│     T09 (Alertas Tg) ─────────── T16 (Go-Live)           │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Fase 1 — Fundação

### T01 — Schema DDL + Extensions + Seeds
**Status:** ✅ Concluído
**Escopo:**
- Criar banco `maisevplus` com extensions (TimescaleDB, pgcrypto).
- Executar DDL base e criar hypertable `odds_history`.
- Inserir seeds de leagues e seasons.

### T02 — Estrutura do Projeto + Config YAMLs
**Status:** ✅ Concluído
**Escopo:**
- Criar infra de diretórios.
- Subir YAMLs e ENVs da aplicação.

### T03 — BaseCollector + Normalizer Core
**Status:** ✅ Concluído
**Escopo:**
- Normalizadores: `TeamResolver`, `MatchResolver`.
- Lógica de deduplicação e overround.

### T04 — Conexão DB + Helpers
**Status:** ✅ Concluído
**Escopo:**
- Asyncpg DB pool manager e Logger estruturado.

---

## 4. Fase 2 — Coletores Principais

### T05 — FootyStats Collector (Resultados e Fixtures)
**Status:** ✅ Concluído
**Escopo:**
- Coletor base da API Footystats.
- Coleta as fixtures, resultados e dados primários `match_stats` com total cobertura.
- Popula campos `kickoff`, HT/FT scores e consolida o jogo no DB.

### T06 — Flashscore Odds Collector (Pivot / Fonte Primária de Odds)
**Status:** ✅ Concluído
**Escopo:**
- Scraping headless com Playwright/Camoufox.
- Burla proteções web (Cloudflare) via Stealth Browsers.
- Retira as odds de fechamento pré-live via request XHR.
- Responsável por popular a hypertable `odds_history`.

### T07 — API-Football Collector (Estatísticas Avançadas, Eventos e Escalações)
**Status:** ✅ Concluído
**Escopo:**
- Scripts para obter de forma massiva xG, Chutes, Passes, Posse de bola, Escalações (Lineups), Jogadores e Eventos.
- Substituto oficial dos antigos FBRef e Understat pela confiabilidade e limite alto.
- Mapeamento dinâmico de aliases API-Football <> DB.

---

## 5. Fase 3 — Orquestração

### T08 — Scheduler e Key Manager
**Status:** ✅ Concluído
**Escopo:**
- APScheduler integrado gerenciando o consumo dinâmico.
- Key Manager multi-keys (7 keys de API-Football).

### T09 — Alertas Telegram
**Status:** ✅ Concluído
**Escopo:**
- Mensageria integrada ao longo dos scripts alertando success, warning, error. Limiters detectáveis.

---

## 6. Fase 4 — Backfill (Status Atual)
> **Fase Crítica:** Foco de recursos para termos o máximo possível de dados na base.

### T10 — Backfill: FootyStats (A Base)
**Status:** ✅ Concluído (100%)
**Escopo:**
- Backfill de 5+ temporadas (2021 a Atual).
- Criar todos os Matches na base de forma retroativa.
- Resolvidas 130/130 Seasons ativas.

### T11 — Backfill: Flashscore (Odds)
**Status:** 🔄 Em Andamento Contínuo
**Escopo:**
- Iterar recursivamente os fixtures pelo Flashscore ID.
- Script: `run_flashscore_backfill.py --league ENG_PL`.
- Capturar dados de 13+ casas (Pinnacle/Bet365 prioridade) para jogos históricos passados.
- Tratar rate-limit de IP local / VPN.

### T12 — Backfill: API-Football (Stats Avançadas)
**Status:** 🔄 Em Andamento Contínuo
**Escopo:**
- Roda de modo cron/backfill reverse.
- Alimenta `match_stats` onde `blocked_shots_home` IS NULL (`run_apifootball_stats_only.py`).
- Extração dos 4 endpoints vitais: Statistics, Events, Lineups, Player Stats.
- Script unificado rege limites (max 7300/dia VIP) com fallback dinâmico: `run_apifootball_backfill.py`.

### T13 — Resolução Contínua de Aliases
**Status:** 🔄 Procedimento de Rotina
**Escopo:**
- Executar e monitorar `resolve_apifootball_aliases.py` e `resolve_flashscore_aliases.py`.
- O que não passar no Fuzzy Matcher, passar para a etapa de seleção manual em CLI.
- Evitar NULL teams no match mapping.

### T14 — Validação Football-Data (CSV Seed)
**Status:** ✅ Concluído / Integrado / Obsoleto
**Escopo:** Antigo validador das temporadas, suprimido pelos dados mais ricos das APIs superiores. A base já está pré-semeada.

---

## 7. Fase 5 — Validação e Go-Live

### T15 — Testes GLOBAIS e Resiliência Diária
**Status:** ⏳ Pendente
**Escopo:**
- Scripts de validação dos dados cross-source (`check_db.py`, queries personalizadas).
- Garantir que deduplicação continua blindando falsos volumes.

### T16 — Go-Live / DevOps VPS
**Status:** ✅ Operando / ⏳ Aprimorando
**Escopo:**
- VPS operacional com PM2 / systemd no Ubuntu.
- Backend M2 Node.JS respondendo e orquestrando.

---

## 8. Checklist Final e Próximos Passos (Foco)
1. **[Backfill]** Continuar rodando `run_apifootball_backfill.py` rotineiramente até exaurir 2021 a 2026.
2. **[Backfill]** Maximizar captura de Flashscore usando `run_flashscore_backfill.py`.
3. **[Aliases]** Zerar pendências diárias de Times pelo resolver.
4. **[Limpeza]** Remoção de debugs/dumps inativos -> (Feito recetemente!).
5. **[Dados]** Produzir cobertura de relatórios (ex: > 80% coverage para eventos pre-jogo).