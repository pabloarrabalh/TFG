# scrapping/odds_live.py
import os
import json
import requests
import pandas as pd
from pathlib import Path
from .commons import normalizar_equipo

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


def _extract_h2h_probs(event: dict):
    # primer bookmaker
    bm = event["bookmakers"][0]
    h2h = next(m for m in bm["markets"] if m["key"] == "h2h")

    prices = {}
    for o in h2h["outcomes"]:
        name = o["name"]
        if name == "Draw":
            prices["draw"] = o["price"]
        elif name == event["home_team"]:
            prices["home"] = o["price"]
        elif name == event["away_team"]:
            prices["away"] = o["price"]

    home_price = prices.get("home")
    draw_price = prices.get("draw")
    away_price = prices.get("away")
    if home_price is None or draw_price is None or away_price is None:
        raise ValueError("Faltan cuotas Home/Draw/Away en H2H.")

    return _safe_prob_from_prices(home_price, draw_price, away_price)



def live_odds_to_row(event: dict, jornada: int | None = None) -> dict:
    home_raw = event["home_team"]
    away_raw = event["away_team"]
    home = normalizar_equipo(home_raw)
    away = normalizar_equipo(away_raw)

    p_home, p_draw, p_away = _extract_h2h_probs(event)
    #p_over25 = _extract_over25_prob(event)

    row: dict = {
        "jornada": jornada,
        "home": home,
        "away": away,
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
    }
    
    return row


def build_live_odds_map_from_api(
    jornada: int | None = None,
    api_key: str | None = None,
    csv_path: str | None = None,
):
    data = fetch_live_odds(api_key)
    rows = [live_odds_to_row(ev, jornada=jornada) for ev in data]
    df = pd.DataFrame(rows)

    path = Path(csv_path or DEFAULT_CSV)
    df.to_csv(path, index=False)

    odds_map: dict[str, dict] = {}
    for _, r in df.iterrows():
        key = f"{r['home']}-{r['away']}"
        odds_map[key] = {
            "p_home": float(r["p_home"]),
            "p_draw": float(r["p_draw"]),
            "p_away": float(r["p_away"]),
        }
    return odds_map


def build_live_odds_map_from_csv(csv_path: str | None = None):
    path = Path(csv_path or DEFAULT_CSV)
    if not path.exists():
        raise FileNotFoundError(f"No existe cache de odds: {path}")

    df = pd.read_csv(path)
    odds_map: dict[str, dict] = {}
    for _, r in df.iterrows():
        key = f"{r['home']}-{r['away']}"
        odds_map[key] = {
            "p_home": float(r["p_home"]),
            "p_draw": float(r["p_draw"]),
            "p_away": float(r["p_away"]),
        }
    return odds_map


def debug_print_raw_odds(api_key: str | None = None, markets=("h2h", "totals")):
    data = fetch_live_odds(api_key=api_key, markets=markets)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def save_raw_odds_to_file(path: str, api_key: str | None = None, markets=("h2h", "totals")):
    data = fetch_live_odds(api_key=api_key, markets=markets)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path

def build_live_odds_map_from_api(
    temporada: str,
    jornada: int,
    api_key: str | None = None,
    csv_path: str | None = None,
):
    data = fetch_live_odds(api_key)
    rows = [live_odds_to_row(ev, jornada=jornada) for ev in data]
    df_new = pd.DataFrame(rows)
    df_new["temporada"] = temporada

    path = Path(csv_path or DEFAULT_CSV)

    if path.exists():
        df_old = pd.read_csv(path)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
        df_all = df_all.drop_duplicates(
            subset=["temporada", "jornada", "home", "away"],
            keep="last"
        )
    else:
        df_all = df_new

    df_all.to_csv(path, index=False)

    odds_map: dict[str, dict] = {}
    for _, r in df_all.iterrows():
        key = f"{r['temporada']}-{r['home']}-{r['away']}"
        odds_map[key] = {
            "p_home": float(r["p_home"]),
            "p_draw": float(r["p_draw"]),
            "p_away": float(r["p_away"]),
        }
    return odds_map

if __name__ == "__main__":
    for temporada, jornadas in {
        "23_24": range(1, 39),
        "24_25": range(1, 39),
        "25_26": range(1, 18),
    }.items():
        for j in jornadas:
            build_live_odds_map_from_api(
                temporada=temporada,
                jornada=j,
                api_key="86acc56b2b32372283ef6764b9a39d26",
                csv_path="live_odds_cache.csv",
            )
