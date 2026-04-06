-- Adiciona bookmakers regionais que aparecem no Flashscore (VPS localizada na França)
-- Rode na VPS: psql -U maisev -d maisev -f scripts/sql/add_flashscore_bookmakers.sql

INSERT INTO bookmakers (name, display_name, country)
VALUES 
    ('betclic', 'Betclic', 'FR'),
    ('unibet', 'Unibet', 'INT'),
    ('winamax', 'Winamax', 'FR'),
    ('pmu', 'PMU', 'FR'),
    ('zebet', 'ZEbet', 'FR'),
    ('parionssport', 'Parions Sport', 'FR'),
    ('francepari', 'France Pari', 'FR'),
    ('vbet', 'Vbet', 'INT'),
    ('betway', 'Betway', 'INT'),
    ('bwin', 'bwin', 'INT'),
    ('williamhill', 'William Hill', 'GB'),
    ('marathonbet', 'Marathonbet', 'INT'),
    ('dafabet', 'Dafabet', 'INT'),
    ('888sport', '888sport', 'INT')
ON CONFLICT (name) DO NOTHING;
