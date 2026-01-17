import requests
import pandas as pd
import os
from pathlib import Path

# TU API KEY
API_KEY = '86acc56b2b32372283ef6764b9a39d26' 

# Configuración
SPORT = 'soccer_spain_la_liga'
REGIONS = 'eu'
MARKETS = 'h2h'
ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'

CARPETA_CSV = Path("csv/csvGenerados/apuestas")
CARPETA_CSV.mkdir(parents=True, exist_ok=True)
ARCHIVO_CSV = CARPETA_CSV / "odds_pinnacle_laliga.csv"

def get_upcoming_odds():
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {
        'api_key': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': ODDS_FORMAT,
        'dateFormat': DATE_FORMAT,
    }

    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f'❌ Error {response.status_code}: {response.text}')
        return None

    data = response.json()
    
    # Procesar JSON: solo Pinnacle, nombres raw
    matches = []
    for match in data:
        home_team = match['home_team']
        away_team = match['away_team']
        
        odds_home = None
        odds_draw = None
        odds_away = None
        
        # Solo Pinnacle
        for bookmaker in match['bookmakers']:
            if bookmaker['key'] == 'pinnacle':
                for market in bookmaker['markets']:
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            if outcome['name'] == home_team:
                                odds_home = outcome['price']
                            elif outcome['name'] == away_team:
                                odds_away = outcome['price']
                            elif outcome['name'] == 'Draw':
                                odds_draw = outcome['price']
                        break
                break
        
        # Solo si tenemos las 3 cuotas
        if all([odds_home, odds_draw, odds_away]):
            matches.append({
                'HomeTeam': home_team,
                'AwayTeam': away_team,
                'B365H': odds_home,  # Compatible con tu modelo
                'B365D': odds_draw,
                'B365A': odds_away
            })
    
    df = pd.DataFrame(matches)
    df.to_csv(ARCHIVO_CSV, index=False)
    print(f"✅ CSV guardado: {ARCHIVO_CSV}")
    print(df)
    return df

if __name__ == "__main__":
    df_futuro = get_upcoming_odds()
