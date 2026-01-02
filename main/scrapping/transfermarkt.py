import os
import csv
import time
import random
import requests
from bs4 import BeautifulSoup

from commons import normalizar_equipo  # para mapear nombres TM -> tus nombres


BASE_URL = "https://www.transfermarkt.es/laliga/spieltagtabelle/wettbewerb/ES1"


def parse_tabla_jornada_transfermarkt(html: str, temporada: str, jornada: int):
    """
    Parsea el HTML de la tabla de jornada de Transfermarkt y devuelve
    una lista de dicts, una fila por equipo, SIN racha (la racha
    se calcula fuera, con estado entre jornadas).
    """
    print(f"[LOG] Parseando HTML de jornada {jornada} (Transfermarkt)...")
    soup = BeautifulSoup(html, "lxml")

    tabla = soup.find("table", class_="items")
    if not tabla or not tabla.tbody:
        print("[WARN] No se ha encontrado <table class='items'><tbody> en el HTML.")
        return []

    filas_out = []
    trs = tabla.tbody.find_all("tr")
    print(f"[LOG] Encontradas {len(trs)} filas de equipos en jornada {jornada}.")

    for idx, tr in enumerate(trs, start=1):
        tds = tr.find_all("td")
        if len(tds) < 10:
            print(f"[DBG] tr #{idx} con menos de 10 td, se salta.")
            continue

        # Posición
        pos_text = tds[0].get_text(strip=True).replace(".", "")
        try:
            posicion = int(pos_text)
        except Exception:
            posicion = None

        # Nombre equipo
        name_td = tds[2]
        a_team = name_td.find("a")
        equipo_raw = a_team.get_text(strip=True) if a_team else name_td.get_text(strip=True)
        equipo = normalizar_equipo(equipo_raw)

        def to_int_td(td):
            try:
                return int(td.get_text(strip=True).replace("+", ""))
            except Exception:
                return None

        pj = to_int_td(tds[3])
        pg = to_int_td(tds[4])
        pe = to_int_td(tds[5])
        pp = to_int_td(tds[6])

        goles_str = tds[7].get_text(strip=True)  # "3:0"
        try:
            gf, gc = map(int, goles_str.split(":"))
        except Exception:
            gf, gc = None, None

        dg = to_int_td(tds[8])
        pts = to_int_td(tds[9])

        fila = {
            "temporada": temporada,
            "jornada": jornada,
            "equipo": equipo,
            "posicion": posicion,
            "pj": pj,
            "pg": pg,
            "pe": pe,
            "pp": pp,
            "gf": gf,
            "gc": gc,
            "dg": dg,
            "pts": pts,
        }
        filas_out.append(fila)

        print(
            f"[DBG FILA] j{jornada}: pos={posicion}, equipo={equipo} "
            f"pj={pj}, pg={pg}, pe={pe}, pp={pp}, gf={gf}, gc={gc}, dg={dg}, pts={pts}"
        )

    print(f"[LOG] Filas encontradas jornada {jornada}: {len(filas_out)}")
    return filas_out


def scrapear_rango_jornadas_online(codigo_temporada: str, temporada_transfermarkt: int, j_ini: int, j_fin: int):
    """
    Descarga TODAS las jornadas indicadas y las mete en un único CSV:

        data/temporada_<codigo_temporada>/clasificacion_temporada.csv

    Una fila = un equipo en una jornada, con racha5partidos ya calculada
    dinámicamente a medida que se recorre la temporada.
    """
    print(
        f"[LOG] Iniciando scrap ONLINE de clasificación Transfermarkt: temp={codigo_temporada}, "
        f"saison_id={temporada_transfermarkt}, jornadas {j_ini}..{j_fin}"
    )

    carpeta_csv = os.path.join("data", f"temporada_{codigo_temporada}")
    os.makedirs(carpeta_csv, exist_ok=True)
    ruta_csv = os.path.join(carpeta_csv, "clasificacion_temporada.csv")

    campos = [
        "temporada",
        "jornada",
        "equipo",
        "posicion",
        "pj",
        "pg",
        "pe",
        "pp",
        "gf",
        "gc",
        "dg",
        "pts",
        "racha5partidos",
    ]

    # historial_por_equipo mantiene la secuencia de resultados y acumulados previos
    historial_por_equipo = {}  # equipo -> dict(pg_prev, pe_prev, pp_prev, resultados[list])

    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for jornada in range(j_ini, j_fin + 1):
            # pequeña espera aleatoria entre requests (p.ej. 3-7 segundos)
            sleep_s = random.uniform(3, 7)
            print(f"[LOG] Esperando {sleep_s:.2f}s antes de pedir jornada {jornada}...")
            time.sleep(sleep_s)

            params = {"saison_id": temporada_transfermarkt, "spieltag": jornada}
            print(f"[LOG] Descargando jornada {jornada} (saison_id={temporada_transfermarkt})...")
            resp = requests.get(BASE_URL, params=params, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                print(f"⚠️ Error HTTP {resp.status_code} para jornada {jornada}")
                continue

            filas = parse_tabla_jornada_transfermarkt(resp.text, codigo_temporada, jornada)

            # procesar filas de esta jornada, actualizando historial_por_equipo y racha5partidos
            for fila in filas:
                equipo = fila["equipo"]
                pg = fila["pg"] or 0
                pe = fila["pe"] or 0
                pp = fila["pp"] or 0

                if equipo not in historial_por_equipo:
                    historial_por_equipo[equipo] = {
                        "pg_prev": 0,
                        "pe_prev": 0,
                        "pp_prev": 0,
                        "resultados": [],
                    }

                info = historial_por_equipo[equipo]
                pg_prev = info["pg_prev"]
                pe_prev = info["pe_prev"]
                pp_prev = info["pp_prev"]

                # detectar resultado de ESTA jornada comparando acumulados
                if pg > pg_prev:
                    res = "W"
                elif pe > pe_prev:
                    res = "D"
                elif pp > pp_prev:
                    res = "L"
                else:
                    res = ""

                if res:
                    info["resultados"].append(res)

                # actualizar acumulados
                info["pg_prev"] = pg
                info["pe_prev"] = pe
                info["pp_prev"] = pp

                ultimos5 = info["resultados"][-5:]
                racha5 = "".join(ultimos5)
                fila["racha5partidos"] = racha5

                writer.writerow(fila)

    print(f"✅ CSV único de temporada generado con racha5partidos: {ruta_csv}")


if __name__ == "__main__":
    # ejemplo: scrapear jornadas 1..38 para saison_id=2025
    scrapear_rango_jornadas_online("25_26", temporada_transfermarkt=2025, j_ini=1, j_fin=38)
