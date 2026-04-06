-- Adiciona bookmakers brasileiros que aparecem no Flashscore (VPS via NordVPN BR)
-- Rode: psql -U maisevplus -d maisevplus_db -f scripts/sql/add_flashscore_bookmakers.sql

INSERT INTO bookmakers (name, display_name, type)
VALUES 
    ('esportesdasorte', 'Esportes da Sorte', 'br_retail'),
    ('betesporte', 'BetEsporte', 'br_retail'),
    ('bet7k', 'Bet7k', 'br_retail'),
    ('br4bet', 'BR4Bet', 'br_retail'),
    ('casadeapostas', 'Casa de Apostas', 'br_retail'),
    ('luvabet', 'LuvaBet', 'br_retail'),
    ('betdasorte', 'BetdaSorte', 'br_retail'),
    ('betboom', 'BetBoom', 'br_retail'),
    ('esportivabet', 'EsportivaBet', 'br_retail'),
    ('segurobet', 'SeguroBet', 'br_retail'),
    ('brasilbet', 'BrasilBet', 'br_retail'),
    ('brasildasorte', 'Brasil da Sorte', 'br_retail'),
    ('goldebet', 'GoldeBet', 'br_retail'),
    ('jogodeouro', 'Jogo de Ouro', 'br_retail'),
    ('lotogreen', 'LotoGreen', 'br_retail'),
    ('alfabet', 'AlfaBet', 'br_retail')
ON CONFLICT (name) DO NOTHING;
