# scrapping/odds_live.py
import os
import requests
import pandas as pd
from pathlib import Path
from scrapping.commons import normalizar_equipo

BASE_URL = "https://api.the-odds-api.com/v4/sports/soccer_spain_la_liga/odds"
DEFAULT_CSV = "live_odds_cache.csv"

def _get_api_key(explicit_key: str | None = None) -> str:
    key = explicit_key or os.getenv("THE_ODDS_API_KEY")
    if not key:
        raise RuntimeError("Falta THE_ODDS_API_KEY en entorno o parámetro.")
    return key

def fetch_live_odds(api_key: str | None = None, markets=("h2h", "totals")):
    key = _get_api_key(api_key)
    params = {
        "apiKey": key,
        "regions": "eu",
        "markets": ",".join(markets),
        "oddsFormat": "decimal",
    }
    r = requests.get(BASE_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def _safe_prob_from_prices(home, draw, away):
    inv_h, inv_d, inv_a = 1.0 / home, 1.0 / draw, 1.0 / away
    s = inv_h + inv_d + inv_a
    return inv_h / s, inv_d / s, inv_a / s

def _extract_h2h_probs(event):
    bm = event["bookmakers"][0]
    h2h = next(m for m in bm["markets"] if m["key"] == "h2h")
    prices = {o["name"].lower(): o["price"] for o in h2h["outcomes"]}
    home_price = prices.get("home")
    draw_price = prices.get("draw")
    away_price = prices.get("away")
    if not (home_price and draw_price and away_price):
        raise ValueError("Faltan cuotas Home/Draw/Away en H2H.")
    return _safe_prob_from_prices(home_price, draw_price, away_price)

def _extract_over25_prob(event):
    bm = event["bookmakers"][0]
    totals = [m for m in bm["markets"] if m["key"] == "totals"]
    for m in totals:
        for o in m["outcomes"]:
            try:
                pt = float(o.get("point", 0))
            except Exception:
                continue
            if o.get("name") == "Over" and abs(pt - 2.5) < 1e-6:
                over_price = o["price"]
                inv_over = 1.0 / over_price
                inv_under = inv_over  # aproximación simétrica
                s = inv_over + inv_under
                return inv_over / s
    return None

def live_odds_to_row(event, jornada: int | None = None):
    home_raw = event["home_team"]
    away_raw = event["away_team"]
    home = normalizar_equipo(home_raw)
    away = normalizar_equipo(away_raw)

    p_home, p_draw, p_away = _extract_h2h_probs(event)
    p_over25 = _extract_over25_prob(event)
    ah_line = None

    return {
        "jornada": jornada,
        "home": home,
        "away": away,
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "p_over25": p_over25,
        "ah_line": ah_line,
    }

def build_live_odds_map_from_api(jornada: int | None = None, api_key: str | None = None):
    data = fetch_live_odds(api_key)
    rows = [live_odds_to_row(ev, jornada=jornada) for ev in data]
    df = pd.DataFrame(rows)
    csv_path = Path(DEFAULT_CSV)
    df.to_csv(csv_path, index=False)
    odds_map = {}
    for _, r in df.iterrows():
        key = f"{r['home']}-{r['away']}"
        odds_map[key] = {
            "p_home": float(r["p_home"]),
            "p_draw": float(r["p_draw"]),
            "p_away": float(r["p_away"]),
            "p_over25": float(r["p_over25"]) if not pd.isna(r["p_over25"]) else None,
            "ah_line": r["ah_line"],
        }
    return odds_map

def build_live_odds_map_from_csv(csv_path: str | None = None):
    path = Path(csv_path or DEFAULT_CSV)
    if not path.exists():
        raise FileNotFoundError(f"No existe cache de odds: {path}")
    df = pd.read_csv(path)
    odds_map = {}
    for _, r in df.iterrows():
        key = f"{r['home']}-{r['away']}"
        odds_map[key] = {
            "p_home": float(r["p_home"]),
            "p_draw": float(r["p_draw"]),
            "p_away": float(r["p_away"]),
            "p_over25": float(r["p_over25"]) if not pd.isna(r["p_over25"]) else None,
            "ah_line": r["ah_line"],
        }
    return odds_map
