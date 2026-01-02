import os
import csv

from bs4 import BeautifulSoup


def parse_tabla_jornada_html(html: str, temporada: str, jornada: int):
    """
    Parsea el HTML de una jornada descargada (jornada.html) y devuelve
    una lista de dicts, una fila por equipo.
    El HTML está en formato markdown-table dentro de la página.
    """
    print(f"[LOG] Parseando HTML de jornada {jornada}...")
    soup = BeautifulSoup(html, "lxml")

    # El HTML descargado tiene la tabla como texto markdown, así que
    # buscamos el bloque que empieza en "## Clasificación Jornada"
    texto = soup.get_text("\n", strip=False)

    filas_out = []
    en_tabla = False

    for linea in texto.splitlines():
        linea = linea.strip()

        # Inicio bloque de la clasificación de jornada
        if linea.startswith("## Clasificación Jornada"):
            en_tabla = False
            continue

        # Cabecera de la tabla principal
        if linea.startswith("|PTS|PJ|PG|PE|PP|GF|GC|DG|"):
            en_tabla = True
            continue

        # Fin de la tabla principal (aparece "Leyenda" después)
        if en_tabla and linea.startswith("Leyenda"):
            break

        if not en_tabla:
            continue

        # Filas de datos: empiezan por | y no son la línea de separadores
        if not linea.startswith("|") or linea.startswith("|--"):
            continue

        # Ejemplo:
        # |1||FC Barcelona V V V V V|46|18|15|1|2|51|20|+31|
        partes = [p.strip() for p in linea.strip("|").split("|")]
        if len(partes) < 11:
            continue

        pos_str = partes[0]
        equipo_racha = partes[2]
        pts_str = partes[3]
        pj_str = partes[4]
        pg_str = partes[5]
        pe_str = partes[6]
        pp_str = partes[7]
        gf_str = partes[8]
        gc_str = partes[9]
        dg_str = partes[10]

        # equipo_racha: "FC Barcelona V V V V V"
        tokens = equipo_racha.split()
        if len(tokens) >= 6:
            racha_tokens = tokens[-5:]
            equipo_tokens = tokens[:-5]
            racha5 = "".join(t[0].upper() for t in racha_tokens)
            equipo = " ".join(equipo_tokens)
        else:
            equipo = equipo_racha
            racha5 = ""

        def to_int(s):
            s = s.replace("+", "").replace(" ", "")
            try:
                return int(s)
            except Exception:
                return None

        fila = {
            "temporada": temporada,
            "jornada": jornada,
            "equipo": equipo,
            "posicion": to_int(pos_str),
            "pj": to_int(pj_str),
            "pg": to_int(pg_str),
            "pe": to_int(pe_str),
            "pp": to_int(pp_str),
            "gf": to_int(gf_str),
            "gc": to_int(gc_str),
            "dg": to_int(dg_str),
            "pts": to_int(pts_str),
            "racha5partidos": racha5,  # ej: "VVVVV"
        }
        filas_out.append(fila)

        print(
            f"[DBG FILA] j{jornada}: pos={fila['posicion']}, equipo={equipo}, "
            f"pts={fila['pts']}, pj={fila['pj']}, gf={fila['gf']}, "
            f"gc={fila['gc']}, dg={fila['dg']}, racha={racha5}"
        )

    return filas_out


def scrapear_jornada_offline(codigo_temporada: str, jornada: int):
    """
    Lee main/html/temporada_<codigo_temporada>/j<jornada>/jornada.html
    y genera data/temporada_<codigo_temporada>/jornada_<jornada>/clasificacion_j<jornada>.csv
    """
    carpeta_html = os.path.join("main", "html", f"temporada_{codigo_temporada}", f"j{jornada}")
    ruta_html = os.path.join(carpeta_html, "jornada.html")

    if not os.path.exists(ruta_html):
        print(f"⚠️ No existe {ruta_html}")
        return

    print(f"[LOG] Leyendo {ruta_html}...")
    with open(ruta_html, "r", encoding="utf-8") as f:
        html = f.read()

    filas = parse_tabla_jornada_html(html, codigo_temporada, jornada)

    carpeta_csv = os.path.join("data", f"temporada_{codigo_temporada}", f"jornada_{jornada}")
    os.makedirs(carpeta_csv, exist_ok=True)

    ruta_csv = os.path.join(carpeta_csv, f"clasificacion_j{jornada}.csv")

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

    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        for fila in filas:
            writer.writerow(fila)

    print(f"✅ CSV generado: {ruta_csv}")


def scrapear_rango_jornadas_offline(codigo_temporada: str, j_ini: int, j_fin: int):
    """
    Procesa un rango de jornadas leyendo jornada.html en local
    y generando un CSV de clasificación por jornada.
    """
    print(
        f"[LOG] Iniciando scrap OFFLINE de clasificación: temp={codigo_temporada}, "
        f"jornadas {j_ini}..{j_fin}"
    )
    for j in range(j_ini, j_fin + 1):
        scrapear_jornada_offline(codigo_temporada, j)


if __name__ == "__main__":
    scrapear_rango_jornadas_offline("25_26", 1, 2)
