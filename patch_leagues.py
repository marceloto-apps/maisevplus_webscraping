import re

with open('src/config/leagues.yaml', 'r', encoding='utf-8') as f:
    text = f.read()

mappings = {
    'ENG_PL': {'api_football_league_id': 39, 'odds_api_sport_key': 'soccer_epl'},
    'ENG_CH': {'api_football_league_id': 40, 'odds_api_sport_key': 'soccer_efl_champ'},
    'ENG_L1': {'api_football_league_id': 41, 'odds_api_sport_key': 'soccer_england_league1'},
    'ENG_L2': {'api_football_league_id': 42, 'odds_api_sport_key': 'soccer_england_league2'},
    'ENG_NL': {'api_football_league_id': 43, 'odds_api_sport_key': 'soccer_england_efl_cup'},
    
    'SCO_PL': {'api_football_league_id': 179, 'odds_api_sport_key': 'soccer_spl'},
    'SCO_CH': {'api_football_league_id': 180, 'odds_api_sport_key': 'null'},
    'SCO_L1': {'api_football_league_id': 183, 'odds_api_sport_key': 'null'},
    'SCO_L2': {'api_football_league_id': 184, 'odds_api_sport_key': 'null'},
    
    'GER_BL': {'api_football_league_id': 78, 'odds_api_sport_key': 'soccer_germany_bundesliga'},
    'GER_B2': {'api_football_league_id': 79, 'odds_api_sport_key': 'soccer_germany_bundesliga2'},
    
    'ITA_SA': {'api_football_league_id': 135, 'odds_api_sport_key': 'soccer_italy_serie_a'},
    'ITA_SB': {'api_football_league_id': 136, 'odds_api_sport_key': 'soccer_italy_serie_b'},
    
    'ESP_PD': {'api_football_league_id': 140, 'odds_api_sport_key': 'soccer_spain_la_liga'},
    'ESP_SD': {'api_football_league_id': 141, 'odds_api_sport_key': 'soccer_spain_segunda_division'},
    
    'FRA_L1': {'api_football_league_id': 61, 'odds_api_sport_key': 'soccer_france_ligue_one'},
    'FRA_L2': {'api_football_league_id': 62, 'odds_api_sport_key': 'soccer_france_ligue_two'},
    
    'NED_ED': {'api_football_league_id': 88, 'odds_api_sport_key': 'soccer_netherlands_eredivisie'},
    'BEL_PL': {'api_football_league_id': 144, 'odds_api_sport_key': 'soccer_belgium_first_div'},
    'POR_PL': {'api_football_league_id': 94, 'odds_api_sport_key': 'soccer_portugal_primeira_liga'},
    'TUR_SL': {'api_football_league_id': 203, 'odds_api_sport_key': 'soccer_turkey_super_league'},
    'GRE_SL': {'api_football_league_id': 197, 'odds_api_sport_key': 'soccer_greece_super_league'},
    
    'BRA_SA': {'api_football_league_id': 71, 'odds_api_sport_key': 'soccer_brazil_campeonato'},
    'MEX_LM': {'api_football_league_id': 262, 'odds_api_sport_key': 'soccer_mexico_ligamx'},
    'AUT_BL': {'api_football_league_id': 218, 'odds_api_sport_key': 'soccer_austria_bundesliga'},
    'SWI_SL': {'api_football_league_id': 207, 'odds_api_sport_key': 'soccer_switzerland_superleague'},
}

def replacer(match):
    code = match.group(2)
    if code in mappings:
        m = mappings[code]
        odds_api_str = f'"{m["odds_api_sport_key"]}"' if m["odds_api_sport_key"] != 'null' else 'null'
        new_str = f"    api_football_league_id: {m['api_football_league_id']}\n    odds_api_sport_key: {odds_api_str}\n"
        return match.group(0) + new_str
    return match.group(0)

new_text = re.sub(r'(  ([A-Z_]+):\n(?:    .*\n)*?    xg_source: .*\n)', replacer, text)

with open('src/config/leagues.yaml', 'w', encoding='utf-8') as f:
    f.write(new_text)

print('Updated leagues.yaml successfully')
