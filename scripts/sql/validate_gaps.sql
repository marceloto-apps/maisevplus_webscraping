-- =============================================================
-- Validação Fase 3 — Executar após rodada complementar
-- =============================================================

-- 1. Status da fila complementar
SELECT status, COUNT(*) AS total
FROM fc_complementary_queue
GROUP BY status
ORDER BY total DESC;

-- 2. Jogos que AINDA têm gap (1x2 sem OU) — deve ser ≤ 5
SELECT COUNT(*) AS jogos_com_gap
FROM matches m
WHERE m.status = 'finished'
  AND m.scraping_flashscore = true
  AND EXISTS (
    SELECT 1 FROM odds_history oh
    WHERE oh.match_id = m.id
      AND oh.source = 'flashscore'
      AND oh.market_type = '1x2'
      AND oh.period = 'ft'
  )
  AND NOT EXISTS (
    SELECT 1 FROM odds_history oh
    WHERE oh.match_id = m.id
      AND oh.source = 'flashscore'
      AND oh.market_type = 'ou'
      AND oh.period = 'ft'
  );

-- 3. Resumo de mercados coletados nas últimas 24h
SELECT oh.market_type, oh.period, COUNT(DISTINCT oh.match_id) AS partidas, COUNT(*) AS registros
FROM odds_history oh
WHERE oh.source = 'flashscore'
  AND oh.created_at >= NOW() - INTERVAL '24 hours'
GROUP BY oh.market_type, oh.period
ORDER BY partidas DESC;

-- 4. Jogos que falharam 3+ vezes na fila (precisam investigação manual)
SELECT fcq.match_id, fcq.flashscore_id, fcq.attempts, fcq.failed_markets, fcq.updated_at
FROM fc_complementary_queue fcq
WHERE fcq.status = 'failed'
ORDER BY fcq.attempts DESC, fcq.updated_at DESC;

-- 5. Distribuição de tentativas na fila
SELECT attempts, status, COUNT(*) AS total
FROM fc_complementary_queue
GROUP BY attempts, status
ORDER BY attempts, status;
