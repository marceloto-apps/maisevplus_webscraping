# API-FOOTBALL

# Ligas e temporadas

Para identificar os ids, nomes, temporadas, coberturas e demais detalhes macros das ligas abaixo estão endpoints e exemplos de códigos.

```python
url = "https://v3.football.api-sports.io/leagues"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
ligas = resposta['response']

# Retira o dicionário aninhado e transforma em um só
lista_ligas = []
season_ligas = []
for i in range(0, len(ligas)):
    ligas_dict = {}
    ligas_dict['league_id'] = ligas[i]['league']['id']
    ligas_dict['league_name'] = ligas[i]['league']['name']
    ligas_dict['league_type'] = ligas[i]['league']['type']
    ligas_dict['league_logo'] = ligas[i]['league']['logo']
    ligas_dict['country'] = ligas[i]['country']['name']
    ligas_dict['code'] = ligas[i]['country']['code']
    ligas_dict['flag'] = ligas[i]['country']['flag']
    lista_ligas.append(ligas_dict)
    id_liga = ligas[i]['league']['id']
    for j in range(0, len(ligas[i]['seasons'])):
        season_dict = {}
        season_dict['league_id'] = id_liga
        season_dict['season'] = ligas[i]['seasons'][j]['year']
        season_dict['start'] = ligas[i]['seasons'][j]['start']
        season_dict['end'] = ligas[i]['seasons'][j]['end']
        season_dict['current'] = ligas[i]['seasons'][j]['current']
        season_dict['cov_fixt_events'] = ligas[i]['seasons'][j]['coverage']['fixtures']['events']
        season_dict['cov_fixt_lineups'] = ligas[i]['seasons'][j]['coverage']['fixtures']['lineups']
        season_dict['cov_fixt_stats'] = ligas[i]['seasons'][j]['coverage']['fixtures']['statistics_fixtures']
        season_dict['cov_fixt_players'] = ligas[i]['seasons'][j]['coverage']['fixtures']['statistics_players']
        season_dict['cov_standings'] = ligas[i]['seasons'][j]['coverage']['standings']
        season_dict['cov_players'] = ligas[i]['seasons'][j]['coverage']['players']
        season_dict['cov_top_scorers'] = ligas[i]['seasons'][j]['coverage']['top_scorers']
        season_dict['cov_top_assists'] = ligas[i]['seasons'][j]['coverage']['top_assists']
        season_dict['cov_top_cards'] = ligas[i]['seasons'][j]['coverage']['top_cards']
        season_dict['cov_injuries'] = ligas[i]['seasons'][j]['coverage']['injuries']
        season_dict['cov_predictions'] = ligas[i]['seasons'][j]['coverage']['predictions']
        season_dict['cov_odds'] = ligas[i]['seasons'][j]['coverage']['odds']
        season_ligas.append(season_dict)

#transforma em DataFrame
lista_ligas = pd.DataFrame(lista_ligas)
season_ligas = pd.DataFrame(season_ligas)
```

# Fixtures

## Partidas por Liga

O Endpoint traz partidas, informações gerais sem detalhes, conforme a liga e a temporada escolhida. Exemplo de código

```python
url = "https://v3.football.api-sports.io/fixtures?league=39&season=2025"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
partidas_liga = resposta['response']

# Pega todos os jogos do dia para complementar as informações da parte das odds
lista_partidas_liga = []
for i in range(len(partidas_liga)):
    dict_fixt = {}
    dict_fixt['id'] = partidas_liga[i]['fixture']['id']
    dict_fixt['date'] = partidas_liga[i]['fixture']['date']
    dict_fixt['elapsed'] = partidas_liga[i]['fixture']['status']['elapsed']
    dict_fixt['extra'] = partidas_liga[i]['fixture']['status']['extra']
    dict_fixt['status'] = partidas_liga[i]['fixture']['status']['long']
    dict_fixt['league_id'] = partidas_liga[i]['league']['id']
    dict_fixt['league'] = partidas_liga[i]['league']['name']
    dict_fixt['pais'] = partidas_liga[i]['league']['country']
    dict_fixt['season'] = partidas_liga[i]['league']['season']
    dict_fixt['round'] = partidas_liga[i]['league']['round']
    dict_fixt['referee'] = partidas_liga[i]['fixture']['referee']
    dict_fixt['id_h'] = partidas_liga[i]['teams']['home']['id']
    dict_fixt['home'] = partidas_liga[i]['teams']['home']['name']
    dict_fixt['id_a'] = partidas_liga[i]['teams']['away']['id']
    dict_fixt['away'] = partidas_liga[i]['teams']['away']['name']
    dict_fixt['GH'] = partidas_liga[i]['goals']['home']
    dict_fixt['GA'] = partidas_liga[i]['goals']['away']
    dict_fixt['GFTH'] = partidas_liga[i]['score']['fulltime']['home']
    dict_fixt['GFTA'] = partidas_liga[i]['score']['fulltime']['away']
    dict_fixt['GHTH'] = partidas_liga[i]['score']['halftime']['home']
    dict_fixt['GHTA'] = partidas_liga[i]['score']['halftime']['away']
    dict_fixt['GETH'] = partidas_liga[i]['score']['extratime']['home']
    dict_fixt['GETA'] = partidas_liga[i]['score']['extratime']['away']
    dict_fixt['GPH'] = partidas_liga[i]['score']['penalty']['home']
    dict_fixt['GPA'] = partidas_liga[i]['score']['penalty']['away']
    lista_partidas_liga.append(dict_fixt)

df_partidas_liga = pd.DataFrame(lista_partidas_liga)
```

## Partidas por Data

O Endpoint traz partidas, informações gerais sem detalhes, conforme a data escolhida (aparece todos os jogos do dia independentemente da liga. Exemplo de código

```python
url = "https://v3.football.api-sports.io/fixtures?date=2026-03-28"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
partidas_liga = resposta['response']

# Pega todos os jogos do dia para complementar as informações da parte das odds
lista_partidas_liga = []
for i in range(len(partidas_liga)):
    dict_fixt = {}
    dict_fixt['id'] = partidas_liga[i]['fixture']['id']
    dict_fixt['date'] = partidas_liga[i]['fixture']['date']
    dict_fixt['elapsed'] = partidas_liga[i]['fixture']['status']['elapsed']
    dict_fixt['extra'] = partidas_liga[i]['fixture']['status']['extra']
    dict_fixt['status'] = partidas_liga[i]['fixture']['status']['long']
    dict_fixt['league_id'] = partidas_liga[i]['league']['id']
    dict_fixt['league'] = partidas_liga[i]['league']['name']
    dict_fixt['pais'] = partidas_liga[i]['league']['country']
    dict_fixt['season'] = partidas_liga[i]['league']['season']
    dict_fixt['round'] = partidas_liga[i]['league']['round']
    dict_fixt['referee'] = partidas_liga[i]['fixture']['referee']
    dict_fixt['id_h'] = partidas_liga[i]['teams']['home']['id']
    dict_fixt['home'] = partidas_liga[i]['teams']['home']['name']
    dict_fixt['id_a'] = partidas_liga[i]['teams']['away']['id']
    dict_fixt['away'] = partidas_liga[i]['teams']['away']['name']
    dict_fixt['GH'] = partidas_liga[i]['goals']['home']
    dict_fixt['GA'] = partidas_liga[i]['goals']['away']
    dict_fixt['GFTH'] = partidas_liga[i]['score']['fulltime']['home']
    dict_fixt['GFTA'] = partidas_liga[i]['score']['fulltime']['away']
    dict_fixt['GHTH'] = partidas_liga[i]['score']['halftime']['home']
    dict_fixt['GHTA'] = partidas_liga[i]['score']['halftime']['away']
    dict_fixt['GETH'] = partidas_liga[i]['score']['extratime']['home']
    dict_fixt['GETA'] = partidas_liga[i]['score']['extratime']['away']
    dict_fixt['GPH'] = partidas_liga[i]['score']['penalty']['home']
    dict_fixt['GPA'] = partidas_liga[i]['score']['penalty']['away']
    lista_partidas_liga.append(dict_fixt)

df_partidas_liga = pd.DataFrame(lista_partidas_liga)
```

# Dados das Partidas

## Estatísticas

Dados por Fixture_ID, onde há várias estatísticas importantes a serem extraídas. Abaixo o código para ter o json das estatísticas

```python
url = "https://v3.football.api-sports.io/fixtures/statistics?fixture=1379094"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers, data=payload)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
estatisticas = resposta['response']
estatisticas 
```

Resultado 

```markdown
[{'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'statistics': [{'type': 'Shots on Goal', 'value': 9},
   {'type': 'Shots off Goal', 'value': 3},
   {'type': 'Total Shots', 'value': 18},
   {'type': 'Blocked Shots', 'value': 6},
   {'type': 'Shots insidebox', 'value': 14},
   {'type': 'Shots outsidebox', 'value': 4},
   {'type': 'Fouls', 'value': 17},
   {'type': 'Corner Kicks', 'value': 8},
   {'type': 'Offsides', 'value': 2},
   {'type': 'Ball Possession', 'value': '62%'},
   {'type': 'Yellow Cards', 'value': 4},
   {'type': 'Red Cards', 'value': None},
   {'type': 'Goalkeeper Saves', 'value': 1},
   {'type': 'Total passes', 'value': 561},
   {'type': 'Passes accurate', 'value': 495},
   {'type': 'Passes %', 'value': '88%'},
   {'type': 'expected_goals', 'value': '3.10'},
   {'type': 'goals_prevented', 'value': 0}]},
 {'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'statistics': [{'type': 'Shots on Goal', 'value': 4},
   {'type': 'Shots off Goal', 'value': 3},
   {'type': 'Total Shots', 'value': 9},
   {'type': 'Blocked Shots', 'value': 2},
   {'type': 'Shots insidebox', 'value': 8},
   {'type': 'Shots outsidebox', 'value': 1},
   {'type': 'Fouls', 'value': 11},
   {'type': 'Corner Kicks', 'value': 1},
   {'type': 'Offsides', 'value': 4},
   {'type': 'Ball Possession', 'value': '38%'},
   {'type': 'Yellow Cards', 'value': 1},
   {'type': 'Red Cards', 'value': None},
   {'type': 'Goalkeeper Saves', 'value': 6},
   {'type': 'Total passes', 'value': 348},
   {'type': 'Passes accurate', 'value': 265},
   {'type': 'Passes %', 'value': '76%'},
   {'type': 'expected_goals', 'value': '1.54'},
   {'type': 'goals_prevented', 'value': 0}]}]
```

Das estatísticas acima quero adicionar na base as abaixo:

```markdown
'Shots off Goal'
'Blocked Shots'
'Shots insidebox'
'Shots outsidebox'
'Total passes'
'Passes accurate'
'Passes %'
'expected_goals'
```

## Eventos

Mostras os eventos dos jogo. Os eventos considerados são Gols, Cartões, Substituições e Gols Cancelados. Tem informações do minuto do evento e se está em extra time ou nçai, o time, o tipo, gol, cartão, etc., de qual jogador fez ou participou do evendo (quem fez o gol, quem deu assistência, quem entrou e quem sai, etc.) e o detalhe do evento

```python
url = "https://v3.football.api-sports.io/fixtures/events?fixture=1379094"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers, data=payload)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
eventos = resposta['response']
eventos
```

Resultados

```markdown
[{'time': {'elapsed': 1, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 631, 'name': 'P. Foden'},
  'assist': {'id': 41621, 'name': 'M. Nunes'},
  'type': 'Goal',
  'detail': 'Normal Goal',
  'comments': None},
 {'time': {'elapsed': 25, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 129033, 'name': 'J. Gvardiol'},
  'assist': {'id': 307123, 'name': "N. O'Reilly"},
  'type': 'Goal',
  'detail': 'Normal Goal',
  'comments': None},
 {'time': {'elapsed': 46, 'extra': None},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 162128, 'name': 'W. Gnonto'},
  'assist': {'id': 833, 'name': 'J. Bijol'},
  'type': 'subst',
  'detail': 'Substitution 1',
  'comments': None},
 {'time': {'elapsed': 46, 'extra': None},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 19329, 'name': 'D. James'},
  'assist': {'id': 18766, 'name': 'D. Calvert-Lewin'},
  'type': 'subst',
  'detail': 'Substitution 2',
  'comments': None},
 {'time': {'elapsed': 49, 'extra': None},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 18766, 'name': 'D. Calvert-Lewin'},
  'assist': {'id': None, 'name': None},
  'type': 'Goal',
  'detail': 'Normal Goal',
  'comments': None},
 {'time': {'elapsed': 55, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 41621, 'name': 'Matheus Nunes'},
  'assist': {'id': None, 'name': None},
  'type': 'Card',
  'detail': 'Yellow Card',
  'comments': 'Foul'},
 {'time': {'elapsed': 57, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 636, 'name': 'Bernardo Silva'},
  'assist': {'id': None, 'name': None},
  'type': 'Card',
  'detail': 'Yellow Card',
  'comments': 'Argument'},
 {'time': {'elapsed': 58, 'extra': None},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 19321, 'name': 'Joe Rodon'},
  'assist': {'id': None, 'name': None},
  'type': 'Card',
  'detail': 'Yellow Card',
  'comments': 'Argument'},
 {'time': {'elapsed': 66, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 129033, 'name': 'Joško Gvardiol'},
  'assist': {'id': None, 'name': None},
  'type': 'Card',
  'detail': 'Yellow Card',
  'comments': 'Foul'},
 {'time': {'elapsed': 68, 'extra': None},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 19461, 'name': 'L. Nmecha'},
  'assist': {'id': None, 'name': None},
  'type': 'Goal',
  'detail': 'Normal Goal',
  'comments': None},
 {'time': {'elapsed': 69, 'extra': None},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 19760, 'name': 'J. Justin'},
  'assist': {'id': 47969, 'name': 'G. Gudmundsson'},
  'type': 'subst',
  'detail': 'Substitution 3',
  'comments': None},
 {'time': {'elapsed': 75, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 36902, 'name': 'T. Reijnders'},
  'assist': {'id': 156477, 'name': 'R. Cherki'},
  'type': 'subst',
  'detail': 'Substitution 1',
  'comments': None},
 {'time': {'elapsed': 82, 'extra': None},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 19461, 'name': 'L. Nmecha'},
  'assist': {'id': 48389, 'name': 'N. Okafor'},
  'type': 'subst',
  'detail': 'Substitution 4',
  'comments': None},
 {'time': {'elapsed': 87, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 1622, 'name': 'Gianluigi Donnarumma'},
  'assist': {'id': None, 'name': None},
  'type': 'Card',
  'detail': 'Yellow Card',
  'comments': 'Argument'},
 {'time': {'elapsed': 89, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 636, 'name': 'B. Silva'},
  'assist': {'id': 81573, 'name': 'O. Marmoush'},
  'type': 'subst',
  'detail': 'Substitution 2',
  'comments': None},
 {'time': {'elapsed': 90, 'extra': 6},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 1422, 'name': 'J. Doku'},
  'assist': {'id': 626, 'name': 'J. Stones'},
  'type': 'subst',
  'detail': 'Substitution 3',
  'comments': None},
 {'time': {'elapsed': 90, 'extra': 2},
  'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png'},
  'player': {'id': 32966, 'name': 'A. Tanaka'},
  'assist': {'id': 50739, 'name': 'B. Aaronson'},
  'type': 'subst',
  'detail': 'Substitution 5',
  'comments': None},
 {'time': {'elapsed': 90, 'extra': None},
  'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png'},
  'player': {'id': 631, 'name': 'P. Foden'},
  'assist': {'id': 156477, 'name': 'R. Cherki'},
  'type': 'Goal',
  'detail': 'Normal Goal',
  'comments': None}]
```

## Lineup

Informações detalhadas sobre as formações. Tem técnico, formação tática, jogadores que iniciam e que estão no banco (id, nome, número, posição, grid) por time.

```python
url = "https://v3.football.api-sports.io/fixtures/lineups?fixture=1379094"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers, data=payload)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
lineup = resposta['response']
lineup 
```

Resultado

```markdown
[{'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png',
   'colors': {'player': {'primary': 'abd1f5',
     'number': '000000',
     'border': 'abd1f5'},
    'goalkeeper': {'primary': '008b48',
     'number': 'feb139',
     'border': '008b48'}}},
  'coach': {'id': 4,
   'name': 'Josep Guardiola i Sala',
   'photo': 'https://media.api-sports.io/football/coachs/4.png'},
  'formation': '4-3-2-1',
  'startXI': [{'player': {'id': 1622,
     'name': 'G. Donnarumma',
     'number': 25,
     'pos': 'G',
     'grid': '1:1'}},
   {'player': {'id': 41621,
     'name': 'M. Nunes',
     'number': 27,
     'pos': 'D',
     'grid': '2:4'}},
   {'player': {'id': 567,
     'name': 'R. Dias',
     'number': 3,
     'pos': 'D',
     'grid': '2:3'}},
   {'player': {'id': 129033,
     'name': 'J. Gvardiol',
     'number': 24,
     'pos': 'D',
     'grid': '2:2'}},
   {'player': {'id': 307123,
     'name': "N. O'Reilly",
     'number': 33,
     'pos': 'D',
     'grid': '2:1'}},
   {'player': {'id': 636,
     'name': 'B. Silva',
     'number': 20,
     'pos': 'M',
     'grid': '3:3'}},
   {'player': {'id': 161933,
     'name': 'Nico',
     'number': 14,
     'pos': 'M',
     'grid': '3:2'}},
   {'player': {'id': 36902,
     'name': 'T. Reijnders',
     'number': 4,
     'pos': 'M',
     'grid': '3:1'}},
   {'player': {'id': 631,
     'name': 'P. Foden',
     'number': 47,
     'pos': 'M',
     'grid': '4:2'}},
   {'player': {'id': 1422,
     'name': 'J. Doku',
     'number': 11,
     'pos': 'M',
     'grid': '4:1'}},
   {'player': {'id': 1100,
     'name': 'E. Haaland',
     'number': 9,
     'pos': 'F',
     'grid': '5:1'}}],
  'substitutes': [{'player': {'id': 162489,
     'name': 'J. Trafford',
     'number': 1,
     'pos': 'G',
     'grid': None}},
   {'player': {'id': 626,
     'name': 'J. Stones',
     'number': 5,
     'pos': 'D',
     'grid': None}},
   {'player': {'id': 18861,
     'name': 'N. Ake',
     'number': 6,
     'pos': 'D',
     'grid': None}},
   {'player': {'id': 81573,
     'name': 'O. Marmoush',
     'number': 7,
     'pos': 'F',
     'grid': None}},
   {'player': {'id': 156477,
     'name': 'R. Cherki',
     'number': 10,
     'pos': 'M',
     'grid': None}},
   {'player': {'id': 21138,
     'name': 'R. Ait Nouri',
     'number': 21,
     'pos': 'D',
     'grid': None}},
   {'player': {'id': 266657,
     'name': 'Savinho',
     'number': 26,
     'pos': 'F',
     'grid': None}},
   {'player': {'id': 360114,
     'name': 'A. Khusanov',
     'number': 45,
     'pos': 'D',
     'grid': None}},
   {'player': {'id': 284230,
     'name': 'R. Lewis',
     'number': 82,
     'pos': 'D',
     'grid': None}}]},
 {'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png',
   'colors': {'player': {'primary': 'ffffff',
     'number': '17277f',
     'border': 'ffffff'},
    'goalkeeper': {'primary': '467cd2',
     'number': 'f1f0ea',
     'border': '467cd2'}}},
  'coach': {'id': 2,
   'name': 'Daniel Farke',
   'photo': 'https://media.api-sports.io/football/coachs/2.png'},
  'formation': '4-3-3',
  'startXI': [{'player': {'id': 80296,
     'name': 'Lucas Perri',
     'number': 1,
     'pos': 'G',
     'grid': '1:1'}},
   {'player': {'id': 19201,
     'name': 'J. Bogle',
     'number': 2,
     'pos': 'D',
     'grid': '2:4'}},
   {'player': {'id': 19321,
     'name': 'J. Rodon',
     'number': 6,
     'pos': 'D',
     'grid': '2:3'}},
   {'player': {'id': 64003,
     'name': 'P. Struijk',
     'number': 5,
     'pos': 'D',
     'grid': '2:2'}},
   {'player': {'id': 19760,
     'name': 'J. Justin',
     'number': 24,
     'pos': 'D',
     'grid': '2:1'}},
   {'player': {'id': 32966,
     'name': 'A. Tanaka',
     'number': 22,
     'pos': 'M',
     'grid': '3:3'}},
   {'player': {'id': 2279,
     'name': 'E. Ampadu',
     'number': 4,
     'pos': 'M',
     'grid': '3:2'}},
   {'player': {'id': 129142,
     'name': 'I. Gruev',
     'number': 44,
     'pos': 'M',
     'grid': '3:1'}},
   {'player': {'id': 19329,
     'name': 'D. James',
     'number': 7,
     'pos': 'F',
     'grid': '4:3'}},
   {'player': {'id': 19461,
     'name': 'L. Nmecha',
     'number': 14,
     'pos': 'F',
     'grid': '4:2'}},
   {'player': {'id': 162128,
     'name': 'W. Gnonto',
     'number': 29,
     'pos': 'F',
     'grid': '4:1'}}],
  'substitutes': [{'player': {'id': 20619,
     'name': 'I. Meslier',
     'number': 16,
     'pos': 'G',
     'grid': None}},
   {'player': {'id': 19287,
     'name': 'S. Byram',
     'number': 25,
     'pos': 'D',
     'grid': None}},
   {'player': {'id': 47969,
     'name': 'G. Gudmundsson',
     'number': 3,
     'pos': 'D',
     'grid': None}},
   {'player': {'id': 833,
     'name': 'J. Bijol',
     'number': 15,
     'pos': 'D',
     'grid': None}},
   {'player': {'id': 19128,
     'name': 'J. Harrison',
     'number': 20,
     'pos': 'F',
     'grid': None}},
   {'player': {'id': 50739,
     'name': 'B. Aaronson',
     'number': 11,
     'pos': 'M',
     'grid': None}},
   {'player': {'id': 48389,
     'name': 'N. Okafor',
     'number': 19,
     'pos': 'F',
     'grid': None}},
   {'player': {'id': 250,
     'name': 'J. Piroe',
     'number': 10,
     'pos': 'F',
     'grid': None}},
   {'player': {'id': 18766,
     'name': 'D. Calvert-Lewin',
     'number': 9,
     'pos': 'F',
     'grid': None}}]}]
```

## Estatísticas dos Jogadores

Diversas estatísticas por jogador de todos os jogadores que entraram na partida. Todas são relevantes para nossa base. Precisarmos extrair todas no processo.

```python
url = "https://v3.football.api-sports.io/fixtures/players?fixture=1379094"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers, data=payload)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
players = resposta['response']
```

Resultado

```markdown
[{'team': {'id': 50,
   'name': 'Manchester City',
   'logo': 'https://media.api-sports.io/football/teams/50.png',
   'update': '2026-03-24T04:12:13+00:00'},
  'players': [{'player': {'id': 1622,
     'name': 'Gianluigi Donnarumma',
     'photo': 'https://media.api-sports.io/football/players/1622.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 25,
       'position': 'G',
       'rating': '6.9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 2, 'assists': 0, 'saves': 1},
      'passes': {'total': 29, 'key': None, 'accuracy': '26'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 1, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': 1}}]},
   {'player': {'id': 41621,
     'name': 'Matheus Nunes',
     'photo': 'https://media.api-sports.io/football/players/41621.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 27,
       'position': 'D',
       'rating': '5.6',
       'captain': False,
       'substitute': False},
      'offsides': 2,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 1, 'saves': None},
      'passes': {'total': 61, 'key': 1, 'accuracy': '52'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 9, 'won': 1},
      'dribbles': {'attempts': 2, 'success': None, 'past': 2},
      'fouls': {'drawn': None, 'committed': 1},
      'cards': {'yellow': 1, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 567,
     'name': 'Rúben Dias',
     'photo': 'https://media.api-sports.io/football/players/567.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 3,
       'position': 'D',
       'rating': '6.6',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 1, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 73, 'key': None, 'accuracy': '68'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 6, 'won': 3},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': 1},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 129033,
     'name': 'Joško Gvardiol',
     'photo': 'https://media.api-sports.io/football/players/129033.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 24,
       'position': 'D',
       'rating': '6.3',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 2, 'on': 1},
      'goals': {'total': 1, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 75, 'key': 1, 'accuracy': '65'},
      'tackles': {'total': 1, 'blocks': None, 'interceptions': 1},
      'duels': {'total': 11, 'won': 5},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': 1, 'committed': 1},
      'cards': {'yellow': 1, 'red': 0},
      'penalty': {'won': None,
       'commited': 1,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 307123,
     'name': "Nico O'Reilly",
     'photo': 'https://media.api-sports.io/football/players/307123.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 33,
       'position': 'D',
       'rating': '6.5',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 2, 'on': 2},
      'goals': {'total': None, 'conceded': 0, 'assists': 1, 'saves': None},
      'passes': {'total': 41, 'key': 3, 'accuracy': '35'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 16, 'won': 9},
      'dribbles': {'attempts': 2, 'success': 1, 'past': 1},
      'fouls': {'drawn': 1, 'committed': 1},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 636,
     'name': 'Bernardo Silva',
     'photo': 'https://media.api-sports.io/football/players/636.png'},
    'statistics': [{'games': {'minutes': 89,
       'number': 20,
       'position': 'M',
       'rating': '6.6',
       'captain': True,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 63, 'key': 1, 'accuracy': '59'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 5, 'won': None},
      'dribbles': {'attempts': 1, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': 2},
      'cards': {'yellow': 1, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 161933,
     'name': 'Nico González',
     'photo': 'https://media.api-sports.io/football/players/161933.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 14,
       'position': 'M',
       'rating': '6.9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 1, 'on': 1},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 70, 'key': None, 'accuracy': '63'},
      'tackles': {'total': 1, 'blocks': None, 'interceptions': None},
      'duels': {'total': 12, 'won': 6},
      'dribbles': {'attempts': 1, 'success': 1, 'past': None},
      'fouls': {'drawn': 2, 'committed': 2},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 36902,
     'name': 'Tijjani Reijnders',
     'photo': 'https://media.api-sports.io/football/players/36902.png'},
    'statistics': [{'games': {'minutes': 75,
       'number': 4,
       'position': 'M',
       'rating': '7.9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 1, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 38, 'key': 1, 'accuracy': '35'},
      'tackles': {'total': 1, 'blocks': 1, 'interceptions': 1},
      'duels': {'total': 8, 'won': 5},
      'dribbles': {'attempts': 3, 'success': 2, 'past': None},
      'fouls': {'drawn': 2, 'committed': 2},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 631,
     'name': 'Phil Foden',
     'photo': 'https://media.api-sports.io/football/players/631.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 47,
       'position': 'M',
       'rating': '9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 3, 'on': 3},
      'goals': {'total': 2, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 46, 'key': 1, 'accuracy': '40'},
      'tackles': {'total': None, 'blocks': 1, 'interceptions': None},
      'duels': {'total': 9, 'won': 4},
      'dribbles': {'attempts': 1, 'success': None, 'past': None},
      'fouls': {'drawn': 2, 'committed': 3},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 1422,
     'name': 'Jérémy Doku',
     'photo': 'https://media.api-sports.io/football/players/1422.png'},
    'statistics': [{'games': {'minutes': 89,
       'number': 11,
       'position': 'M',
       'rating': '7.3',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 41, 'key': 3, 'accuracy': '32'},
      'tackles': {'total': 2, 'blocks': None, 'interceptions': None},
      'duels': {'total': 16, 'won': 6},
      'dribbles': {'attempts': 7, 'success': 3, 'past': 1},
      'fouls': {'drawn': 1, 'committed': 2},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 1100,
     'name': 'Erling Haaland',
     'photo': 'https://media.api-sports.io/football/players/1100.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 9,
       'position': 'F',
       'rating': '6.2',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 1, 'on': 1},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 10, 'key': 1, 'accuracy': '7'},
      'tackles': {'total': 1, 'blocks': 1, 'interceptions': None},
      'duels': {'total': 12, 'won': 4},
      'dribbles': {'attempts': 1, 'success': None, 'past': None},
      'fouls': {'drawn': 1, 'committed': 2},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 156477,
     'name': 'Rayan Cherki',
     'photo': 'https://media.api-sports.io/football/players/156477.png'},
    'statistics': [{'games': {'minutes': 15,
       'number': 10,
       'position': 'M',
       'rating': '7',
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 1, 'saves': None},
      'passes': {'total': 12, 'key': 1, 'accuracy': '11'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 2, 'won': 1},
      'dribbles': {'attempts': 1, 'success': None, 'past': None},
      'fouls': {'drawn': 1, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 81573,
     'name': 'Omar Marmoush',
     'photo': 'https://media.api-sports.io/football/players/81573.png'},
    'statistics': [{'games': {'minutes': 12,
       'number': 7,
       'position': 'F',
       'rating': '6.2',
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': 1, 'on': 1},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 2, 'won': None},
      'dribbles': {'attempts': 1, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 626,
     'name': 'John Stones',
     'photo': 'https://media.api-sports.io/football/players/626.png'},
    'statistics': [{'games': {'minutes': 1,
       'number': 5,
       'position': 'D',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 2, 'key': None, 'accuracy': '2'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 162489,
     'name': 'James Trafford',
     'photo': 'https://media.api-sports.io/football/players/162489.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 1,
       'position': 'G',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 360114,
     'name': 'Abdukodir Khusanov',
     'photo': 'https://media.api-sports.io/football/players/360114.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 45,
       'position': 'D',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 18861,
     'name': 'Nathan Aké',
     'photo': 'https://media.api-sports.io/football/players/18861.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 6,
       'position': 'D',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 284230,
     'name': 'Rico Lewis',
     'photo': 'https://media.api-sports.io/football/players/284230.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 82,
       'position': 'D',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 266657,
     'name': 'Savinho',
     'photo': 'https://media.api-sports.io/football/players/266657.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 26,
       'position': 'F',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 21138,
     'name': 'Rayan Aït-Nouri',
     'photo': 'https://media.api-sports.io/football/players/21138.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 21,
       'position': 'D',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]}]},
 {'team': {'id': 63,
   'name': 'Leeds',
   'logo': 'https://media.api-sports.io/football/teams/63.png',
   'update': '2026-03-24T04:12:13+00:00'},
  'players': [{'player': {'id': 80296,
     'name': 'Lucas Perri',
     'photo': 'https://media.api-sports.io/football/players/80296.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 1,
       'position': 'G',
       'rating': '7.7',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 3, 'assists': 0, 'saves': 6},
      'passes': {'total': 45, 'key': None, 'accuracy': '23'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 1, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': 0}}]},
   {'player': {'id': 19201,
     'name': 'Jayden Bogle',
     'photo': 'https://media.api-sports.io/football/players/19201.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 2,
       'position': 'D',
       'rating': '5.9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 30, 'key': None, 'accuracy': '18'},
      'tackles': {'total': 1, 'blocks': None, 'interceptions': 1},
      'duels': {'total': 7, 'won': 4},
      'dribbles': {'attempts': 1, 'success': None, 'past': 1},
      'fouls': {'drawn': 2, 'committed': 1},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 19321,
     'name': 'Joe Rodon',
     'photo': 'https://media.api-sports.io/football/players/19321.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 6,
       'position': 'D',
       'rating': '6.2',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 39, 'key': None, 'accuracy': '34'},
      'tackles': {'total': 3, 'blocks': 1, 'interceptions': None},
      'duels': {'total': 4, 'won': 3},
      'dribbles': {'attempts': None, 'success': None, 'past': 1},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 1, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 64003,
     'name': 'Pascal Struijk',
     'photo': 'https://media.api-sports.io/football/players/64003.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 5,
       'position': 'D',
       'rating': '6.6',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 1, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 28, 'key': None, 'accuracy': '25'},
      'tackles': {'total': 1, 'blocks': 2, 'interceptions': 1},
      'duels': {'total': 12, 'won': 7},
      'dribbles': {'attempts': None, 'success': None, 'past': 1},
      'fouls': {'drawn': 2, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 19760,
     'name': 'James Justin',
     'photo': 'https://media.api-sports.io/football/players/19760.png'},
    'statistics': [{'games': {'minutes': 69,
       'number': 24,
       'position': 'D',
       'rating': '6.9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 28, 'key': None, 'accuracy': '21'},
      'tackles': {'total': None, 'blocks': 2, 'interceptions': 1},
      'duels': {'total': 4, 'won': 4},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': 3, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 32966,
     'name': 'Ao Tanaka',
     'photo': 'https://media.api-sports.io/football/players/32966.png'},
    'statistics': [{'games': {'minutes': 89,
       'number': 22,
       'position': 'M',
       'rating': '6.3',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 25, 'key': None, 'accuracy': '18'},
      'tackles': {'total': 5, 'blocks': None, 'interceptions': 1},
      'duels': {'total': 12, 'won': 7},
      'dribbles': {'attempts': None, 'success': None, 'past': 3},
      'fouls': {'drawn': None, 'committed': 1},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 2279,
     'name': 'Ethan Ampadu',
     'photo': 'https://media.api-sports.io/football/players/2279.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 4,
       'position': 'M',
       'rating': '6.3',
       'captain': True,
       'substitute': False},
      'offsides': None,
      'shots': {'total': 1, 'on': 1},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 54, 'key': None, 'accuracy': '46'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': 1},
      'duels': {'total': 3, 'won': 2},
      'dribbles': {'attempts': 2, 'success': 1, 'past': None},
      'fouls': {'drawn': 1, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 129142,
     'name': 'Ilia Gruev',
     'photo': 'https://media.api-sports.io/football/players/129142.png'},
    'statistics': [{'games': {'minutes': 90,
       'number': 44,
       'position': 'M',
       'rating': '6.9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 40, 'key': 2, 'accuracy': '38'},
      'tackles': {'total': 4, 'blocks': 1, 'interceptions': 1},
      'duels': {'total': 11, 'won': 4},
      'dribbles': {'attempts': 1, 'success': None, 'past': 1},
      'fouls': {'drawn': None, 'committed': 4},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 19329,
     'name': 'Daniel James',
     'photo': 'https://media.api-sports.io/football/players/19329.png'},
    'statistics': [{'games': {'minutes': 45,
       'number': 7,
       'position': 'F',
       'rating': '6.9',
       'captain': False,
       'substitute': False},
      'offsides': 1,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 3, 'key': None, 'accuracy': '2'},
      'tackles': {'total': 2, 'blocks': None, 'interceptions': 1},
      'duels': {'total': 5, 'won': 4},
      'dribbles': {'attempts': 1, 'success': 1, 'past': None},
      'fouls': {'drawn': 1, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 19461,
     'name': 'Lukas Nmecha',
     'photo': 'https://media.api-sports.io/football/players/19461.png'},
    'statistics': [{'games': {'minutes': 82,
       'number': 14,
       'position': 'F',
       'rating': '6.5',
       'captain': False,
       'substitute': False},
      'offsides': 1,
      'shots': {'total': 3, 'on': 2},
      'goals': {'total': 1, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 10, 'key': None, 'accuracy': '7'},
      'tackles': {'total': 1, 'blocks': None, 'interceptions': None},
      'duels': {'total': 11, 'won': 7},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': 1, 'committed': 2},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 1,
       'saved': None}}]},
   {'player': {'id': 162128,
     'name': 'Wilfried Gnonto',
     'photo': 'https://media.api-sports.io/football/players/162128.png'},
    'statistics': [{'games': {'minutes': 45,
       'number': 29,
       'position': 'F',
       'rating': '6.9',
       'captain': False,
       'substitute': False},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 11, 'key': 1, 'accuracy': '9'},
      'tackles': {'total': 3, 'blocks': None, 'interceptions': None},
      'duels': {'total': 11, 'won': 6},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': 3, 'committed': 1},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 833,
     'name': 'Jaka Bijol',
     'photo': 'https://media.api-sports.io/football/players/833.png'},
    'statistics': [{'games': {'minutes': 45,
       'number': 15,
       'position': 'D',
       'rating': '6.5',
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': 1, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 24, 'key': None, 'accuracy': '20'},
      'tackles': {'total': 2, 'blocks': None, 'interceptions': 1},
      'duels': {'total': 5, 'won': 2},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': 1},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 18766,
     'name': 'Dominic Calvert-Lewin',
     'photo': 'https://media.api-sports.io/football/players/18766.png'},
    'statistics': [{'games': {'minutes': 45,
       'number': 9,
       'position': 'F',
       'rating': '7.9',
       'captain': False,
       'substitute': True},
      'offsides': 2,
      'shots': {'total': 1, 'on': 1},
      'goals': {'total': 1, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 4, 'key': None, 'accuracy': '1'},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': 14, 'won': 6},
      'dribbles': {'attempts': 1, 'success': 1, 'past': None},
      'fouls': {'drawn': 3, 'committed': 1},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': 1,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 47969,
     'name': 'Gabriel Gudmundsson',
     'photo': 'https://media.api-sports.io/football/players/47969.png'},
    'statistics': [{'games': {'minutes': 21,
       'number': 3,
       'position': 'D',
       'rating': '6.6',
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 3, 'key': None, 'accuracy': '2'},
      'tackles': {'total': 2, 'blocks': None, 'interceptions': None},
      'duels': {'total': 5, 'won': 5},
      'dribbles': {'attempts': 1, 'success': 1, 'past': None},
      'fouls': {'drawn': 1, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 48389,
     'name': 'Noah Okafor',
     'photo': 'https://media.api-sports.io/football/players/48389.png'},
    'statistics': [{'games': {'minutes': 8,
       'number': 19,
       'position': 'F',
       'rating': '6.5',
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 50739,
     'name': 'Brenden Aaronson',
     'photo': 'https://media.api-sports.io/football/players/50739.png'},
    'statistics': [{'games': {'minutes': 9,
       'number': 11,
       'position': 'M',
       'rating': '6.6',
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': 0, 'saves': None},
      'passes': {'total': 4, 'key': None, 'accuracy': '1'},
      'tackles': {'total': 2, 'blocks': None, 'interceptions': None},
      'duels': {'total': 3, 'won': 3},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 20619,
     'name': 'Illan Meslier',
     'photo': 'https://media.api-sports.io/football/players/20619.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 16,
       'position': 'G',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 19287,
     'name': 'Sam Byram',
     'photo': 'https://media.api-sports.io/football/players/19287.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 25,
       'position': 'D',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 19128,
     'name': 'Jack Harrison',
     'photo': 'https://media.api-sports.io/football/players/19128.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 20,
       'position': 'F',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]},
   {'player': {'id': 250,
     'name': 'Joël Piroe',
     'photo': 'https://media.api-sports.io/football/players/250.png'},
    'statistics': [{'games': {'minutes': None,
       'number': 10,
       'position': 'F',
       'rating': None,
       'captain': False,
       'substitute': True},
      'offsides': None,
      'shots': {'total': None, 'on': None},
      'goals': {'total': None, 'conceded': 0, 'assists': None, 'saves': None},
      'passes': {'total': None, 'key': None, 'accuracy': None},
      'tackles': {'total': None, 'blocks': None, 'interceptions': None},
      'duels': {'total': None, 'won': None},
      'dribbles': {'attempts': None, 'success': None, 'past': None},
      'fouls': {'drawn': None, 'committed': None},
      'cards': {'yellow': 0, 'red': 0},
      'penalty': {'won': None,
       'commited': None,
       'scored': 0,
       'missed': 0,
       'saved': None}}]}]}]

```

# Odds (Pre-Match)

## Odds

Get odds from fixtures, leagues or date.

This endpoint uses a **pagination system**, you can navigate between the different pages with to the `page` parameter.

> **Pagination** : 10 results per page.
> 

We provide pre-match odds between 1 and 14 days before the fixture.

We keep a 7-days history *(The availability of odds may vary according to the leagues, seasons, fixtures and bookmakers)*

**Update Frequency** : This endpoint is updated every 3 hours.

**Recommended Calls** : 1 call every 3 hours.

### query Parameters

| fixture | integer
The id of the fixture |
| --- | --- |
| league | integer
The id of the league |
| season | integer = 4 characters YYYY
The season of the league |
| date | stringYYYY-MM-DD
A valid date |
| timezone | string
A valid timezone from the endpoint `Timezone` |
| page | integerDefault: 1
Use for the pagination |
| bookmaker | integer
The id of the bookmaker |
| bet | integer
The id of the bet |

A nossa lógica é buscar odds por league/season ou date. Para aproveitar ao máximo o request e ter o máximo de informação com um único request. Entendo que o melhor é por date, pois faremos o backfill de ligas que atualmente não estão sendo cobertas, mas que no futuro vão ser, aí já começamos a acumular histórico desde agora. O foco é pegar jogos de 7 dias antes da data atual até 14 dias após a data atual e ir populando a base. Vamos montar toda a lógic usando as contas que temos agora no tier free focando em testes pontuais de sanidade e qualidade dos dados.

### Endpoints com Dimensões.

Necessário para ter as informações de quais são as casas cobertas e mercados cobertos acessar os endpoints. Exemplo abaixo

#### Bookmakers

```python
url = "https://v3.football.api-sports.io/odds/bookmakers"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers, data=payload)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
bookies = resposta['response']
```

```markdown
[{'id': 1, 'name': '10Bet'},
 {'id': 2, 'name': 'Marathonbet'},
 {'id': 3, 'name': 'Betfair'},
 {'id': 4, 'name': 'Pinnacle'},
 {'id': 5, 'name': 'SBO'},
 {'id': 6, 'name': 'Bwin'},
 {'id': 7, 'name': 'William Hill'},
 {'id': 8, 'name': 'Bet365'},
 {'id': 9, 'name': 'Dafabet'},
 {'id': 10, 'name': 'Ladbrokes'},
 {'id': 11, 'name': '1xBet'},
 {'id': 12, 'name': 'BetFred'},
 {'id': 13, 'name': '188Bet'},
 {'id': 15, 'name': 'Interwetten'},
 {'id': 16, 'name': 'Unibet'},
 {'id': 17, 'name': '5Dimes'},
 {'id': 18, 'name': 'Intertops'},
 {'id': 19, 'name': 'Bovada'},
 {'id': 20, 'name': 'Betcris'},
 {'id': 21, 'name': '888Sport'},
 {'id': 22, 'name': 'Tipico'},
 {'id': 23, 'name': 'Sportingbet'},
 {'id': 24, 'name': 'Betway'},
 {'id': 25, 'name': 'Expekt'},
 {'id': 26, 'name': 'Betsson'},
 {'id': 27, 'name': 'NordicBet'},
 {'id': 28, 'name': 'ComeOn'},
 {'id': 30, 'name': 'Netbet'},
 {'id': 32, 'name': 'Betano'},
 {'id': 33, 'name': 'Fonbet'},
 {'id': 34, 'name': 'Superbet'},
 {'id': 36, 'name': 'BetVictor'}]
```

#### Bets

Mercados de Bets disponíveis na API

Get all available bets for pre-match odds.

All bets `id` can be used in endpoint odds as filters, **but are not compatible with endpoint `odds/live` for in-play odds**.

**Update Frequency** : This endpoint is updated several times a week.

```python
url = "https://v3.football.api-sports.io/odds/bets"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers, data=payload)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
bets = resposta['response']
```

```markdown
[{'id': 1, 'name': 'Match Winner'},
 {'id': 2, 'name': 'Home/Away'},
 {'id': 3, 'name': 'Second Half Winner'},
 {'id': 4, 'name': 'Asian Handicap'},
 {'id': 5, 'name': 'Goals Over/Under'},
 {'id': 6, 'name': 'Goals Over/Under First Half'},
 {'id': 7, 'name': 'HT/FT Double'},
 {'id': 8, 'name': 'Both Teams Score'},
 {'id': 9, 'name': 'Handicap Result'},
 {'id': 10, 'name': 'Exact Score'},
 {'id': 11, 'name': 'Highest Scoring Half'},
 {'id': 12, 'name': 'Double Chance'},
 {'id': 13, 'name': 'First Half Winner'},
 {'id': 14, 'name': 'Team To Score First'},
 {'id': 15, 'name': 'Team To Score Last'},
 {'id': 16, 'name': 'Total - Home'},
 {'id': 17, 'name': 'Total - Away'},
 {'id': 18, 'name': 'Handicap Result - First Half'},
 {'id': 19, 'name': 'Asian Handicap First Half'},
 {'id': 20, 'name': 'Double Chance - First Half'},
 {'id': 21, 'name': 'Odd/Even'},
 {'id': 22, 'name': 'Odd/Even - First Half'},
 {'id': 23, 'name': 'Home Odd/Even'},
 {'id': 24, 'name': 'Results/Both Teams Score'},
 {'id': 25, 'name': 'Result/Total Goals'},
 {'id': 26, 'name': 'Goals Over/Under - Second Half'},
 {'id': 27, 'name': 'Clean Sheet - Home'},
 {'id': 28, 'name': 'Clean Sheet - Away'},
 {'id': 29, 'name': 'Win to Nil - Home'},
 {'id': 30, 'name': 'Win to Nil - Away'},
 {'id': 31, 'name': 'Correct Score - First Half'},
 {'id': 32, 'name': 'Win Both Halves'},
 {'id': 33, 'name': 'Double Chance - Second Half'},
 {'id': 34, 'name': 'Both Teams Score - First Half'},
 {'id': 35, 'name': 'Both Teams To Score - Second Half'},
 {'id': 36, 'name': 'Win To Nil'},
 {'id': 37, 'name': 'Home win both halves'},
 {'id': 38, 'name': 'Exact Goals Number'},
 {'id': 39, 'name': 'To Win Either Half'},
 {'id': 40, 'name': 'Home Team Exact Goals Number'},
 {'id': 41, 'name': 'Away Team Exact Goals Number'},
 {'id': 42, 'name': 'Second Half Exact Goals Number'},
 {'id': 43, 'name': 'Home Team Score a Goal'},
 {'id': 44, 'name': 'Away Team Score a Goal'},
 {'id': 45, 'name': 'Corners Over Under'},
 {'id': 46, 'name': 'Exact Goals Number - First Half'},
 {'id': 47, 'name': 'Winning Margin'},
 {'id': 48, 'name': 'To Score In Both Halves By Teams'},
 {'id': 49, 'name': 'Total Goals/Both Teams To Score'},
 {'id': 50, 'name': 'Goal Line'},
 {'id': 51, 'name': 'Halftime Result/Total Goals'},
 {'id': 52, 'name': 'Halftime Result/Both Teams Score'},
 {'id': 53, 'name': 'Away win both halves'},
 {'id': 54, 'name': 'First 10 min Winner'},
 {'id': 55, 'name': 'Corners 1x2'},
 {'id': 56, 'name': 'Corners Asian Handicap'},
 {'id': 57, 'name': 'Home Corners Over/Under'},
 {'id': 58, 'name': 'Away Corners Over/Under'},
 {'id': 59, 'name': 'Own Goal'},
 {'id': 60, 'name': 'Away Odd/Even'},
 {'id': 61, 'name': 'To Qualify'},
 {'id': 62, 'name': 'Correct Score - Second Half'},
 {'id': 63, 'name': 'Odd/Even - Second Half'},
 {'id': 72, 'name': 'Goal Line (1st Half)'},
 {'id': 73, 'name': 'Both Teams to Score 1st Half - 2nd Half'},
 {'id': 74, 'name': '10 Over/Under'},
 {'id': 75, 'name': 'Last Corner'},
 {'id': 76, 'name': 'First Corner'},
 {'id': 77, 'name': 'Total Corners (1st Half)'},
 {'id': 78, 'name': 'RTG_H1'},
 {'id': 79, 'name': 'Cards European Handicap'},
 {'id': 80, 'name': 'Cards Over/Under'},
 {'id': 81, 'name': 'Cards Asian Handicap'},
 {'id': 82, 'name': 'Home Team Total Cards'},
 {'id': 83, 'name': 'Away Team Total Cards'},
 {'id': 84, 'name': 'Total Corners (3 way) (1st Half)'},
 {'id': 85, 'name': 'Total Corners (3 way)'},
 {'id': 86, 'name': 'RCARD'},
 {'id': 87, 'name': 'Total ShotOnGoal'},
 {'id': 88, 'name': 'Home Total ShotOnGoal'},
 {'id': 89, 'name': 'Away Total ShotOnGoal'},
 {'id': 91, 'name': 'Total Goals (3 way)'},
 {'id': 92, 'name': 'Anytime Goal Scorer'},
 {'id': 93, 'name': 'First Goal Scorer'},
 {'id': 94, 'name': 'Last Goal Scorer'},
 {'id': 95, 'name': 'To Score Two or More Goals'},
 {'id': 96, 'name': 'Last Goal Scorer'},
 {'id': 97, 'name': 'First Goal Method'},
 {'id': 99, 'name': 'To Score A Penalty'},
 {'id': 100, 'name': 'To Miss A Penalty'},
 {'id': 102, 'name': 'Player to be booked'},
 {'id': 103, 'name': 'Player to be Sent Off'},
 {'id': 104, 'name': 'Asian Handicap (2nd Half)'},
 {'id': 105, 'name': 'Home Team Total Goals(1st Half)'},
 {'id': 106, 'name': 'Away Team Total Goals(1st Half)'},
 {'id': 107, 'name': 'Home Team Total Goals(2nd Half)'},
 {'id': 108, 'name': 'Away Team Total Goals(2nd Half)'},
 {'id': 109, 'name': 'Draw No Bet (1st Half)'},
 {'id': 110, 'name': 'Scoring Draw'},
 {'id': 111, 'name': 'Home team will score in both halves'},
 {'id': 112, 'name': 'Away team will score in both halves'},
 {'id': 113, 'name': 'Both Teams To Score in Both Halves'},
 {'id': 114, 'name': 'Home Team Score a Goal (1st Half)'},
 {'id': 115, 'name': 'Home Team Score a Goal (2nd Half)'},
 {'id': 116, 'name': 'Away Team Score a Goal (1st Half)'},
 {'id': 117, 'name': 'Away Team Score a Goal (2nd Half)'},
 {'id': 118, 'name': 'Home Win/Over'},
 {'id': 119, 'name': 'Home Win/Under'},
 {'id': 120, 'name': 'Away Win/Over'},
 {'id': 121, 'name': 'Away Win/Under'},
 {'id': 122, 'name': 'Home team will win either half'},
 {'id': 123, 'name': 'Away team will win either half'},
 {'id': 124, 'name': 'Home Come From Behind and Win'},
 {'id': 125, 'name': 'Corners Asian Handicap (1st Half)'},
 {'id': 126, 'name': 'Corners Asian Handicap (2nd Half)'},
 {'id': 127, 'name': 'Total Corners (2nd Half)'},
 {'id': 128, 'name': 'Total Corners (3 way) (2nd Half)'},
 {'id': 129, 'name': 'Away Come From Behind and Win'},
 {'id': 130, 'name': 'Corners 1x2 (1st Half)'},
 {'id': 131, 'name': 'Corners 1x2 (2nd Half)'},
 {'id': 132, 'name': 'Home Total Corners (1st Half)'},
 {'id': 133, 'name': 'Home Total Corners (2nd Half)'},
 {'id': 134, 'name': 'Away Total Corners (1st Half)'},
 {'id': 135, 'name': 'Away Total Corners (2nd Half)'},
 {'id': 136, 'name': '1x2 - 15 minutes'},
 {'id': 137, 'name': '1x2 - 60 minutes'},
 {'id': 138, 'name': '1x2 - 75 minutes'},
 {'id': 139, 'name': '1x2 - 30 minutes'},
 {'id': 140, 'name': 'DC - 30 minutes'},
 {'id': 141, 'name': 'DC - 15 minutes'},
 {'id': 142, 'name': 'DC - 60 minutes'},
 {'id': 143, 'name': 'DC - 75 minutes'},
 {'id': 144, 'name': 'Goal in 1-15 minutes'},
 {'id': 145, 'name': 'Goal in 16-30 minutes'},
 {'id': 146, 'name': 'Goal in 31-45 minutes'},
 {'id': 147, 'name': 'Goal in 46-60 minutes'},
 {'id': 148, 'name': 'Goal in 61-75 minutes'},
 {'id': 149, 'name': 'Goal in 76-90 minutes'},
 {'id': 150, 'name': 'Home Team Yellow Cards'},
 {'id': 151, 'name': 'Away Team Yellow Cards'},
 {'id': 152, 'name': 'Yellow Asian Handicap'},
 {'id': 153, 'name': 'Yellow Over/Under'},
 {'id': 154, 'name': 'Yellow Double Chance'},
 {'id': 155, 'name': 'Yellow Over/Under (1st Half)'},
 {'id': 156, 'name': 'Yellow Over/Under (2nd Half)'},
 {'id': 157, 'name': 'Yellow Odd/Even'},
 {'id': 158, 'name': 'Yellow Cards 1x2'},
 {'id': 159, 'name': 'Yellow Asian Handicap (1st Half)'},
 {'id': 160, 'name': 'Yellow Asian Handicap (2nd Half)'},
 {'id': 161, 'name': 'Yellow Cards 1x2 (1st Half)'},
 {'id': 162, 'name': 'Yellow Cards 1x2 (2nd Half)'},
 {'id': 163, 'name': 'Penalty Awarded'},
 {'id': 164, 'name': 'Offsides Total'},
 {'id': 165, 'name': 'Offsides 1x2'},
 {'id': 166, 'name': 'Offsides Handicap'},
 {'id': 167, 'name': 'Offsides Home Total'},
 {'id': 168, 'name': 'Offsides Away Total'},
 {'id': 169, 'name': 'Offsides Double Chance'},
 {'id': 170, 'name': 'Fouls. Away Total'},
 {'id': 171, 'name': 'Fouls. Home Total'},
 {'id': 172, 'name': 'Fouls. Double Chance'},
 {'id': 173, 'name': 'Fouls. Total'},
 {'id': 174, 'name': 'Fouls. Handicap'},
 {'id': 175, 'name': 'Fouls. 1x2'},
 {'id': 176, 'name': 'ShotOnTarget 1x2'},
 {'id': 177, 'name': 'ShotOnTarget Handicap'},
 {'id': 178, 'name': 'ShotOnTarget Double Chance'},
 {'id': 179, 'name': 'First Team to Score'},
 {'id': 180, 'name': 'Last Team to Score'},
 {'id': 181, 'name': 'European Handicap (2nd Half)'},
 {'id': 182, 'name': 'Draw No Bet (2nd Half)'},
 {'id': 183, 'name': 'Double Chance/Total'},
 {'id': 184, 'name': 'To Score in Both Halves'},
 {'id': 185, 'name': 'First Team to Score (3 way) 1st Half'},
 {'id': 186, 'name': 'Total Goals Number By Ranges'},
 {'id': 187, 'name': 'Total Goals By Ranges (1st Half)'},
 {'id': 188, 'name': 'Clean Sheet'},
 {'id': 189, 'name': 'To Advance Handicap'},
 {'id': 190, 'name': 'Home Exact Goals Number (1st Half)'},
 {'id': 191, 'name': 'Away Exact Goals Number (1st Half)'},
 {'id': 192, 'name': 'Home Highest Scoring Half'},
 {'id': 193, 'name': 'Away Highest Scoring Half'},
 {'id': 194, 'name': 'Result/Total Goals (2nd Half)'},
 {'id': 195, 'name': 'Either Team Wins By 1 Goals'},
 {'id': 196, 'name': 'Either Team Wins By 2 Goals'},
 {'id': 197, 'name': 'Over/Under 15m-30m'},
 {'id': 198, 'name': 'Over/Under 30m-45m'},
 {'id': 199, 'name': 'Home Win To Nill (1st Half)'},
 {'id': 200, 'name': 'Home Win To Nill (2nd Half)'},
 {'id': 201, 'name': 'To Score In 1st Half'},
 {'id': 202, 'name': 'To Score In 2nd Half'},
 {'id': 203, 'name': 'Yellow Cards. Odd/Even (1st Half)'},
 {'id': 204, 'name': 'Yellow Cards. Odd/Even (2nd Half)'},
 {'id': 205, 'name': 'First Team to Score (3 way) 2nd Half'},
 {'id': 206, 'name': 'Home No Bet'},
 {'id': 207, 'name': 'Away No Bet'},
 {'id': 208, 'name': 'Corners. First Corner (3 way)'},
 {'id': 209, 'name': 'Home Come From Behind and Draw'},
 {'id': 210, 'name': 'Away Come From Behind and Draw'},
 {'id': 211, 'name': 'Total Shots'},
 {'id': 212, 'name': 'Player Assists'},
 {'id': 213, 'name': 'Player Triples'},
 {'id': 214, 'name': 'Player Points'},
 {'id': 215, 'name': 'Player Singles'},
 {'id': 216, 'name': 'Multi Touchdown Scorer (2 or More)'},
 {'id': 217, 'name': 'Multi Touchdown Scorer (3 or More)'},
 {'id': 218, 'name': 'Away Anytime Goal Scorer'},
 {'id': 219, 'name': 'Away First Goal Scorer'},
 {'id': 220, 'name': 'Shots. Away Total'},
 {'id': 221, 'name': 'Shots. Home Total'},
 {'id': 222, 'name': 'To Win From Behind'},
 {'id': 223, 'name': 'Number of Goals In Match (Range)'},
 {'id': 224, 'name': 'Game Decided After Penalties'},
 {'id': 225, 'name': 'Game Decided in Extra Time'},
 {'id': 226, 'name': 'Away Last Goal Scorer'},
 {'id': 227, 'name': 'Goal Method Header'},
 {'id': 228, 'name': 'Home Goal Method Header'},
 {'id': 229, 'name': 'Goal Method Outside the Box'},
 {'id': 230, 'name': 'Home Goal Method Outside the Box'},
 {'id': 231, 'name': 'Home Anytime Goal Scorer'},
 {'id': 232, 'name': 'Home First Goal Scorer'},
 {'id': 233, 'name': 'Home Last Goal Scorer'},
 {'id': 234, 'name': 'Home To Score Three or More Goals'},
 {'id': 235, 'name': 'Away To Score Three or More Goals'},
 {'id': 236, 'name': 'Away To Score Two or More Goals'},
 {'id': 237, 'name': 'Home To Score Two or More Goals'},
 {'id': 238, 'name': 'Home Team Goalscorers First'},
 {'id': 239, 'name': 'Corners. European Handicap'},
 {'id': 240, 'name': 'Home Player Shots'},
 {'id': 241, 'name': 'Away Player Shots'},
 {'id': 242, 'name': 'Player Shots On Target'},
 {'id': 243, 'name': 'Home Shots On Target'},
 {'id': 244, 'name': 'Away Shots On Target'},
 {'id': 245, 'name': 'Away Goal Method Header'},
 {'id': 246, 'name': 'Away Goal Method Outside the Box'},
 {'id': 247, 'name': 'Corners Race To'},
 {'id': 248, 'name': 'Time Of 1st Score'},
 {'id': 249, 'name': 'Multicorners'},
 {'id': 250, 'name': 'First Card Received (3 way)'},
 {'id': 251, 'name': 'Player to be booked'},
 {'id': 252, 'name': 'Both Teams to Receive a Card'},
 {'id': 253, 'name': 'Time Of 1st Score'},
 {'id': 254, 'name': 'Team Performances (Range)'},
 {'id': 255, 'name': 'Home Player Assists'},
 {'id': 256, 'name': 'Away Player Assists'},
 {'id': 257, 'name': 'Player to Score or Assist'},
 {'id': 258, 'name': 'Home Player to Score or Assist'},
 {'id': 259, 'name': 'Away Player to Score or Assist'},
 {'id': 260, 'name': 'Team Time Of 1st Score'},
 {'id': 261, 'name': 'Total Goal Minutes (Range)'},
 {'id': 262, 'name': 'Late Goal (Range)'},
 {'id': 263, 'name': 'Early Goal (Range)'},
 {'id': 264, 'name': 'Player Shots On Target Total'},
 {'id': 265, 'name': 'Player Shots Total'},
 {'id': 266, 'name': 'Player Fouls Committed'},
 {'id': 267, 'name': 'Goalkeeper Saves'},
 {'id': 268, 'name': 'Home Goalkeeper Saves'},
 {'id': 269, 'name': 'Home Player Shots On Target Total'},
 {'id': 270, 'name': 'Home Player Shots Total'},
 {'id': 271, 'name': 'Home Player Fouls Committed'},
 {'id': 272, 'name': 'Home Player Tackles'},
 {'id': 273, 'name': 'Home Player Passes'},
 {'id': 274, 'name': 'Away Goalkeeper Saves'},
 {'id': 275, 'name': 'Away Player Shots On Target Total'},
 {'id': 276, 'name': 'Away Player Shots Total'},
 {'id': 277, 'name': 'Away Player Fouls Committed'},
 {'id': 278, 'name': 'Away Player Tackles'},
 {'id': 279, 'name': 'Away Player Passes'},
 {'id': 280, 'name': 'First Set Piece 5 Minutes'},
 {'id': 281, 'name': 'Total Tackles'},
 {'id': 282, 'name': 'Double Chance/Both Teams To Score'},
 {'id': 283, 'name': 'Away Win To Nill (1st Half)'},
 {'id': 284, 'name': 'Away Win To Nill (2nd Half)'},
 {'id': 285, 'name': 'Team To Score (Goals)'},
 {'id': 286, 'name': 'Team Goalscorers First'},
 {'id': 287, 'name': 'Team Goalscorers Last'},
 {'id': 288, 'name': 'Home Team Goalscorers Last'},
 {'id': 289, 'name': 'Away Team Goalscorers First'},
 {'id': 290, 'name': 'Away Team Goalscorers Last'},
 {'id': 291, 'name': 'Time of First Goal Brackets (Range)'},
 {'id': 292, 'name': 'Over/Under between 0 and 10m'},
 {'id': 293, 'name': 'Double Chance 0-15m'},
 {'id': 294, 'name': 'Double Chance 15-30m'},
 {'id': 295, 'name': 'Corners. Total (Range)'},
 {'id': 296, 'name': 'Double Chance 30-45m'},
 {'id': 297, 'name': 'Corners. total between 0 and 10m'},
 {'id': 298, 'name': 'Method of Victory'},
 {'id': 299, 'name': 'Cards over/under between 0 and 10 m'},
 {'id': 300, 'name': 'Both Teams to Receive 2+ Cards'},
 {'id': 301, 'name': 'Tackles. Away Total'},
 {'id': 302, 'name': 'Tackles. Home Total'},
 {'id': 303, 'name': 'Over/Under between 0 and 10 m'},
 {'id': 304, 'name': 'Over/Under between  0 and 10 m'},
 {'id': 305, 'name': 'Race to the 2nd goal?'},
 {'id': 306, 'name': 'Race to the 3rd goal?'},
 {'id': 307, 'name': 'Corners. Double Chance'},
 {'id': 308, 'name': 'Race To'},
 {'id': 309, 'name': 'Yellow Cards. Home Total (1st Half)'},
 {'id': 310, 'name': 'Yellow Cards Away Total (1st Half)'},
 {'id': 311, 'name': 'Which team will score the 1st goal?'},
 {'id': 312, 'name': '1x2 - 20 minutes'},
 {'id': 313, 'name': 'Offsides Odd/Even'},
 {'id': 314, 'name': 'Fouls Odd/Even'},
 {'id': 315, 'name': 'Saves Total'},
 {'id': 316, 'name': 'Saves 1x2'},
 {'id': 317, 'name': 'Saves Asian H'},
 {'id': 318, 'name': 'Saves O/U Home'},
 {'id': 319, 'name': 'Saves O/U Away'},
 {'id': 320, 'name': 'Saves Double Chance'},
 {'id': 321, 'name': 'Penalty Awarded (1st Half)'},
 {'id': 322, 'name': 'Penalty Awarded (2nd Half)'},
 {'id': 323, 'name': 'Saves Odd/Even'},
 {'id': 324, 'name': 'Corner in 1-15 minutes'},
 {'id': 325, 'name': 'Corner in 16-30 minutes'},
 {'id': 326, 'name': 'Corner in 31-45 minutes'},
 {'id': 327, 'name': 'Corner in 45-60 minutes'},
 {'id': 328, 'name': 'Corner in 60-75 minutes'},
 {'id': 329, 'name': 'Corner in 75-90 minutes'},
 {'id': 330, 'name': 'Home Not lose/Over'},
 {'id': 331, 'name': 'Home Not lose/Under'},
 {'id': 332, 'name': 'Away Not lose/Over'},
 {'id': 333, 'name': 'Away Not lose/Under'},
 {'id': 334, 'name': '1x2 - 70 minutes'},
 {'id': 335, 'name': 'Red Cards Over/Under'},
 {'id': 336, 'name': 'Goal Line'},
 {'id': 337, 'name': 'Asian Handicap (Sets)'},
 {'id': 338, 'name': 'Corners. Odd/Even'},
 {'id': 339, 'name': 'Corners. Double Chance'},
 {'id': 340, 'name': 'Shots.1x2'},
 {'id': 341, 'name': None},
 {'id': 342, 'name': 'Red Card In The Match (1st Half)'},
 {'id': 343, 'name': 'Fouls. Odd/Even'},
 {'id': 344, 'name': 'Odd/Even (1st Set)'},
 {'id': 345, 'name': 'Set Betting'},
 {'id': 346, 'name': 'Extra Point (1st Set)'},
 {'id': 347, 'name': 'Home Winning Margin (1st Set)'},
 {'id': 348, 'name': 'Away Winning Margin (1st Set)'}]
```

## Odds por Data

```python
url = "https://v3.football.api-sports.io/odds?date=2026-04-01"

payload={}
headers = {
  'x-apisports-key': '11b0151f3fcf9b5522de91b35f6b556b',
}

response = requests.request("GET", url, headers=headers, data=payload)

resposta = response.json()

qtde = resposta['results']
pages = resposta['paging']
odds_date = resposta['response']
odds_date[0]
```

```markdown
{'league': {'id': 730,
  'name': 'Football League - Highland League',
  'country': 'Scotland',
  'logo': 'https://media.api-sports.io/football/leagues/730.png',
  'flag': 'https://media.api-sports.io/flags/gb-sct.svg',
  'season': 2025},
 'fixture': {'id': 1379854,
  'timezone': 'UTC',
  'date': '2026-04-01T19:00:00+00:00',
  'timestamp': 1775070000},
 'update': '2026-04-01T16:00:25+00:00',
 'bookmakers': [{'id': 2,
   'name': 'Marathonbet',
   'bets': [{'id': 1,
     'name': 'Match Winner',
     'values': [{'value': 'Home', 'odd': '1.78'},
      {'value': 'Draw', 'odd': '3.60'},
      {'value': 'Away', 'odd': '3.65'}]},
    {'id': 3,
     'name': 'Second Half Winner',
     'values': [{'value': 'Home', 'odd': '2.08'},
      {'value': 'Draw', 'odd': '2.69'},
      {'value': 'Away', 'odd': '3.68'}]},
    {'id': 4,
     'name': 'Asian Handicap',
     'values': [{'value': 'Home -1.25', 'odd': '2.74'},
      {'value': 'Away -1.25', 'odd': '1.35'},
      {'value': 'Home -1', 'odd': '2.45'},
      {'value': 'Away -1', 'odd': '1.47'},
      {'value': 'Home -0.75', 'odd': '2.00'},
      {'value': 'Away -0.75', 'odd': '1.65'},
      {'value': 'Home -0.25', 'odd': '1.56'},
      {'value': 'Away -0.25', 'odd': '2.15'},
      {'value': 'Home +0', 'odd': '1.35'},
      {'value': 'Away +0', 'odd': '2.74'},
      {'value': 'Home +0.25', 'odd': '1.27'},
      {'value': 'Away +0.25', 'odd': '3.14'},
      {'value': 'Home -2', 'odd': '5.30'},
      {'value': 'Away -2', 'odd': '1.09'},
      {'value': 'Home +1', 'odd': '1.04'},
      {'value': 'Away +1', 'odd': '7.10'},
      {'value': 'Home -1.75', 'odd': '3.82'},
      {'value': 'Away -1.75', 'odd': '1.18'},
      {'value': 'Home -1.5', 'odd': '3.08'},
      {'value': 'Away -1.5', 'odd': '1.28'},
      {'value': 'Home +1.5', 'odd': '1.02'},
      {'value': 'Away +1.5', 'odd': '8.10'},
      {'value': 'Home -2.5', 'odd': '6.15'},
      {'value': 'Away -2.5', 'odd': '1.06'}]},
    {'id': 5,
     'name': 'Goals Over/Under',
     'values': [{'value': 'Over 2.0', 'odd': '1.21'},
      {'value': 'Under 2.0', 'odd': '3.58'},
      {'value': 'Over 2.25', 'odd': '1.37'},
      {'value': 'Under 2.25', 'odd': '2.66'},
      {'value': 'Over 2.5', 'odd': '1.53'},
      {'value': 'Under 2.5', 'odd': '2.21'},
      {'value': 'Over 2.75', 'odd': '1.67'},
      {'value': 'Under 2.75', 'odd': '1.98'},
      {'value': 'Over 3.5', 'odd': '2.41'},
      {'value': 'Under 3.5', 'odd': '1.49'},
      {'value': 'Over 3.0', 'odd': '1.86'},
      {'value': 'Under 3.0', 'odd': '1.76'},
      {'value': 'Over 4.5', 'odd': '4.20'},
      {'value': 'Under 4.5', 'odd': '1.15'},
      {'value': 'Over 3.25', 'odd': '2.12'},
      {'value': 'Under 3.25', 'odd': '1.58'},
      {'value': 'Over 3.75', 'odd': '2.74'},
      {'value': 'Under 3.75', 'odd': '1.35'},
      {'value': 'Over 4.0', 'odd': '3.50'},
      {'value': 'Under 4.0', 'odd': '1.22'},
      {'value': 'Over 4.25', 'odd': '3.86'},
      {'value': 'Under 4.25', 'odd': '1.18'},
      {'value': 'Over 5.0', 'odd': '7.30'},
      {'value': 'Under 5.0', 'odd': '1.03'}]},
    {'id': 6,
     'name': 'Goals Over/Under First Half',
     'values': [{'value': 'Over 1.5', 'odd': '2.29'},
      {'value': 'Under 1.5', 'odd': '1.51'},
      {'value': 'Over 2.0', 'odd': '3.58'},
      {'value': 'Under 2.0', 'odd': '1.22'},
      {'value': 'Over 0.5', 'odd': '1.26'},
      {'value': 'Under 0.5', 'odd': '3.28'},
      {'value': 'Over 1.0', 'odd': '1.56'},
      {'value': 'Under 1.0', 'odd': '2.24'}]},
    {'id': 26,
     'name': 'Goals Over/Under - Second Half',
     'values': [{'value': 'Over 1.5', 'odd': '1.77'},
      {'value': 'Under 1.5', 'odd': '1.92'},
      {'value': 'Over 2.0', 'odd': '2.53'},
      {'value': 'Under 2.0', 'odd': '1.42'},
      {'value': 'Over 1.0', 'odd': '1.23'},
      {'value': 'Under 1.0', 'odd': '3.50'}]},
    {'id': 8,
     'name': 'Both Teams Score',
     'values': [{'value': 'Yes', 'odd': '1.51'},
      {'value': 'No', 'odd': '2.29'}]},
    {'id': 9,
     'name': 'Handicap Result',
     'values': [{'value': 'Home -1', 'odd': '3.08'},
      {'value': 'Away -1', 'odd': '1.82'},
      {'value': 'Draw -1', 'odd': '3.84'},
      {'value': 'Home -2', 'odd': '6.15'},
      {'value': 'Draw -2', 'odd': '5.50'},
      {'value': 'Away -2', 'odd': '1.28'}]},
    {'id': 12,
     'name': 'Double Chance',
     'values': [{'value': 'Home/Draw', 'odd': '1.19'},
      {'value': 'Home/Away', 'odd': '1.20'},
      {'value': 'Draw/Away', 'odd': '1.82'}]},
    {'id': 13,
     'name': 'First Half Winner',
     'values': [{'value': 'Home', 'odd': '2.32'},
      {'value': 'Draw', 'odd': '2.22'},
      {'value': 'Away', 'odd': '4.15'}]},
    {'id': 14,
     'name': 'Team To Score First',
     'values': [{'value': 'Home', 'odd': '1.57'},
      {'value': 'Draw', 'odd': '16.00'},
      {'value': 'Away', 'odd': '2.36'}]},
    {'id': 15,
     'name': 'Team To Score Last',
     'values': [{'value': 'Home', 'odd': '1.58'},
      {'value': 'Draw', 'odd': '16.00'},
      {'value': 'Away', 'odd': '2.34'}]},
    {'id': 16,
     'name': 'Total - Home',
     'values': [{'value': 'Over 1.5', 'odd': '1.67'},
      {'value': 'Under 1.5', 'odd': '2.05'},
      {'value': 'Over 2.5', 'odd': '2.78'},
      {'value': 'Under 2.5', 'odd': '1.36'},
      {'value': 'Over 1', 'odd': '1.18'},
      {'value': 'Under 1', 'odd': '4.05'},
      {'value': 'Over 2', 'odd': '2.32'},
      {'value': 'Under 2', 'odd': '1.51'}]},
    {'id': 17,
     'name': 'Total - Away',
     'values': [{'value': 'Over 1.5', 'odd': '2.57'},
      {'value': 'Under 1.5', 'odd': '1.42'},
      {'value': 'Over 1', 'odd': '1.69'},
      {'value': 'Under 1', 'odd': '2.02'},
      {'value': 'Over 2', 'odd': '5.15'},
      {'value': 'Under 2', 'odd': '1.10'}]},
    {'id': 18,
     'name': 'Handicap Result - First Half',
     'values': [{'value': 'Home -1', 'odd': '6.45'},
      {'value': 'Away -1', 'odd': '1.45'},
      {'value': 'Draw -1', 'odd': '3.60'}]},
    {'id': 19,
     'name': 'Asian Handicap First Half',
     'values': [{'value': 'Home -1', 'odd': '5.00'},
      {'value': 'Away -1', 'odd': '1.10'},
      {'value': 'Home -0.25', 'odd': '1.90'},
      {'value': 'Away -0.25', 'odd': '1.75'},
      {'value': 'Home +0', 'odd': '1.44'},
      {'value': 'Away +0', 'odd': '2.47'},
      {'value': 'Home +0.25', 'odd': '1.26'},
      {'value': 'Away +0.25', 'odd': '3.28'}]},
    {'id': 20,
     'name': 'Double Chance - First Half',
     'values': [{'value': 'Home/Draw', 'odd': '1.13'},
      {'value': 'Home/Away', 'odd': '1.49'},
      {'value': 'Draw/Away', 'odd': '1.45'}]},
    {'id': 33,
     'name': 'Double Chance - Second Half',
     'values': [{'value': 'Home/Draw', 'odd': '1.18'},
      {'value': 'Home/Away', 'odd': '1.33'},
      {'value': 'Draw/Away', 'odd': '1.56'}]},
    {'id': 34,
     'name': 'Both Teams Score - First Half',
     'values': [{'value': 'Yes', 'odd': '3.58'},
      {'value': 'No', 'odd': '1.22'}]},
    {'id': 35,
     'name': 'Both Teams To Score - Second Half',
     'values': [{'value': 'Yes', 'odd': '2.67'},
      {'value': 'No', 'odd': '1.38'}]},
    {'id': 21,
     'name': 'Odd/Even',
     'values': [{'value': 'Odd', 'odd': '1.85'},
      {'value': 'Even', 'odd': '1.79'}]},
    {'id': 22,
     'name': 'Odd/Even - First Half',
     'values': [{'value': 'Odd', 'odd': '1.99'},
      {'value': 'Even', 'odd': '1.68'}]},
    {'id': 43,
     'name': 'Home Team Score a Goal',
     'values': [{'value': 'Yes', 'odd': '1.09'},
      {'value': 'No', 'odd': '5.50'}]},
    {'id': 44,
     'name': 'Away Team Score a Goal',
     'values': [{'value': 'Yes', 'odd': '1.29'},
      {'value': 'No', 'odd': '3.08'}]},
    {'id': 104,
     'name': 'Asian Handicap (2nd Half)',
     'values': [{'value': 'Home -1', 'odd': '3.72'},
      {'value': 'Away -1', 'odd': '1.20'},
      {'value': 'Home -0.25', 'odd': '1.77'},
      {'value': 'Away -0.25', 'odd': '1.87'},
      {'value': 'Home +0', 'odd': '1.43'},
      {'value': 'Away +0', 'odd': '2.50'},
      {'value': 'Home +0.25', 'odd': '1.29'},
      {'value': 'Away +0.25', 'odd': '3.08'}]},
    {'id': 63,
     'name': 'Odd/Even - Second Half',
     'values': [{'value': 'Odd', 'odd': '1.87'},
      {'value': 'Even', 'odd': '1.77'}]},
    {'id': 181,
     'name': 'European Handicap (2nd Half)',
     'values': [{'value': 'Home -1', 'odd': '4.90'},
      {'value': 'Away -1', 'odd': '1.56'},
      {'value': 'Draw -1', 'odd': '3.60'}]},
    {'id': 111,
     'name': 'Home team will score in both halves',
     'values': [{'value': 'Yes', 'odd': '2.47'},
      {'value': 'No', 'odd': '1.44'}]},
    {'id': 112,
     'name': 'Away team will score in both halves',
     'values': [{'value': 'Yes', 'odd': '4.10'},
      {'value': 'No', 'odd': '1.17'}]},
    {'id': 184,
     'name': 'To Score in Both Halves',
     'values': [{'value': 'Yes', 'odd': '1.52'},
      {'value': 'No', 'odd': '2.27'}]},
    {'id': 113,
     'name': 'Both Teams To Score in Both Halves',
     'values': [{'value': 'Yes', 'odd': '9.60'},
      {'value': 'No', 'odd': '1.00'}]}]},
  {'id': 4,
   'name': 'Pinnacle',
   'bets': [{'id': 1,
     'name': 'Match Winner',
     'values': [{'value': 'Home', 'odd': '1.85'},
      {'value': 'Draw', 'odd': '3.61'},
      {'value': 'Away', 'odd': '3.53'}]},
    {'id': 4,
     'name': 'Asian Handicap',
     'values': [{'value': 'Home -1.25', 'odd': '2.81'},
      {'value': 'Away -1.25', 'odd': '1.37'},
      {'value': 'Home -1', 'odd': '2.49'},
      {'value': 'Away -1', 'odd': '1.47'},
      {'value': 'Home -0.75', 'odd': '2.09'},
      {'value': 'Away -0.75', 'odd': '1.68'},
      {'value': 'Home -0.5', 'odd': '1.85'},
      {'value': 'Away -0.5', 'odd': '1.90'},
      {'value': 'Home -0.25', 'odd': '1.63'},
      {'value': 'Away -0.25', 'odd': '2.17'},
      {'value': 'Home +0', 'odd': '1.41'},
      {'value': 'Away +0', 'odd': '2.69'},
      {'value': 'Home +0.25', 'odd': '1.32'},
      {'value': 'Away +0.25', 'odd': '3.06'}]},
    {'id': 5,
     'name': 'Goals Over/Under',
     'values': [{'value': 'Over 2.25', 'odd': '1.41'},
      {'value': 'Under 2.25', 'odd': '2.68'},
      {'value': 'Over 2.5', 'odd': '1.57'},
      {'value': 'Under 2.5', 'odd': '2.24'},
      {'value': 'Over 2.75', 'odd': '1.72'},
      {'value': 'Under 2.75', 'odd': '2.02'},
      {'value': 'Over 3.5', 'odd': '2.43'},
      {'value': 'Under 3.5', 'odd': '1.49'},
      {'value': 'Over 3.0', 'odd': '1.96'},
      {'value': 'Under 3.0', 'odd': '1.80'},
      {'value': 'Over 3.25', 'odd': '2.21'},
      {'value': 'Under 3.25', 'odd': '1.61'},
      {'value': 'Over 3.75', 'odd': '2.82'},
      {'value': 'Under 3.75', 'odd': '1.37'},
      {'value': 'Over 4.0', 'odd': '2.93'},
      {'value': 'Under 4.0', 'odd': '1.35'}]},
    {'id': 6,
     'name': 'Goals Over/Under First Half',
     'values': [{'value': 'Over 1.5', 'odd': '2.30'},
      {'value': 'Under 1.5', 'odd': '1.55'},
      {'value': 'Over 1.75', 'odd': '2.80'},
      {'value': 'Under 1.75', 'odd': '1.37'},
      {'value': 'Over 0.75', 'odd': '1.36'},
      {'value': 'Under 0.75', 'odd': '2.85'},
      {'value': 'Over 1.0', 'odd': '1.54'},
      {'value': 'Under 1.0', 'odd': '2.33'},
      {'value': 'Over 1.25', 'odd': '1.94'},
      {'value': 'Under 1.25', 'odd': '1.80'}]},
    {'id': 16,
     'name': 'Total - Home',
     'values': [{'value': 'Over 1.5', 'odd': '1.72'},
      {'value': 'Under 1.5', 'odd': '2.05'}]},
    {'id': 17,
     'name': 'Total - Away',
     'values': [{'value': 'Over 1.5', 'odd': '2.57'},
      {'value': 'Under 1.5', 'odd': '1.47'}]},
    {'id': 19,
     'name': 'Asian Handicap First Half',
     'values': [{'value': 'Home -0.75', 'odd': '2.89'},
      {'value': 'Away -0.75', 'odd': '1.35'},
      {'value': 'Home -0.5', 'odd': '2.31'},
      {'value': 'Away -0.5', 'odd': '1.55'},
      {'value': 'Home -0.25', 'odd': '1.92'},
      {'value': 'Away -0.25', 'odd': '1.83'},
      {'value': 'Home +0', 'odd': '1.47'},
      {'value': 'Away +0', 'odd': '2.50'},
      {'value': 'Home +0.25', 'odd': '1.30'},
      {'value': 'Away +0.25', 'odd': '3.12'}]},
    {'id': 105,
     'name': 'Home Team Total Goals(1st Half)',
     'values': [{'value': 'Over 0.5', 'odd': '1.66'},
      {'value': 'Under 0.5', 'odd': '2.10'}]},
    {'id': 106,
     'name': 'Away Team Total Goals(1st Half)',
     'values': [{'value': 'Over 0.5', 'odd': '2.18'},
      {'value': 'Under 0.5', 'odd': '1.61'}]}]},
  {'id': 11,
   'name': '1xBet',
   'bets': [{'id': 1,
     'name': 'Match Winner',
     'values': [{'value': 'Home', 'odd': '1.80'},
      {'value': 'Draw', 'odd': '3.60'},
      {'value': 'Away', 'odd': '3.72'}]},
    {'id': 3,
     'name': 'Second Half Winner',
     'values': [{'value': 'Home', 'odd': '2.10'},
      {'value': 'Draw', 'odd': '2.69'},
      {'value': 'Away', 'odd': '3.80'}]},
    {'id': 4,
     'name': 'Asian Handicap',
     'values': [{'value': 'Home -1.25', 'odd': '2.74'},
      {'value': 'Away -1.25', 'odd': '1.35'},
      {'value': 'Home -1', 'odd': '2.45'},
      {'value': 'Away -1', 'odd': '1.47'},
      {'value': 'Home -0.75', 'odd': '2.00'},
      {'value': 'Away -0.75', 'odd': '1.65'},
      {'value': 'Home -0.25', 'odd': '1.56'},
      {'value': 'Away -0.25', 'odd': '2.15'},
      {'value': 'Home +0', 'odd': '1.35'},
      {'value': 'Away +0', 'odd': '2.74'},
      {'value': 'Home +0.25', 'odd': '1.27'},
      {'value': 'Away +0.25', 'odd': '3.14'},
      {'value': 'Home -3', 'odd': '6.90'},
      {'value': 'Away -3', 'odd': '1.06'},
      {'value': 'Home -2', 'odd': '5.30'},
      {'value': 'Away -2', 'odd': '1.09'},
      {'value': 'Home +1', 'odd': '1.04'},
      {'value': 'Away +1', 'odd': '7.10'},
      {'value': 'Home -1.75', 'odd': '3.82'},
      {'value': 'Away -1.75', 'odd': '1.18'},
      {'value': 'Home -1.5', 'odd': '3.08'},
      {'value': 'Away -1.5', 'odd': '1.28'},
      {'value': 'Home +1.5', 'odd': '1.02'},
      {'value': 'Away +1.5', 'odd': '8.10'},
      {'value': 'Home -2.5', 'odd': '6.15'},
      {'value': 'Away -2.5', 'odd': '1.06'},
      {'value': 'Home -3.5', 'odd': '8.00'},
      {'value': 'Away -3.5', 'odd': '1.04'}]},
    {'id': 5,
     'name': 'Goals Over/Under',
     'values': [{'value': 'Over 1.5', 'odd': '1.15'},
      {'value': 'Under 1.5', 'odd': '4.50'},
      {'value': 'Over 2.0', 'odd': '1.21'},
      {'value': 'Under 2.0', 'odd': '3.58'},
      {'value': 'Over 2.25', 'odd': '1.37'},
      {'value': 'Under 2.25', 'odd': '2.66'},
      {'value': 'Over 2.5', 'odd': '1.53'},
      {'value': 'Under 2.5', 'odd': '2.21'},
      {'value': 'Over 2.75', 'odd': '1.67'},
      {'value': 'Under 2.75', 'odd': '1.98'},
      {'value': 'Over 3.5', 'odd': '2.41'},
      {'value': 'Under 3.5', 'odd': '1.49'},
      {'value': 'Over 0.5', 'odd': '1.01'},
      {'value': 'Under 0.5', 'odd': '11.50'},
      {'value': 'Over 1.0', 'odd': '1.02'},
      {'value': 'Under 1.0', 'odd': '9.00'},
      {'value': 'Over 3.0', 'odd': '1.86'},
      {'value': 'Under 3.0', 'odd': '1.76'},
      {'value': 'Over 4.5', 'odd': '4.20'},
      {'value': 'Under 4.5', 'odd': '1.15'},
      {'value': 'Over 3.25', 'odd': '2.12'},
      {'value': 'Under 3.25', 'odd': '1.58'},
      {'value': 'Over 3.75', 'odd': '2.74'},
      {'value': 'Under 3.75', 'odd': '1.35'},
      {'value': 'Over 4.0', 'odd': '3.50'},
      {'value': 'Under 4.0', 'odd': '1.22'},
      {'value': 'Over 4.25', 'odd': '3.86'},
      {'value': 'Under 4.25', 'odd': '1.18'},
      {'value': 'Over 5.0', 'odd': '7.30'},
      {'value': 'Under 5.0', 'odd': '1.03'}]},
    {'id': 6,
     'name': 'Goals Over/Under First Half',
     'values': [{'value': 'Over 1.5', 'odd': '2.29'},
      {'value': 'Under 1.5', 'odd': '1.51'},
      {'value': 'Over 1.75', 'odd': '2.57'},
      {'value': 'Under 1.75', 'odd': '1.42'},
      {'value': 'Over 2.0', 'odd': '4.15'},
      {'value': 'Under 2.0', 'odd': '1.19'},
      {'value': 'Over 2.5', 'odd': '5.00'},
      {'value': 'Under 2.5', 'odd': '1.12'},
      {'value': 'Over 0.5', 'odd': '1.26'},
      {'value': 'Under 0.5', 'odd': '3.28'},
      {'value': 'Over 0.75', 'odd': '1.37'},
      {'value': 'Under 0.75', 'odd': '2.75'},
      {'value': 'Over 1.0', 'odd': '1.56'},
      {'value': 'Under 1.0', 'odd': '2.24'},
      {'value': 'Over 1.25', 'odd': '1.93'},
      {'value': 'Under 1.25', 'odd': '1.74'}]},
    {'id': 26,
     'name': 'Goals Over/Under - Second Half',
     'values': [{'value': 'Over 1.5', 'odd': '1.77'},
      {'value': 'Under 1.5', 'odd': '1.92'},
      {'value': 'Over 1.75', 'odd': '2.02'},
      {'value': 'Under 1.75', 'odd': '1.67'},
      {'value': 'Over 2.0', 'odd': '2.53'},
      {'value': 'Under 2.0', 'odd': '1.42'},
      {'value': 'Over 0.5', 'odd': '1.14'},
      {'value': 'Under 0.5', 'odd': '4.90'},
      {'value': 'Over 1.0', 'odd': '1.23'},
      {'value': 'Under 1.0', 'odd': '3.50'},
      {'value': 'Over 1.25', 'odd': '1.50'},
      {'value': 'Under 1.25', 'odd': '2.34'}]},
    {'id': 8,
     'name': 'Both Teams Score',
     'values': [{'value': 'Yes', 'odd': '1.51'},
      {'value': 'No', 'odd': '2.34'}]},
    {'id': 11,
     'name': 'Highest Scoring Half',
     'values': [{'value': 'Draw', 'odd': '3.80'},
      {'value': '1st Half', 'odd': '3.00'},
      {'value': '2nd Half', 'odd': '1.91'}]},
    {'id': 12,
     'name': 'Double Chance',
     'values': [{'value': 'Home/Draw', 'odd': '1.19'},
      {'value': 'Home/Away', 'odd': '1.20'},
      {'value': 'Draw/Away', 'odd': '1.82'}]},
    {'id': 13,
     'name': 'First Half Winner',
     'values': [{'value': 'Home', 'odd': '2.34'},
      {'value': 'Draw', 'odd': '2.22'},
      {'value': 'Away', 'odd': '4.32'}]},
    {'id': 16,
     'name': 'Total - Home',
     'values': [{'value': 'Over 1.5', 'odd': '1.75'},
      {'value': 'Under 1.5', 'odd': '1.95'},
      {'value': 'Over 2.5', 'odd': '3.05'},
      {'value': 'Under 2.5', 'odd': '1.33'},
      {'value': 'Over 3.5', 'odd': '5.90'},
      {'value': 'Under 3.5', 'odd': '1.08'},
      {'value': 'Over 1', 'odd': '1.23'},
      {'value': 'Under 1', 'odd': '3.75'},
      {'value': 'Over 2', 'odd': '2.35'},
      {'value': 'Under 2', 'odd': '1.52'},
      {'value': 'Over 3', 'odd': '5.20'},
      {'value': 'Under 3', 'odd': '1.11'},
      {'value': 'Over 0.5', 'odd': '1.10'},
      {'value': 'Under 0.5', 'odd': '5.40'}]},
    {'id': 17,
     'name': 'Total - Away',
     'values': [{'value': 'Over 1.5', 'odd': '2.70'},
      {'value': 'Under 1.5', 'odd': '1.40'},
      {'value': 'Over 2.5', 'odd': '5.60'},
      {'value': 'Under 2.5', 'odd': '1.09'},
      {'value': 'Over 1', 'odd': '1.73'},
      {'value': 'Under 1', 'odd': '2.00'},
      {'value': 'Over 2', 'odd': '4.70'},
      {'value': 'Under 2', 'odd': '1.13'},
      {'value': 'Over 0.5', 'odd': '1.33'},
      {'value': 'Under 0.5', 'odd': '3.00'}]},
    {'id': 19,
     'name': 'Asian Handicap First Half',
     'values': [{'value': 'Home -1', 'odd': '5.00'},
      {'value': 'Away -1', 'odd': '1.10'},
      {'value': 'Home -0.25', 'odd': '1.90'},
      {'value': 'Away -0.25', 'odd': '1.75'},
      {'value': 'Home +0', 'odd': '1.44'},
      {'value': 'Away +0', 'odd': '2.47'},
      {'value': 'Home +0.25', 'odd': '1.26'},
      {'value': 'Away +0.25', 'odd': '3.28'}]},
    {'id': 20,
     'name': 'Double Chance - First Half',
     'values': [{'value': 'Home/Draw', 'odd': '1.13'},
      {'value': 'Home/Away', 'odd': '1.49'},
      {'value': 'Draw/Away', 'odd': '1.45'}]},
    {'id': 33,
     'name': 'Double Chance - Second Half',
     'values': [{'value': 'Home/Draw', 'odd': '1.18'},
      {'value': 'Home/Away', 'odd': '1.33'},
      {'value': 'Draw/Away', 'odd': '1.56'}]},
    {'id': 34,
     'name': 'Both Teams Score - First Half',
     'values': [{'value': 'Yes', 'odd': '3.58'},
      {'value': 'No', 'odd': '1.23'}]},
    {'id': 35,
     'name': 'Both Teams To Score - Second Half',
     'values': [{'value': 'Yes', 'odd': '2.67'},
      {'value': 'No', 'odd': '1.40'}]},
    {'id': 21,
     'name': 'Odd/Even',
     'values': [{'value': 'Odd', 'odd': '1.85'},
      {'value': 'Even', 'odd': '1.79'}]},
    {'id': 22,
     'name': 'Odd/Even - First Half',
     'values': [{'value': 'Odd', 'odd': '1.99'},
      {'value': 'Even', 'odd': '1.68'}]},
    {'id': 23,
     'name': 'Home Odd/Even',
     'values': [{'value': 'Odd', 'odd': '1.85'},
      {'value': 'Even', 'odd': '1.79'}]},
    {'id': 60,
     'name': 'Away Odd/Even',
     'values': [{'value': 'Odd', 'odd': '1.96'},
      {'value': 'Even', 'odd': '1.70'}]},
    {'id': 104,
     'name': 'Asian Handicap (2nd Half)',
     'values': [{'value': 'Home -1', 'odd': '3.72'},
      {'value': 'Away -1', 'odd': '1.20'},
      {'value': 'Home -0.25', 'odd': '1.77'},
      {'value': 'Away -0.25', 'odd': '1.87'},
      {'value': 'Home +0', 'odd': '1.43'},
      {'value': 'Away +0', 'odd': '2.50'},
      {'value': 'Home +0.25', 'odd': '1.29'},
      {'value': 'Away +0.25', 'odd': '3.08'}]},
    {'id': 105,
     'name': 'Home Team Total Goals(1st Half)',
     'values': [{'value': 'Over 0.5', 'odd': '1.65'},
      {'value': 'Under 0.5', 'odd': '2.03'}]},
    {'id': 106,
     'name': 'Away Team Total Goals(1st Half)',
     'values': [{'value': 'Over 0.5', 'odd': '2.16'},
      {'value': 'Under 0.5', 'odd': '1.57'}]},
    {'id': 107,
     'name': 'Home Team Total Goals(2nd Half)',
     'values': [{'value': 'Over 0.5', 'odd': '1.41'},
      {'value': 'Under 0.5', 'odd': '2.56'}]},
    {'id': 108,
     'name': 'Away Team Total Goals(2nd Half)',
     'values': [{'value': 'Over 0.5', 'odd': '1.81'},
      {'value': 'Under 0.5', 'odd': '1.83'}]},
    {'id': 63,
     'name': 'Odd/Even - Second Half',
     'values': [{'value': 'Odd', 'odd': '1.87'},
      {'value': 'Even', 'odd': '1.77'}]}]},
  {'id': 32,
   'name': 'Betano',
   'bets': [{'id': 1,
     'name': 'Match Winner',
     'values': [{'value': 'Home', 'odd': '1.82'},
      {'value': 'Draw', 'odd': '3.60'},
      {'value': 'Away', 'odd': '3.55'}]},
    {'id': 2,
     'name': 'Home/Away',
     'values': [{'value': 'Home', 'odd': '1.38'},
      {'value': 'Away', 'odd': '2.57'}]},
    {'id': 3,
     'name': 'Second Half Winner',
     'values': [{'value': 'Home', 'odd': '2.12'},
      {'value': 'Draw', 'odd': '2.70'},
      {'value': 'Away', 'odd': '3.50'}]},
    {'id': 4,
     'name': 'Asian Handicap',
     'values': [{'value': 'Home -0.5', 'odd': '1.75'},
      {'value': 'Away -0.5', 'odd': '1.85'}]},
    {'id': 5,
     'name': 'Goals Over/Under',
     'values': [{'value': 'Over 2.5', 'odd': '1.55'},
      {'value': 'Under 2.5', 'odd': '2.15'},
      {'value': 'Over 3.5', 'odd': '2.07'},
      {'value': 'Under 3.5', 'odd': '1.60'},
      {'value': 'Over 3.0', 'odd': '1.87'},
      {'value': 'Under 3.0', 'odd': '1.78'},
      {'value': 'Over 3.25', 'odd': '1.90'},
      {'value': 'Under 3.25', 'odd': '1.75'}]},
    {'id': 6,
     'name': 'Goals Over/Under First Half',
     'values': [{'value': 'Over 1.5', 'odd': '2.18'},
      {'value': 'Under 1.5', 'odd': '1.50'},
      {'value': 'Over 1.25', 'odd': '1.88'},
      {'value': 'Under 1.25', 'odd': '1.67'}]},
    {'id': 7,
     'name': 'HT/FT Double',
     'values': [{'value': 'Home/Draw', 'odd': '13.00'},
      {'value': 'Home/Away', 'odd': '32.00'},
      {'value': 'Draw/Away', 'odd': '8.25'},
      {'value': 'Draw/Draw', 'odd': '5.90'},
      {'value': 'Home/Home', 'odd': '2.82'},
      {'value': 'Draw/Home', 'odd': '4.70'},
      {'value': 'Away/Home', 'odd': '21.00'},
      {'value': 'Away/Draw', 'odd': '14.00'},
      {'value': 'Away/Away', 'odd': '6.10'}]},
    {'id': 11,
     'name': 'Highest Scoring Half',
     'values': [{'value': 'Draw', 'odd': '3.50'},
      {'value': '1st Half', 'odd': '3.00'},
      {'value': '2nd Half', 'odd': '1.87'}]},
    {'id': 31,
     'name': 'Correct Score - First Half',
     'values': [{'value': '1:0', 'odd': '3.20'},
      {'value': '2:0', 'odd': '6.30'},
      {'value': '2:1', 'odd': '9.75'},
      {'value': '3:0', 'odd': '17.00'},
      {'value': '3:1', 'odd': '26.00'},
      {'value': '3:2', 'odd': '65.00'},
      {'value': '4:0', 'odd': '55.00'},
      {'value': '4:1', 'odd': '90.00'},
      {'value': '0:0', 'odd': '2.62'},
      {'value': '1:1', 'odd': '4.90'},
      {'value': '2:2', 'odd': '26.00'},
      {'value': '0:1', 'odd': '4.35'},
      {'value': '0:2', 'odd': '12.00'},
      {'value': '0:3', 'odd': '45.00'},
      {'value': '1:2', 'odd': '14.00'},
      {'value': '1:3', 'odd': '55.00'},
      {'value': '2:3', 'odd': '100.00'},
      {'value': '3:3', 'odd': '250.00'},
      {'value': '0:4', 'odd': '200.00'},
      {'value': '1:4', 'odd': '250.00'},
      {'value': '4:2', 'odd': '250.00'},
      {'value': '5:0', 'odd': '200.00'}]},
    {'id': 12,
     'name': 'Double Chance',
     'values': [{'value': 'Home/Draw', 'odd': '1.24'},
      {'value': 'Home/Away', 'odd': '1.24'},
      {'value': 'Draw/Away', 'odd': '1.80'}]},
    {'id': 13,
     'name': 'First Half Winner',
     'values': [{'value': 'Home', 'odd': '2.32'},
      {'value': 'Draw', 'odd': '2.25'},
      {'value': 'Away', 'odd': '3.90'}]},
    {'id': 19,
     'name': 'Asian Handicap First Half',
     'values': [{'value': 'Home -0.25', 'odd': '1.82'},
      {'value': 'Away -0.25', 'odd': '1.72'}]},
    {'id': 20,
     'name': 'Double Chance - First Half',
     'values': [{'value': 'Home/Draw', 'odd': '1.22'},
      {'value': 'Home/Away', 'odd': '1.50'},
      {'value': 'Draw/Away', 'odd': '1.50'}]},
    {'id': 21,
     'name': 'Odd/Even',
     'values': [{'value': 'Odd', 'odd': '1.83'},
      {'value': 'Even', 'odd': '1.80'}]},
    {'id': 109,
     'name': 'Draw No Bet (1st Half)',
     'values': [{'value': 'Home', 'odd': '1.44'},
      {'value': 'Away', 'odd': '2.35'}]},
    {'id': 182,
     'name': 'Draw No Bet (2nd Half)',
     'values': [{'value': 'Home', 'odd': '1.45'},
      {'value': 'Away', 'odd': '2.35'}]}]}]}
```

Exemplo de código que pode ser usado… Neste código tem filtro por Bookies e Mercados

```markdown
      # limite do free é de 30 requests por minuto, aqui dá um sleep para atender este ponto
      if pagina > 30 and chk == 0:
          time.sleep(30)
          chk = 1
      if pagina > 60 and chk == 1:
          time.sleep(30)
          chk = 2
      if pagina > 90 and chk == 2:
          time.sleep(30)
          chk = 3
      if pagina > 1:
          headers = {
          	"x-rapidapi-key": f"{api}",
          	"x-rapidapi-host": "api-football-v1.p.rapidapi.com"
          }
          
          url = "https://api-football-v1.p.rapidapi.com/v3/odds"
      
          response = requests.get(url, headers=headers, params=query)
          dados = response.json()
      
      try:
          dados = dados['response']
          
          for i in range(len(dados)):
              #Informações da Partida
              fixture_id = dados[i]['fixture']['id']
      
              for j in range(0, len(dados[i]['bookmakers'])):
                  book_id = dados[i]['bookmakers'][j]['id']
                  
                  # Filtro por bookmaker / casa
                  if book_id in book_list:
                      dict_jogo = {}
                      dict_jogo['id'] = fixture_id
                      dict_jogo['book_id'] = book_id
                      dict_jogo['book_name'] = dados[i]['bookmakers'][j]['name']
                      for k in range(0, len(dados[i]['bookmakers'][j]['bets'])):
                          bet_id = dados[i]['bookmakers'][j]['bets'][k]['id']
                          # Match Odds FT
                          if bet_id == 1:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home':
                                      dict_jogo['FTH'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Draw':
                                      dict_jogo['FTD'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away':
                                      dict_jogo['FTA'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Handicap Asiático FT
                          if bet_id == 4:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0':
                                      dict_jogo['AH0_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0':
                                      dict_jogo['AH0_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -0.25':
                                      dict_jogo['AH-025_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -0.25':
                                      dict_jogo['AH+025_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0.25':
                                      dict_jogo['AH+025_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0.25':
                                      dict_jogo['AH-025_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -0.5':
                                      dict_jogo['AH-05_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -0.5':
                                      dict_jogo['AH+05_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0.5':
                                      dict_jogo['AH+05_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0.5':
                                      dict_jogo['AH-05_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -0.75':
                                      dict_jogo['AH-075_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -0.75':
                                      dict_jogo['AH+075_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0.75':
                                      dict_jogo['AH+075_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0.75':
                                      dict_jogo['AH-075_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1':
                                      dict_jogo['AH-1_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1':
                                      dict_jogo['AH+1_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1':
                                      dict_jogo['AH+1_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1':
                                      dict_jogo['AH-1_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1.25':
                                      dict_jogo['AH-125_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1.25':
                                      dict_jogo['AH+125_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1.25':
                                      dict_jogo['AH+125_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1.25':
                                      dict_jogo['AH-125_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1.5':
                                      dict_jogo['AH-15_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1.5':
                                      dict_jogo['AH+15_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1.5':
                                      dict_jogo['AH+15_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1.5':
                                      dict_jogo['AH-15_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1.75':
                                      dict_jogo['AH-175_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1.75':
                                      dict_jogo['AH+175_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1.75':
                                      dict_jogo['AH+175_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1.75':
                                      dict_jogo['AH-175_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2':
                                      dict_jogo['AH-2_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2':
                                      dict_jogo['AH+2_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2':
                                      dict_jogo['AH+2_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2':
                                      dict_jogo['AH-2_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2.25':
                                      dict_jogo['AH-225_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2.25':
                                      dict_jogo['AH+225_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2.25':
                                      dict_jogo['AH+225_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2.25':
                                      dict_jogo['AH-225_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2.5':
                                      dict_jogo['AH-25_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2.5':
                                      dict_jogo['AH+25_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2.5':
                                      dict_jogo['AH+25_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2.5':
                                      dict_jogo['AH-25_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2.75':
                                      dict_jogo['AH-275_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2.75':
                                      dict_jogo['AH+275_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2.75':
                                      dict_jogo['AH+275_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2.75':
                                      dict_jogo['AH-275_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3':
                                      dict_jogo['AH-3_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3':
                                      dict_jogo['AH+3_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3':
                                      dict_jogo['AH+3_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3':
                                      dict_jogo['AH-3_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3.25':
                                      dict_jogo['AH-325_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3.25':
                                      dict_jogo['AH+325_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3.25':
                                      dict_jogo['AH+325_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3.25':
                                      dict_jogo['AH-325_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3.5':
                                      dict_jogo['AH-35_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3.5':
                                      dict_jogo['AH+35_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3.5':
                                      dict_jogo['AH+35_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3.5':
                                      dict_jogo['AH-35_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3.75':
                                      dict_jogo['AH-375_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3.75':
                                      dict_jogo['AH+375_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3.75':
                                      dict_jogo['AH+375_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3.75':
                                      dict_jogo['AH-375_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -4':
                                      dict_jogo['AH-4_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -4':
                                      dict_jogo['AH+4_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +4':
                                      dict_jogo['AH+4_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +4':
                                      dict_jogo['AH-4_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -4.25':
                                      dict_jogo['AH-425_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -4.25':
                                      dict_jogo['AH+425_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +4.25':
                                      dict_jogo['AH+425_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +4.25':
                                      dict_jogo['AH-425_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -4.5':
                                      dict_jogo['AH-45_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -4.5':
                                      dict_jogo['AH+45_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +4.5':
                                      dict_jogo['AH+45_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +4.5':
                                      dict_jogo['AH-45_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -4.75':
                                      dict_jogo['AH-475_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -4.75':
                                      dict_jogo['AH+475_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +4.75':
                                      dict_jogo['AH+475_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +4.75':
                                      dict_jogo['AH-475_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -5':
                                      dict_jogo['AH-5_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -5':
                                      dict_jogo['AH+5_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +5':
                                      dict_jogo['AH+5_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +5':
                                      dict_jogo['AH-5_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -5.25':
                                      dict_jogo['AH-525_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -5.25':
                                      dict_jogo['AH+525_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +5.25':
                                      dict_jogo['AH+525_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +5.25':
                                      dict_jogo['AH-525_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -5.5':
                                      dict_jogo['AH-55_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -5.5':
                                      dict_jogo['AH+55_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +5.5':
                                      dict_jogo['AH+55_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +5.5':
                                      dict_jogo['AH-55_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -5.75':
                                      dict_jogo['AH-575_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -5.75':
                                      dict_jogo['AH+575_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +5.75':
                                      dict_jogo['AH+575_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +5.75':
                                      dict_jogo['AH-575_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -6':
                                      dict_jogo['AH-6_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -6':
                                      dict_jogo['AH+6_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +6':
                                      dict_jogo['AH+6_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +6':
                                      dict_jogo['AH-6_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Over/Under FT
                          if bet_id == 5:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 0.5':
                                      dict_jogo['Ov05FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 0.5':
                                      dict_jogo['Un05FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1.0':
                                      dict_jogo['Ov10FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1.0':
                                      dict_jogo['Un10FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1.5':
                                      dict_jogo['Ov15FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1.5':
                                      dict_jogo['Un15FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.0':
                                      dict_jogo['Ov20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.0':
                                      dict_jogo['Un20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.5':
                                      dict_jogo['Ov25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.5':
                                      dict_jogo['Un25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.0':
                                      dict_jogo['Ov30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.0':
                                      dict_jogo['Un30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.5':
                                      dict_jogo['Ov35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.5':
                                      dict_jogo['Un35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.0':
                                      dict_jogo['Ov40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.0':
                                      dict_jogo['Un40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.5':
                                      dict_jogo['Ov45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.5':
                                      dict_jogo['Un45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.0':
                                      dict_jogo['Ov50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.0':
                                      dict_jogo['Un50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.5':
                                      dict_jogo['Ov55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.5':
                                      dict_jogo['Un55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6.0':
                                      dict_jogo['Ov60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6.0':
                                      dict_jogo['Un60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6.5':
                                      dict_jogo['Ov65FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6.5':
                                      dict_jogo['Un65FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7.0':
                                      dict_jogo['Ov70FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7.0':
                                      dict_jogo['Un70FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7.5':
                                      dict_jogo['Ov75FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7.5':
                                      dict_jogo['Un75FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8.0':
                                      dict_jogo['Ov80FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8.0':
                                      dict_jogo['Un80FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8.5':
                                      dict_jogo['Ov85FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8.5':
                                      dict_jogo['Un85FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9.0':
                                      dict_jogo['Ov90FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9.0':
                                      dict_jogo['Un90FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9.5':
                                      dict_jogo['Ov95FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9.5':
                                      dict_jogo['Un95FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Over/Under HT
                          if bet_id == 6:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 0.5':
                                      dict_jogo['Ov05HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 0.5':
                                      dict_jogo['Un05HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1.0':
                                      dict_jogo['Ov10FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1.0':
                                      dict_jogo['Un10FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1.5':
                                      dict_jogo['Ov15HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1.5':
                                      dict_jogo['Un15HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.0':
                                      dict_jogo['Ov20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.0':
                                      dict_jogo['Un20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.5':
                                      dict_jogo['Ov25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.5':
                                      dict_jogo['Un25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.0':
                                      dict_jogo['Ov30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.0':
                                      dict_jogo['Un30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.5':
                                      dict_jogo['Ov35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.5':
                                      dict_jogo['Un35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.0':
                                      dict_jogo['Ov40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.0':
                                      dict_jogo['Un40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.5':
                                      dict_jogo['Ov45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.5':
                                      dict_jogo['Un45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.0':
                                      dict_jogo['Ov50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.0':
                                      dict_jogo['Un50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.5':
                                      dict_jogo['Ov55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.5':
                                      dict_jogo['Un55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6.0':
                                      dict_jogo['Ov60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6.0':
                                      dict_jogo['Un60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Ambas Marcam
                          if bet_id == 8:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Yes':
                                      dict_jogo['BTTSY'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'No':
                                      dict_jogo['BTTSN'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Dupla Chance
                          if bet_id == 12:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home/Draw':
                                      dict_jogo['1X'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home/Away':
                                      dict_jogo['12'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Draw/Away':
                                      dict_jogo['X2'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Resultado HT
                          if bet_id == 13:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home':
                                      dict_jogo['HTH'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Draw':
                                      dict_jogo['HTD'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away':
                                      dict_jogo['HTA'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Placar Correto FT
                          if bet_id == 10:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:0':
                                      dict_jogo['1x0'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:0':
                                      dict_jogo['2x0'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:1':
                                      dict_jogo['2x1'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:0':
                                      dict_jogo['3x0'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:1':
                                      dict_jogo['3x1'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:2':
                                      dict_jogo['3x2'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '4:0':
                                      dict_jogo['4x0'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '4:1':
                                      dict_jogo['4x1'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '4:2':
                                      dict_jogo['4x2'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '4:3':
                                      dict_jogo['4x3'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '5:0':
                                      dict_jogo['5x0'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '5:1':
                                      dict_jogo['5x1'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '5:2':
                                      dict_jogo['5x2'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '5:3':
                                      dict_jogo['5x3'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '5:4':
                                      dict_jogo['5x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:0':
                                      dict_jogo['0x0'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:1':
                                      dict_jogo['1x1'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:2':
                                      dict_jogo['2x2'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:3':
                                      dict_jogo['3x3'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '4:4':
                                      dict_jogo['4x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '5:5':
                                      dict_jogo['5x5'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:1':
                                      dict_jogo['0x1'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:2':
                                      dict_jogo['0x2'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:3':
                                      dict_jogo['0x3'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:4':
                                      dict_jogo['0x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:5':
                                      dict_jogo['0x5'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:2':
                                      dict_jogo['1x2'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:3':
                                      dict_jogo['1x3'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:4':
                                      dict_jogo['1x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:5':
                                      dict_jogo['1x5'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:3':
                                      dict_jogo['2x3'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:4':
                                      dict_jogo['2x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:5':
                                      dict_jogo['2x5'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:4':
                                      dict_jogo['3x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:5':
                                      dict_jogo['3x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '4:5':
                                      dict_jogo['3x4'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                      # Placar Correto HT
                          if bet_id == 31:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:0':
                                      dict_jogo['1x0HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:0':
                                      dict_jogo['2x0HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:1':
                                      dict_jogo['2x1HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:0':
                                      dict_jogo['3x0HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:1':
                                      dict_jogo['3x1HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:2':
                                      dict_jogo['3x2HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:0':
                                      dict_jogo['0x0HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:1':
                                      dict_jogo['1x1HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:2':
                                      dict_jogo['2x2HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '3:3':
                                      dict_jogo['3x3HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:1':
                                      dict_jogo['0x1HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:2':
                                      dict_jogo['0x2HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '0:3':
                                      dict_jogo['0x3HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:2':
                                      dict_jogo['1x2HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '1:3':
                                      dict_jogo['1x3HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == '2:3':
                                      dict_jogo['2x3HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Corners 1x2
                          if bet_id == 55:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home':
                                      dict_jogo['C_1x2H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Draw':
                                      dict_jogo['C_1x2D'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away':
                                      dict_jogo['C_1x2A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Corners Handicap Asiático
                          if bet_id == 56:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0':
                                      dict_jogo['C_AH0_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0':
                                      dict_jogo['C_AH0_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -0.5':
                                      dict_jogo['C_AH-05H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -0.5':
                                      dict_jogo['C_AH+05A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0.5':
                                      dict_jogo['C_AH+05_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0.5':
                                      dict_jogo['C_AH-05_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1':
                                      dict_jogo['C_AH-10H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1':
                                      dict_jogo['C_AH+10A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1':
                                      dict_jogo['C_AH+10H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1':
                                      dict_jogo['C_AH-10A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1.5':
                                      dict_jogo['C_AH-15H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1.5':
                                      dict_jogo['C_AH+15A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1.5':
                                      dict_jogo['C_AH+15H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1.5':
                                      dict_jogo['C_AH-15A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2':
                                      dict_jogo['C_AH-20H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2':
                                      dict_jogo['C_AH+20A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2':
                                      dict_jogo['C_AH+20H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2':
                                      dict_jogo['C_AH-20A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2.5':
                                      dict_jogo['C_AH-25H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2.5':
                                      dict_jogo['C_AH+25A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2.5':
                                      dict_jogo['C_AH+25H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2.5':
                                      dict_jogo['C_AH-25A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3':
                                      dict_jogo['C_AH-30H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3':
                                      dict_jogo['C_AH+30A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3':
                                      dict_jogo['C_AH+30H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3':
                                      dict_jogo['C_AH-30A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3.5':
                                      dict_jogo['C_AH-35H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3.5':
                                      dict_jogo['C_AH+35A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3.5':
                                      dict_jogo['C_AH+35H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3.5':
                                      dict_jogo['C_AH-35A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -4':
                                      dict_jogo['C_AH-40H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -4':
                                      dict_jogo['C_AH+40A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +4':
                                      dict_jogo['C_AH+40H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +4':
                                      dict_jogo['C_AH-40A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -4.5':
                                      dict_jogo['C_AH-45H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -4.5':
                                      dict_jogo['C_AH+45A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +4.5':
                                      dict_jogo['C_AH+45H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +4.5':
                                      dict_jogo['C_AH-45A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -5':
                                      dict_jogo['C_AH-50H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -5':
                                      dict_jogo['C_AH+50A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +5':
                                      dict_jogo['C_AH+50H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +5':
                                      dict_jogo['C_AH-50A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -5.5':
                                      dict_jogo['C_AH-55H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -5.5':
                                      dict_jogo['C_AH+55A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +5.5':
                                      dict_jogo['C_AH+55H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +5.5':
                                      dict_jogo['C_AH-55A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Corners Over/Under
                          if bet_id == 45:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2':
                                      dict_jogo['C_Ov20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2':
                                      dict_jogo['C_Un20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.5':
                                      dict_jogo['C_Ov25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.5':
                                      dict_jogo['C_Un25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3':
                                      dict_jogo['C_Ov30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3':
                                      dict_jogo['C_Un30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.5':
                                      dict_jogo['C_Ov35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.5':
                                      dict_jogo['C_Un35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4':
                                      dict_jogo['C_Ov40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4':
                                      dict_jogo['C_Un40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.5':
                                      dict_jogo['C_Ov45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.5':
                                      dict_jogo['C_Un45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5':
                                      dict_jogo['C_Ov50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5':
                                      dict_jogo['C_Un50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.5':
                                      dict_jogo['C_Ov55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.5':
                                      dict_jogo['C_Un55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6':
                                      dict_jogo['C_Ov60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6':
                                      dict_jogo['C_Un60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6.5':
                                      dict_jogo['C_Ov65FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6.5':
                                      dict_jogo['C_Un65FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7':
                                      dict_jogo['C_Ov70FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7':
                                      dict_jogo['C_Un70FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7.5':
                                      dict_jogo['C_Ov75FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7.5':
                                      dict_jogo['C_Un75FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8':
                                      dict_jogo['C_Ov80FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8':
                                      dict_jogo['C_Un80FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8.5':
                                      dict_jogo['C_Ov85FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8.5':
                                      dict_jogo['C_Un85FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9':
                                      dict_jogo['C_Ov90FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9':
                                      dict_jogo['C_Un90FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9.5':
                                      dict_jogo['C_Ov95FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9.5':
                                      dict_jogo['C_Un95FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 10':
                                      dict_jogo['C_Ov100FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 10':
                                      dict_jogo['C_Un100FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 10.5':
                                      dict_jogo['C_Ov105FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 10.5':
                                      dict_jogo['C_Un105FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 11':
                                      dict_jogo['C_Ov110FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 11':
                                      dict_jogo['C_Un110FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 11.5':
                                      dict_jogo['C_Ov115FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 11.5':
                                      dict_jogo['C_Un115FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 12':
                                      dict_jogo['C_Ov120FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 12':
                                      dict_jogo['C_Un120FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 12.5':
                                      dict_jogo['C_Ov125FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 12.5':
                                      dict_jogo['C_Un125FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 13':
                                      dict_jogo['C_Ov130FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 13':
                                      dict_jogo['C_Un130FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 13.5':
                                      dict_jogo['C_Ov135FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 13.5':
                                      dict_jogo['C_Un135FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 14':
                                      dict_jogo['C_Ov140FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 14':
                                      dict_jogo['C_Un140FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 14.5':
                                      dict_jogo['C_Ov145FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 14.5':
                                      dict_jogo['C_Un145FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Corners Total - 3 Opções FT
                          if bet_id == 85:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2':
                                      dict_jogo['C_3Ov2FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2':
                                      dict_jogo['C_3Un2FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 2':
                                      dict_jogo['C_3Ex2FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3':
                                      dict_jogo['C_3Ov3FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3':
                                      dict_jogo['C_3Un3FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 3':
                                      dict_jogo['C_3Ex3FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4':
                                      dict_jogo['C_3Ov4FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4':
                                      dict_jogo['C_3Un4FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 4':
                                      dict_jogo['C_3Ex4FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5':
                                      dict_jogo['C_3Ov5FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5':
                                      dict_jogo['C_3Un5FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 5':
                                      dict_jogo['C_3Ex5FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6':
                                      dict_jogo['C_3Ov6FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6':
                                      dict_jogo['C_3Un6FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 6':
                                      dict_jogo['C_3Ex6FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7':
                                      dict_jogo['C_3Ov7FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7':
                                      dict_jogo['C_3Un7FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 7':
                                      dict_jogo['C_3Ex7FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8':
                                      dict_jogo['C_3Ov8FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8':
                                      dict_jogo['C_3Un8FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 8':
                                      dict_jogo['C_3Ex8FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9':
                                      dict_jogo['C_3Ov9FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9':
                                      dict_jogo['C_3Un9FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 9':
                                      dict_jogo['C_3Ex9FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 10':
                                      dict_jogo['C_3Ov10FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 10':
                                      dict_jogo['C_3Un10FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 10':
                                      dict_jogo['C_3Ex10FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 11':
                                      dict_jogo['C_3Ov11FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 11':
                                      dict_jogo['C_3Un11FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 11':
                                      dict_jogo['C_3Ex11FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 12':
                                      dict_jogo['C_3Ov12FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 12':
                                      dict_jogo['C_3Un12FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 12':
                                      dict_jogo['C_3Ex12FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 13':
                                      dict_jogo['C_3Ov13FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 13':
                                      dict_jogo['C_3Un13FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 13':
                                      dict_jogo['C_3Ex13FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 14':
                                      dict_jogo['C_3Ov14FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 14':
                                      dict_jogo['C_3Un14FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 14':
                                      dict_jogo['C_3Ex14FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 15':
                                      dict_jogo['C_3Ov15FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 15':
                                      dict_jogo['C_3Un15FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 15':
                                      dict_jogo['C_3Ex15FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 16':
                                      dict_jogo['C_3Ov16FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 16':
                                      dict_jogo['C_3Un16FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 16':
                                      dict_jogo['C_3Ex16FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 17':
                                      dict_jogo['C_3Ov17FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 17':
                                      dict_jogo['C_3Un17FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 17':
                                      dict_jogo['C_3Ex17FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 18':
                                      dict_jogo['C_3Ov18FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 18':
                                      dict_jogo['C_3Un18FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 18':
                                      dict_jogo['C_3Ex18FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 19':
                                      dict_jogo['C_3Ov19FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 19':
                                      dict_jogo['C_3Un19FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 19':
                                      dict_jogo['C_3Ex19FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Corners Over/Under HT
                          if bet_id == 77:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1':
                                      dict_jogo['C_Ov10HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1':
                                      dict_jogo['C_Un10HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1.5':
                                      dict_jogo['C_Ov15HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1.5':
                                      dict_jogo['C_Un15HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2':
                                      dict_jogo['C_Ov20HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2':
                                      dict_jogo['C_Un20HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.5':
                                      dict_jogo['C_Ov25HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.5':
                                      dict_jogo['C_Un25HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3':
                                      dict_jogo['C_Ov30HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3':
                                      dict_jogo['C_Un30HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.5':
                                      dict_jogo['C_Ov35HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.5':
                                      dict_jogo['C_Un35HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4':
                                      dict_jogo['C_Ov40HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4':
                                      dict_jogo['C_Un40HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.5':
                                      dict_jogo['C_Ov45HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.5':
                                      dict_jogo['C_Un45HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5':
                                      dict_jogo['C_Ov50HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5':
                                      dict_jogo['C_Un50HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.5':
                                      dict_jogo['C_Ov55HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.5':
                                      dict_jogo['C_Un55HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6':
                                      dict_jogo['C_Ov60HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6':
                                      dict_jogo['C_Un60HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6.5':
                                      dict_jogo['C_Ov65HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6.5':
                                      dict_jogo['C_Un65HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7':
                                      dict_jogo['C_Ov70HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7':
                                      dict_jogo['C_Un70HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7.5':
                                      dict_jogo['C_Ov75HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7.5':
                                      dict_jogo['C_Un75HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8':
                                      dict_jogo['C_Ov80HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8':
                                      dict_jogo['C_Un80HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8.5':
                                      dict_jogo['C_Ov85HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8.5':
                                      dict_jogo['C_Un85HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9':
                                      dict_jogo['C_Ov90HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9':
                                      dict_jogo['C_Un90HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9.5':
                                      dict_jogo['C_Ov95HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9.5':
                                      dict_jogo['C_Un95HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Corners Total - 3 Opções HT
                          if bet_id == 85:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1':
                                      dict_jogo['C_3Ov1HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1':
                                      dict_jogo['C_3Un1HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 1':
                                      dict_jogo['C_3Ex1HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2':
                                      dict_jogo['C_3Ov2HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2':
                                      dict_jogo['C_3Un2HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 2':
                                      dict_jogo['C_3Ex2HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3':
                                      dict_jogo['C_3Ov3HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3':
                                      dict_jogo['C_3Un3HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 3':
                                      dict_jogo['C_3Ex3HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4':
                                      dict_jogo['C_3Ov4HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4':
                                      dict_jogo['C_3Un4HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 4':
                                      dict_jogo['C_3Ex4HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5':
                                      dict_jogo['C_3Ov5HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5':
                                      dict_jogo['C_3Un5HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 5':
                                      dict_jogo['C_3Ex5HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6':
                                      dict_jogo['C_3Ov6HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6':
                                      dict_jogo['C_3Un6HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 6':
                                      dict_jogo['C_3Ex6HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7':
                                      dict_jogo['C_3Ov7HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7':
                                      dict_jogo['C_3Un7HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 7':
                                      dict_jogo['C_3Ex7HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8':
                                      dict_jogo['C_3Ov8HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8':
                                      dict_jogo['C_3Un8HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 8':
                                      dict_jogo['C_3Ex8HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9':
                                      dict_jogo['C_3Ov9HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9':
                                      dict_jogo['C_3Un9HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 9':
                                      dict_jogo['C_3Ex9HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 10':
                                      dict_jogo['C_3Ov10HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 10':
                                      dict_jogo['C_3Un10HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Exactly 10':
                                      dict_jogo['C_3Ex10HT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Cartões Over/Under FT
                          if bet_id == 80:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 1.5':
                                      dict_jogo['CA_Ov15FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 1.5':
                                      dict_jogo['CA_Un15FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.0':
                                      dict_jogo['CA_Ov20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.0':
                                      dict_jogo['CA_Un20FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 2.5':
                                      dict_jogo['CA_Ov25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 2.5':
                                      dict_jogo['CA_Un25FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.0':
                                      dict_jogo['CA_Ov30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.0':
                                      dict_jogo['CA_Un30FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 3.5':
                                      dict_jogo['CA_Ov35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 3.5':
                                      dict_jogo['CA_Un35FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.0':
                                      dict_jogo['CA_Ov40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.0':
                                      dict_jogo['CA_Un40FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 4.5':
                                      dict_jogo['CA_Ov45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 4.5':
                                      dict_jogo['CA_Un45FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.0':
                                      dict_jogo['CA_Ov50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.0':
                                      dict_jogo['CA_Un50FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 5.5':
                                      dict_jogo['CA_Ov55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 5.5':
                                      dict_jogo['CA_Un55FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6.0':
                                      dict_jogo['CA_Ov60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6.0':
                                      dict_jogo['CA_Un60FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 6.5':
                                      dict_jogo['CA_Ov65FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 6.5':
                                      dict_jogo['CA_Un65FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7.0':
                                      dict_jogo['CA_Ov70FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7.0':
                                      dict_jogo['CA_Un70FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 7.5':
                                      dict_jogo['CA_Ov75FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 7.5':
                                      dict_jogo['CA_Un75FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8.0':
                                      dict_jogo['CA_Ov80FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8.0':
                                      dict_jogo['CA_Un80FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 8.5':
                                      dict_jogo['CA_Ov85FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 8.5':
                                      dict_jogo['CA_Un85FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9.0':
                                      dict_jogo['CA_Ov90FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9.0':
                                      dict_jogo['CA_Un90FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 9.5':
                                      dict_jogo['CA_Ov95FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 9.5':
                                      dict_jogo['CA_Un95FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 10.0':
                                      dict_jogo['CA_Ov100FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 10.0':
                                      dict_jogo['CA_Un100FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Over 10.5':
                                      dict_jogo['CA_Ov105FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Under 10.5':
                                      dict_jogo['CA_Un105FT'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                          # Cartões Handicap Asiática
                          if bet_id == 81:
                              for l in range(0, len(dados[i]['bookmakers'][j]['bets'][k]['values'])):
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0':
                                      dict_jogo['CA_AH+0H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0':
                                      dict_jogo['CA_AH+0A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -0.5':
                                      dict_jogo['CA_AH-05H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -0.5':
                                      dict_jogo['CA_AH+05A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +0.5':
                                      dict_jogo['CA_AH+05_H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +0.5':
                                      dict_jogo['CA_AH-05_A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1':
                                      dict_jogo['CA_AH-10H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1':
                                      dict_jogo['CA_AH+10A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1':
                                      dict_jogo['CA_AH+10H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1':
                                      dict_jogo['CA_AH-10A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -1.5':
                                      dict_jogo['CA_AH-15H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -1.5':
                                      dict_jogo['CA_AH+15A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +1.5':
                                      dict_jogo['CA_AH+15H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +1.5':
                                      dict_jogo['CA_AH-15A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2':
                                      dict_jogo['CA_AH-20H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2':
                                      dict_jogo['CA_AH+20A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2':
                                      dict_jogo['CA_AH+20H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2':
                                      dict_jogo['CA_AH-20A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -2.5':
                                      dict_jogo['CA_AH-25H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -2.5':
                                      dict_jogo['CA_AH+25A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +2.5':
                                      dict_jogo['CA_AH+25H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +2.5':
                                      dict_jogo['CA_AH-25A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3':
                                      dict_jogo['CA_AH-30H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3':
                                      dict_jogo['CA_AH+30A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3':
                                      dict_jogo['CA_AH+30H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3':
                                      dict_jogo['CA_AH-30A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home -3.5':
                                      dict_jogo['CA_AH-35H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away -3.5':
                                      dict_jogo['CA_AH+35A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Home +3.5':
                                      dict_jogo['CA_AH+35H'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                                  if dados[i]['bookmakers'][j]['bets'][k]['values'][l]['value'] == 'Away +3.5':
                                      dict_jogo['CA_AH-35A'] = dados[i]['bookmakers'][j]['bets'][k]['values'][l]['odd']
                      lista_odds.append(dict_jogo)
          print('Página', pagina, 'de', paginas, 'páginas processadas.')
      except:
          print('Página', pagina, 'com erro, de', paginas, 'páginas processadas.')

df_odds = pd.DataFrame(lista_odds)
```