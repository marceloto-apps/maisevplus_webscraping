-- scripts/seed_api_keys.sql
INSERT INTO api_keys (service, key_label, key_value, limit_daily, limit_monthly, is_active) VALUES
    ('api_football', 'af_key_1', '11b0151f3fcf9b5522de91b35f6b556b', 100, NULL, TRUE),
    ('api_football', 'af_key_2', '923e3795ff02e18792c3ce1295d611f1', 100, NULL, TRUE),
    ('api_football', 'af_key_3', 'f8e0a43dfa6ab6118ecc4153fb80495e', 100, NULL, TRUE),
    ('api_football', 'af_key_4', 'aea0378013f0e0e483386d70411c0c45', 100, NULL, TRUE),
    ('api_football', 'af_key_5', 'b1033ef48186b6ac23ac15ac8b6055e1', 100, NULL, TRUE),
    ('odds_api',     'oa_key_1', 'c0f101dc31276f4860edea42e39300a2', NULL, 500, TRUE),
    ('odds_api',     'oa_key_2', '0a60c904410d30dca14cb289eabf679e', NULL, 500, TRUE),
    ('odds_api',     'oa_key_3', '5e833013821d504769cebe73283eaebe', NULL, 500, TRUE),
    ('odds_api',     'oa_key_4', '30668c94e73375ee3d75ed20463942ad', NULL, 500, TRUE),
    ('odds_api',     'oa_key_5', '44a248f483cb283fdd91efd0adc90b33', NULL, 500, TRUE)
ON CONFLICT (key_value) DO NOTHING;
