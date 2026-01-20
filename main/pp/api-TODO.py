import requests
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import time

# The Odds API
ODDS_API_KEY = '86acc56b2b32372283ef6764b9a39d26'
SPORT = 'soccer_spain_la_liga'
REGIONS = 'eu'
MARKETS = 'h2h'
ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'

# Football-Data.org
FOOTBALL_DATA_TOKEN = '1549bd940d124507bdd5fa1187e769c3'

CARPETA_JSON = Path("csv/csvGenerados/apuestas")
CARPETA_JSON.mkdir(parents=True, exist_ok=True)
ARCHIVO_JSON = CARPETA_JSON / "odds_laliga_jornadas.json"

def get_matchday_dates(matchday=19):
    """Obtiene las fechas de inicio/fin de una jornada usando football-data.org"""
    headers = {'X-Auth-Token': FOOTBALL_DATA_TOKEN}
    url = 'https://api.football-data.org/v4/competitions/PD/matches'
    params = {'matchday': matchday}
    
    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        print(f'❌ Error football-data jornada {matchday}: {response.status_code}')
        return None, None
    
    matches = response.json().get('matches', [])
    if not matches:
        print(f'❌ No matches found for matchday {matchday}')
        return None, None
    
    dates = [m['utcDate'] for m in matches]
    date_from = min(dates)
    date_to = max(dates)
    
    print(f"📅 Jornada {matchday}: {date_from} to {date_to}")
    return date_from, date_to

def get_odds_by_matchday(matchday=20):
    """Obtiene odds de The Odds API para una jornada específica"""
    
    date_from, date_to = get_matchday_dates(matchday)
    if not date_from or not date_to:
        return None
    
    url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds'
    params = {
        'api_key': ODDS_API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': ODDS_FORMAT,
        'dateFormat': DATE_FORMAT,
        'commenceTimeFrom': date_from,
        'commenceTimeTo': date_to,
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f'❌ Error The Odds API {response.status_code}: {response.text}')
        return None
    
    data = response.json()
    print(f"📊 Jornada {matchday}: Found {len(data)} matches")
    
    # CAMBIO: Parsear PRIMER bookmaker disponible (no solo Pinnacle)
    matches = []
    for match in data:
        home_team = match['home_team']
        away_team = match['away_team']
        
        odds_home = None
        odds_draw = None
        odds_away = None
        bookmaker_used = None
        
        # Tomar PRIMER bookmaker con H2H
        for bookmaker in match['bookmakers']:
            for market in bookmaker['markets']:
                if market['key'] == 'h2h':
                    for outcome in market['outcomes']:
                        if outcome['name'] == home_team:
                            odds_home = outcome['price']
                        elif outcome['name'] == away_team:
                            odds_away = outcome['price']
                        elif outcome['name'] == 'Draw':
                            odds_draw = outcome['price']
                    bookmaker_used = bookmaker['key']
                    break
            # Si encontramos H2H, salimos
            if odds_home and odds_draw and odds_away:
                break
        
        # Solo si tenemos las 3 cuotas
        if all([odds_home, odds_draw, odds_away]):
            matches.append({
                'HomeTeam': home_team,
                'AwayTeam': away_team,
                'B365H': odds_home,
                'B365D': odds_draw,
                'B365A': odds_away,
                'Bookmaker': bookmaker_used
            })
    
    if matches:
        print(f"✅ Jornada {matchday}: {len(matches)} matches")
        return matches
    else:
        print(f"⚠️  Jornada {matchday}: No matches with available odds")
        return None

def scrape_all_matchdays(from_matchday=21, to_matchday=38):
    """Scraper de todas las jornadas y guarda en JSON"""
    
    all_odds = {}
    successful = 0
    failed = 0
    
    print(f"\n🚀 Iniciando scraping jornadas {from_matchday} a {to_matchday}...\n")
    
    for matchday in range(from_matchday, to_matchday + 1):
        print(f"⏳ Procesando jornada {matchday}/{to_matchday}...")
        
        odds = get_odds_by_matchday(matchday)
        
        if odds:
            all_odds[str(matchday)] = {
                'matchday': matchday,
                'timestamp': datetime.now().isoformat(),
                'matches': odds
            }
            successful += 1
        else:
            all_odds[str(matchday)] = {
                'matchday': matchday,
                'timestamp': datetime.now().isoformat(),
                'matches': [],
                'status': 'NO_DATA'
            }
            failed += 1
        
        time.sleep(0.5)
    
    with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_odds, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"✅ JSON guardado: {ARCHIVO_JSON}")
    print(f"📊 Resumen:")
    print(f"   - Jornadas con datos: {successful}")
    print(f"   - Jornadas sin datos: {failed}")
    total_matches = sum(len(all_odds[j]['matches']) for j in all_odds)
    print(f"   - Total partidos: {total_matches}")
    print(f"{'='*60}\n")
    
    return all_odds

def load_odds_json():
    """Carga el JSON de odds guardado"""
    if ARCHIVO_JSON.exists():
        with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

if __name__ == "__main__":
    # Scraper jornadas 21 a 38
    all_odds = scrape_all_matchdays(from_matchday=21, to_matchday=23)
    
    # Mostrar ejemplo
    print("📋 Ejemplo jornada 21:")
    if all_odds.get('21', {}).get('matches'):
        print(json.dumps(all_odds['21']['matches'][:1], indent=2, ensure_ascii=False))
