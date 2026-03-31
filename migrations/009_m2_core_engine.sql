cat > /var/www/maisevplus/migrations/009_m2_core_engine.sql << 'SQLEOF'
-- =============================================================
-- Migration 009: M2 Core Engine Tables
-- Projeto: MaisEV+ | Motor Analitico M2
-- matches.match_id = UUID | users.id = SERIAL
-- Executada com sucesso em: 2026-03-31
-- =============================================================

BEGIN;

-- 1. PREDICTIONS
CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    match_id        UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    model_version   TEXT NOT NULL DEFAULT 'poisson_v1',
    home_lambda     NUMERIC(6,4) NOT NULL,
    away_lambda     NUMERIC(6,4) NOT NULL,
    prob_home       NUMERIC(6,5) NOT NULL,
    prob_draw       NUMERIC(6,5) NOT NULL,
    prob_away       NUMERIC(6,5) NOT NULL,
    fair_odd_home   NUMERIC(8,4),
    fair_odd_draw   NUMERIC(8,4),
    fair_odd_away   NUMERIC(8,4),
    edge_home       NUMERIC(6,4),
    edge_draw       NUMERIC(6,4),
    edge_away       NUMERIC(6,4),
    suggested_bet   TEXT CHECK (suggested_bet IN ('home','draw','away','over','under','skip')),
    ev_percent      NUMERIC(8,4),
    confidence      NUMERIC(5,4),
    score_matrix    JSONB,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions (match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_user  ON predictions (user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions (model_version);
CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_unique_snap
    ON predictions (match_id, user_id, model_version);

-- 2. BETS
CREATE TABLE IF NOT EXISTS bets (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id        UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    prediction_id   INTEGER REFERENCES predictions(id) ON DELETE SET NULL,
    bookmaker_id    INTEGER REFERENCES bookmakers(bookmaker_id) ON DELETE SET NULL,
    market_type     TEXT NOT NULL DEFAULT '1x2',
    selection       TEXT NOT NULL,
    odd_placed      NUMERIC(8,4) NOT NULL,
    fair_odd        NUMERIC(8,4),
    edge            NUMERIC(6,4),
    stake           NUMERIC(12,2) NOT NULL CHECK (stake > 0),
    stake_pct       NUMERIC(5,4),
    kelly_fraction  NUMERIC(5,4),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','won','lost','void','cashout','half_won','half_lost')),
    pnl             NUMERIC(12,2),
    settled_at      TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bets_user    ON bets (user_id);
CREATE INDEX IF NOT EXISTS idx_bets_match   ON bets (match_id);
CREATE INDEX IF NOT EXISTS idx_bets_status  ON bets (status);
CREATE INDEX IF NOT EXISTS idx_bets_settled ON bets (settled_at);

-- 3. BANKROLL (append-only ledger)
CREATE TABLE IF NOT EXISTS bankroll (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bet_id          INTEGER REFERENCES bets(id) ON DELETE SET NULL,
    tx_type         TEXT NOT NULL
                        CHECK (tx_type IN ('deposit','withdraw','bet_placed','bet_won','bet_lost','bet_void','adjustment')),
    amount          NUMERIC(12,2) NOT NULL,
    balance_after   NUMERIC(12,2) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bankroll_user    ON bankroll (user_id);
CREATE INDEX IF NOT EXISTS idx_bankroll_bet     ON bankroll (bet_id);
CREATE INDEX IF NOT EXISTS idx_bankroll_type    ON bankroll (tx_type);
CREATE INDEX IF NOT EXISTS idx_bankroll_created ON bankroll (user_id, created_at DESC);

-- 4. TRIGGER
CREATE TRIGGER trg_bets_updated
    BEFORE UPDATE ON bets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 5. VIEW
CREATE OR REPLACE VIEW v_bankroll_summary AS
SELECT
    b.user_id,
    u.display_name,
    COUNT(*) FILTER (WHERE b.tx_type = 'bet_placed')  AS total_bets,
    COUNT(*) FILTER (WHERE b.tx_type = 'bet_won')     AS total_wins,
    COUNT(*) FILTER (WHERE b.tx_type = 'bet_lost')    AS total_losses,
    SUM(b.amount)                                       AS net_flow,
    (SELECT b2.balance_after
     FROM bankroll b2
     WHERE b2.user_id = b.user_id
     ORDER BY b2.created_at DESC LIMIT 1)              AS current_balance
FROM bankroll b
JOIN users u ON u.id = b.user_id
GROUP BY b.user_id, u.display_name;

COMMIT;
SQLEOF
