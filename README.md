# maisevplus_webscraping

Sistema de coleta e ingestão de dados de futebol para o projeto **MaisEV+** — odds em tempo real, resultados, estatísticas avançadas e escalações de **26 ligas em 14 países**.

---

## 📌 Visão Geral

Este repositório contém o **Módulo 1 (M1) — Coleta de Dados (Ingestão)** do MaisEV+, responsável por coletar, normalizar e persistir dados de múltiplas fontes em um banco de dados TimescaleDB.

### Fontes de Dados

| Fonte | Tipo | Responsabilidade |
|---|---|---|
| **Footystats API** | HTTP REST | Resultados, stats, fixtures |
| **FlashScore** | Selenium headless | Odds em tempo real (13 casas × 9 mercados) |
| **Football-Data.co.uk** | HTTP (CSV) | Backfill histórico |
| **FBRef** | HTTP + BeautifulSoup | xG para 19 ligas |
| **Understat** | HTTP (lib Python async) | xG granular Top 5 ligas |
| **The Odds API** | HTTP REST | Validação cruzada de odds |
| **API-Football** | HTTP REST | Escalações confirmadas |

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

**26 ligas | 14 países | ~57.500 jogos (backfill 5 temporadas)**

Inclui Premier League, Bundesliga, Serie A, La Liga, Ligue 1, Brasileirão Série A e mais.

---

## 🔒 Repositório Privado

Este projeto é de uso privado e está licenciado sob termos proprietários.