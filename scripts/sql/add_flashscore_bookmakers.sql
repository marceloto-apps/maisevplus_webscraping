-- Adiciona bookmakers brasileiros que aparecem no Flashscore (VPS via NordVPN BR)
-- Rode na VPS: psql -U maisev -d maisev -f scripts/sql/add_flashscore_bookmakers.sql

INSERT INTO bookmakers (name, display_name, country)
VALUES 
    ('betnacional', 'Betnacional', 'BR'),
    ('kto', 'KTO', 'BR'),
    ('esportesdasorte', 'Esportes da Sorte', 'BR'),
    ('estrelabet', 'EstrelaBet', 'BR'),
    ('betesporte', 'BetEsporte', 'BR'),
    ('bet7k', 'Bet7k', 'BR'),
    ('br4bet', 'BR4Bet', 'BR'),
    ('casadeapostas', 'Casa de Apostas', 'BR'),
    ('luvabet', 'LuvaBet', 'BR'),
    ('betdasorte', 'BetdaSorte', 'BR'),
    ('betboom', 'BetBoom', 'BR'),
    ('f12bet', 'F12 Bet', 'BR'),
    ('esportivabet', 'EsportivaBet', 'BR'),
    ('segurobet', 'SeguroBet', 'BR'),
    ('brasilbet', 'BrasilBet', 'BR'),
    ('brasildasorte', 'Brasil da Sorte', 'BR'),
    ('goldebet', 'GoldeBet', 'BR'),
    ('jogodeouro', 'Jogo de Ouro', 'BR'),
    ('lotogreen', 'LotoGreen', 'BR'),
    ('multibet', 'MultiBet', 'BR'),
    ('alfabet', 'AlfaBet', 'BR')
ON CONFLICT (name) DO NOTHING;
