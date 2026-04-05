-- scripts/update_api_keys.sql
-- Ajuste: KEY_1 → VIP (7500/dia), Keys 2-7 → desativadas

-- 1. Ver estado atual
SELECT key_id, key_label, limit_daily, usage_today, is_active
FROM api_keys WHERE service = 'api_football' ORDER BY key_id;

-- 2. Atualizar KEY_1 (menor key_id do api_football) → limit=7500
UPDATE api_keys
SET limit_daily = 7500, is_active = TRUE
WHERE key_id = (
    SELECT key_id FROM api_keys
    WHERE service = 'api_football'
    ORDER BY key_id ASC
    LIMIT 1
);

-- 3. Desativar todas as outras keys api_football
UPDATE api_keys
SET is_active = FALSE
WHERE service = 'api_football'
  AND key_id != (
    SELECT key_id FROM api_keys
    WHERE service = 'api_football'
    ORDER BY key_id ASC
    LIMIT 1
);

-- 4. Verificar resultado
SELECT key_id, key_label, limit_daily, usage_today, is_active
FROM api_keys WHERE service = 'api_football' ORDER BY key_id;
