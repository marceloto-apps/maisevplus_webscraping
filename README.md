# maisevplus_webscraping

Sistema de coleta e ingestão de dados de futebol para o projeto **MaisEV+** — odds em tempo real, resultados, estatísticas avançadas e escalações de **51 ligas em 32 países**.

---

## 📌 Visão Geral

Este repositório contém o **Módulo 1 (M1) — Coleta de Dados (Ingestão)** do MaisEV+, responsável por coletar, normalizar e persistir dados de múltiplas fontes em um banco de dados TimescaleDB.

### Fontes de Dados

| Fonte | Tipo | Responsabilidade |
|---|---|---|
| **Footystats API** | HTTP REST | Resultados, schedules/fixtures, placar HT/FT |
| **Flashscore** | Camoufox/Playwright + VPN | Odds em tempo real, closing odds (CLV), Discovery de Partidas, Backfill histórico |
| **API-Football** | HTTP REST (Multi-Keys) | Estatísticas detalhadas de partidas (xG, chutes, escanteios, posse, passes), Escalações completas, Performance por jogador, Eventos (Gols/Cartões) |
| **Football-Data.co.uk** | HTTP (CSV) | Backfill histórico (seed de partidas + odds Pinnacle/B365) |
| **Understat** | Suspenso / Descontinuado | Substituído unificadamente pela API-Football |
| **FBRef** | Suspenso / Descontinuado | Substituído unificadamente pela API-Football |
| **The Odds API** | Descontinuada | Odds API descontinuada. Flashscore (Camoufox) é a fonte única de odds |

---

## 🗂 Estrutura do Projeto

```
maisevplus_webscraping/
├── docs/
│   ├── PRD.md          # Product Requirements Document (M1 completo)
│   ├── SCHEMA.md       # Schema do banco de dados
│   ├── SPECS.md        # Especificações técnicas
│   └── TASKS.md        # Backlog de tarefas
├── .gitignore
└── README.md
```

---

## 🚀 Setup

### Pré-requisitos

- Python 3.11+
- PostgreSQL 15+ com TimescaleDB
- Google Chrome + ChromeDriver (para Selenium/FlashScore)

### Instalação

```bash
# Clone o repositório
git clone https://github.com/marceloto-apps/maisevplus_webscraping.git
cd maisevplus_webscraping-

# Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# Instale as dependências
pip install -r requirements.txt
```

### Variáveis de Ambiente

Copie o arquivo de exemplo e preencha com suas chaves:

```bash
cp .env.example .env
```

---

## 📖 Documentação

- [PRD M1 — Coleta de Dados](docs/PRD.md)
- [Schema do Banco de Dados](docs/SCHEMA.md)
- [Especificações Técnicas](docs/SPECS.md)
- [Backlog de Tarefas](docs/TASKS.md)

---

## 📊 Escopo de Ligas

**51 ligas | 32 países | ~110.000 jogos (backfill 5 temporadas)**

Inclui Premier League, Bundesliga, Serie A, La Liga, Ligue 1, Brasileirão Série A e Série B, MLS, Liga Profesional (Argentina), Primera División (Chile), Eliteserien (Noruega), J1 League (Japão), Liga 1 (Peru), Liga AUF (Uruguai), Primera A (Colômbia), Copa de Primera (Paraguai), Liga Pro (Equador), e mais.

---

## 🔒 Repositório Privado

Este projeto é de uso privado e está licenciado sob termos proprietários.