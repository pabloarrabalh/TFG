import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from commons import (
    normalizar_texto,
    normalizar_equipo,
    aplicar_alias,
    obtener_match_nombre,
)


CAMPOS_MAPEO = [
    ("Min_partido", ["Min", "minutes", "Min"]),
    ("Gol_partido", ["Gls", "Goals", "Gls"]),
    ("Asist_partido", ["Ast", "Assists", "Ast"]),
    ("xG_partido", ["xG", "xG", "xG"]),
    ("TiroFallado_partido", ["Sh", "Shots", "Sh"]),
    ("TiroPuerta_partido", ["SoT", "Shots on target", "SoT"]),
    ("Pases_Totales", ["Cmp", "Att", "Cmp"]),
    ("Pases_Completados_Pct", ["Cmp%", "Cmp%", "Cmp%"]),
    ("Amarillas", ["CrdY", "Yellow Cards", "CrdY"]),
    ("Rojas", ["CrdR", "Red Cards", "CrdR"]),
    ("Goles_en_contra", ["GA", "GA", "GA"]),
    ("Porcentaje_paradas", ["Save%", "Save%", "Save%"]),
    ("PSxG", ["PSxG", "PSxG", "PSxG"]),
    ("Entradas", ["Tkl", "Tackles", "Tkl"]),
    ("Duelos", ["Att", "Challenges", "Att"]),
    ("DuelosGanados", ["Won", "Challenges Won", "Won"]),
    ("DuelosPerdidos", ["Lost", "Challenges Lost", "Lost"]),
    ("Bloqueos", ["Blocks", "Blocks", "Blocks"]),
    ("BloqueoTiros", ["Sh", "Shots Blocked", "Sh"]),
    ("BloqueoPase", ["Pass", "Passes Blocked", "Pass"]),
    ("Despejes", ["Clr", "Clearances", "Clr"]),
    ("Regates", ["Att", "Dribbles", "Att"]),
    ("RegatesCompletados", ["Succ", "Dribbles Succ", "Succ"]),
    ("RegatesFallidos", ["Lost", "Dribbles Lost", "Lost"]),
    ("Conducciones", ["Carries", "Carries", "Carries"]),
    ("DistanciaConduccion", ["TotDist", "Total Distance", "TotDist"]),
    ("MetrosAvanzadosConduccion", ["PrgDist", "Progressive Distance", "PrgDist"]),
    ("ConduccionesProgresivas", ["PrgC", "Progressive Carries", "PrgC"]),
    ("DuelosAereosGanados", ["Won", "Aerials Won", "Won"]),
    ("DuelosAereosPerdidos", ["Lost", "Aerials Lost", "Lost"]),
    ("DuelosAereosGanadosPct", ["Won%", "Aerials Won%", "Won%"]),
    ("puntosFantasy", ["puntosFantasy"]),
]


TABLAS_FBREF = {
    "summary": ["_summary"],
    "passing": ["_passing"],
    "defense": ["_defense"],
    "possession": ["_possession"],
    "misc": ["_misc"],
    # Adaptado para tablas de portero tipo keeper_stats_XXXX
    "keepers": ["keeper_stats_"],
}


def limpiar_float(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if pd.isna(val) or val == "" or val == "-":
        return 0.0
    s_val = str(val).split('\n')[0].replace('%', '').strip()
    try:
        return float(s_val)
    except:
        return 0.0


def limpiar_numero(val):
    """
    Normaliza valores numéricos para comparación:
    - Quita % y saltos de línea.
    - Convierte a float.
    - Si es NaN o no convertible (incluye 0/0 -> NaN), devuelve 0.0.
    """
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if val is None:
        return 0.0
    s = str(val).split('\n')[0].replace('%', '').strip()
    if s in ["", "-", "nan", "NaN", "None"]:
        return 0.0
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def extraer_tablas_fbref(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    tablas = {}
    for tipo, sufijos in TABLAS_FBREF.items():
        dfs = []
        for tabla in soup.find_all('table'):
            tid = tabla.get('id') or ''
            if tipo == "keepers":
                if not any(suf in tid for suf in sufijos):
                    continue
            else:
                if not any(tid.endswith(suf) for suf in sufijos):
                    continue
            try:
                df = pd.read_html(str(tabla))[0]
            except Exception:
                df = None
            if df is None:
                continue
            try:
                cols = df.columns.get_level_values(-1)
            except Exception:
                cols = df.columns
            df.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in cols
            ]
            dfs.append(df)
        if dfs:
            tablas[tipo] = pd.concat(dfs, ignore_index=True)
    return tablas


def construir_diccionario_jugadores(tablas):
    jugadores = {}
    for tipo, df in tablas.items():
        for _, row in df.iterrows():
            nombre = str(row.get('Player', '')).strip()
            if nombre in ['nan', 'Player', 'Total', 'Players'] or re.match(r'^\d+\s+Players$', nombre):
                continue
            equipo = str(row.get('Squad', '')).strip() if 'Squad' in row else None
            equipo_norm = normalizar_equipo(equipo) if equipo else None
            nombre_norm = normalizar_texto(aplicar_alias(nombre, equipo_norm))
            if nombre_norm not in jugadores:
                jugadores[nombre_norm] = {}
            for col in row.index:
                key = f"{tipo}:{col}"
                if key not in jugadores[nombre_norm]:
                    val = row[col]
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    if isinstance(val, str):
                        val = val.split('\n')[0].strip()
                    jugadores[nombre_norm][key] = val
    return jugadores


def buscar_valor(jugador_dict, posibles_campos, preferencia_tipo=None):
    if preferencia_tipo is None:
        preferencia_tipo = list(TABLAS_FBREF.keys())
    for campo in posibles_campos:
        for tipo in preferencia_tipo:
            key = f"{tipo}:{campo}"
            if key in jugador_dict:
                return jugador_dict[key]
    return None


def fmt(val):
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except:
        return str(val)


def mostrar_errores(errores):
    if errores:
        print("\nErrores encontrados:")
        print(f"{'JUGADOR':<25} | {'CAMPO':<25} | {'HTML (correcto)':<15} | {'CSV (tu dato)':<15}")
        print("-" * 90)
        for err in errores:
            print(f"{err['player'][:25]:<25} | {err['campo']:<25} | {err['html']:<15} | {err['csv']:<15}")
    else:
        print("\nTodos los campos coinciden correctamente.")


def mostrar_comparativa_jugador(info):
    """
    La dejo por si quieres debug visual completo.
    No se usa en el flujo normal tras tu petición.
    """
    if info is None:
        return
    jugador_objetivo = info["jugador_objetivo"]
    fila_csv = info["fila_csv"]
    get_summary = info["get_summary"]
    get_passing = info["get_passing"]
    get_misc = info["get_misc"]
    get_keepers = info["get_keepers"]
    get_defense = info["get_defense"]
    get_possession = info["get_possession"]
    es_portero = info["es_portero"]

    print(f"\nComparativa de campos para {jugador_objetivo.title()}:\n")
    print(f"{'Campo CSV':<25} | {'Valor CSV':<10} | {'Valor HTML':<10} | {'Tabla/Columna HTML'}")
    print("-" * 80)

    print(f"{'Min_partido':<25} | {fmt(fila_csv.get('Min_partido','')):<10} | {fmt(get_summary('Min')):<10} | summary:Min")
    print(f"{'Gol_partido':<25} | {fmt(fila_csv.get('Gol_partido','')):<10} | {fmt(get_summary('Gls')):<10} | summary:Gls")
    print(f"{'Asist_partido':<25} | {fmt(fila_csv.get('Asist_partido','')):<10} | {fmt(get_summary('Ast')):<10} | summary:Ast")
    print(f"{'xG_partido':<25} | {fmt(fila_csv.get('xG_partido','')):<10} | {fmt(get_summary('xG')):<10} | summary:xG")
    print(f"{'xAG':<25} | {fmt(fila_csv.get('xAG','')):<10} | {fmt(get_summary('xAG')):<10} | summary:xAG")
    print(f"{'Tiros':<25} | {fmt(fila_csv.get('Tiros','')):<10} | {fmt(get_summary('Sh')):<10} | summary:Sh")

    sh = get_summary('Sh')
    sot = get_summary('SoT')
    try:
        tiro_fallado_html = float(sh) - float(sot)
    except:
        tiro_fallado_html = 0.0

    print(f"{'TiroFallado_partido':<25} | {fmt(fila_csv.get('TiroFallado_partido','')):<10} | {fmt(tiro_fallado_html):<10} | summary:Sh-summary:SoT")
    print(f"{'TiroPuerta_partido':<25} | {fmt(fila_csv.get('TiroPuerta_partido','')):<10} | {fmt(get_summary('SoT')):<10} | summary:SoT")
    print(f"{'Pases_Totales':<25} | {fmt(fila_csv.get('Pases_Totales','')):<10} | {fmt(get_summary('Att')):<10} | summary:Att")

    cmp_pct = get_passing('Cmp%') if get_passing('Cmp%') != "" else get_summary('Cmp%')
    print(f"{'Pases_Completados_Pct':<25} | {fmt(fila_csv.get('Pases_Completados_Pct','')):<10} | {fmt(cmp_pct):<10} | passing/summary:Cmp%")
    print(f"{'Amarillas':<25} | {fmt(fila_csv.get('Amarillas','')):<10} | {fmt(get_misc('CrdY')):<10} | misc:CrdY")
    print(f"{'Rojas':<25} | {fmt(fila_csv.get('Rojas','')):<10} | {fmt(get_misc('CrdR')):<10} | misc:CrdR")

    ga_html = limpiar_numero(get_keepers('GA') if es_portero else 0)
    save_html = limpiar_numero(get_keepers('Save%') if es_portero else 0)
    psxg_html = limpiar_numero(get_keepers('PSxG') if es_portero else 0)

    print(f"{'Goles_en_contra':<25} | {fmt(fila_csv.get('Goles_en_contra','')):<10} | {fmt(ga_html):<10} | keepers:GA")
    print(f"{'Porcentaje_paradas':<25} | {fmt(fila_csv.get('Porcentaje_paradas','')):<10} | {fmt(save_html):<10} | keepers:Save%")
    print(f"{'PSxG':<25} | {fmt(fila_csv.get('PSxG','')):<10} | {fmt(psxg_html):<10} | keepers:PSxG")

    print(f"{'Entradas':<25} | {fmt(fila_csv.get('Entradas','')):<10} | {fmt(get_defense('Tkl')):<10} | defense:Tkl")
    print(f"{'Duelos':<25} | {fmt(fila_csv.get('Duelos','')):<10} | {fmt(get_defense('Att')):<10} | defense:Att")

    duelos_ganados_csv = limpiar_numero(fila_csv.get('DuelosGanados',''))
    duelos_ganados_html = limpiar_numero(get_defense('Won'))
    print(f"{'DuelosGanados':<25} | {fmt(duelos_ganados_csv):<10} | {fmt(duelos_ganados_html):<10} | defense:Won")
    print(f"{'DuelosPerdidos':<25} | {fmt(fila_csv.get('DuelosPerdidos','')):<10} | {fmt(get_defense('Lost')):<10} | defense:Lost")
    print(f"{'Bloqueos':<25} | {fmt(fila_csv.get('Bloqueos','')):<10} | {fmt(get_defense('Blocks')):<10} | defense:Blocks")
    print(f"{'BloqueoTiros':<25} | {fmt(fila_csv.get('BloqueoTiros','')):<10} | {fmt(get_defense('Sh')):<10} | defense:Sh (Blocks)")
    print(f"{'BloqueoPase':<25} | {fmt(fila_csv.get('BloqueoPase','')):<10} | {fmt(get_defense('Pass')):<10} | defense:Pass")
    print(f"{'Despejes':<25} | {fmt(fila_csv.get('Despejes','')):<10} | {fmt(get_defense('Clr')):<10} | defense:Clr")

    print(f"{'Regates':<25} | {fmt(fila_csv.get('Regates','')):<10} | {fmt(get_possession('Att')):<10} | possession:Att (Take-Ons)")
    print(f"{'RegatesCompletados':<25} | {fmt(fila_csv.get('RegatesCompletados','')):<10} | {fmt(get_possession('Succ')):<10} | possession:Succ (Take-Ons)")
    print(f"{'RegatesFallidos':<25} | {fmt(fila_csv.get('RegatesFallidos','')):<10} | {fmt(get_possession('Tkld')):<10} | possession:Tkld (Take-Ons)")

    print(f"{'Conducciones':<25} | {fmt(fila_csv.get('Conducciones','')):<10} | {fmt(get_possession('Carries')):<10} | possession:Carries")
    print(f"{'DistanciaConduccion':<25} | {fmt(fila_csv.get('DistanciaConduccion','')):<10} | {fmt(get_possession('TotDist')):<10} | possession:TotDist")
    print(f"{'MetrosAvanzadosConduccion':<25} | {fmt(fila_csv.get('MetrosAvanzadosConduccion','')):<10} | {fmt(get_possession('PrgDist')):<10} | possession:PrgDist")
    print(f"{'ConduccionesProgresivas':<25} | {fmt(fila_csv.get('ConduccionesProgresivas','')):<10} | {fmt(get_possession('PrgC')):<10} | possession:PrgC")

    wonpct_html = limpiar_numero(get_misc('Won%'))
    print(f"{'DuelosAereosGanados':<25} | {fmt(fila_csv.get('DuelosAereosGanados','')):<10} | {fmt(get_misc('Won')):<10} | misc:Won")
    print(f"{'DuelosAereosPerdidos':<25} | {fmt(fila_csv.get('DuelosAereosPerdidos','')):<10} | {fmt(get_misc('Lost')):<10} | misc:Lost")
    print(f"{'DuelosAereosGanadosPct':<25} | {fmt(fila_csv.get('DuelosAereosGanadosPct','')):<10} | {fmt(wonpct_html):<10} | misc:Won%")


def comparar_partido_stats(path_html, path_csv, jugador_objetivo="kylian mbappe"):
    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)
    df_csv = pd.read_csv(path_csv)
    df_csv["player_norm"] = df_csv.apply(
        lambda row: normalizar_texto(aplicar_alias(row["player"], row["Equipo_propio"])), axis=1
    )

    fila_jugador = df_csv[df_csv["player_norm"].str.lower() == normalizar_texto(jugador_objetivo).lower()]
    if fila_jugador.empty:
        return None

    fila_csv = fila_jugador.iloc[0]
    equipo_jugador = fila_csv["Equipo_propio"]
    jugador_norm = normalizar_texto(aplicar_alias(jugador_objetivo, equipo_jugador))
    if jugador_norm not in jugadores_html:
        return None

    row_html = jugadores_html[jugador_norm]

    def get_summary(col):
        return row_html.get(f"summary:{col}", "")

    def get_passing(col):
        return row_html.get(f"passing:{col}", "")

    def get_misc(col):
        return row_html.get(f"misc:{col}", "")

    def get_keepers(col):
        return row_html.get(f"keepers:{col}", "")

    def get_defense(col):
        return row_html.get(f"defense:{col}", "")

    def get_possession(col):
        return row_html.get(f"possession:{col}", "")

    es_portero = str(fila_csv.get('posicion', '')).strip().upper() == 'PT'

    return {
        "jugador_objetivo": jugador_objetivo,
        "fila_csv": fila_csv,
        "row_html": row_html,
        "get_summary": get_summary,
        "get_passing": get_passing,
        "get_misc": get_misc,
        "get_keepers": get_keepers,
        "get_defense": get_defense,
        "get_possession": get_possession,
        "es_portero": es_portero,
    }


def comparar_jornada(num_jornada):
    carpeta_html = os.path.join("main", "html", f"j{num_jornada}")
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
    archivos_csv = [n for n in os.listdir(carpeta_csv) if n.endswith(".csv")]
    errores = []
    for archivo_csv in archivos_csv:
        m = re.search(r"p(\d+)_(.+)-(.+)\.csv", archivo_csv)
        if not m:
            continue
        idx = m.group(1)
        path_html = os.path.join(carpeta_html, f"p{idx}.html")
        path_csv = os.path.join(carpeta_csv, archivo_csv)
        if not os.path.exists(path_html):
            print(f"Falta HTML: {path_html}")
            continue
        with open(path_html, "r", encoding="utf-8") as f:
            html_content = f.read()
        tablas = extraer_tablas_fbref(html_content)
        jugadores_html = construir_diccionario_jugadores(tablas)
        df_csv = pd.read_csv(path_csv)
        df_csv["player_norm"] = df_csv.apply(
            lambda row: normalizar_texto(aplicar_alias(row["player"], row["Equipo_propio"])), axis=1
        )
        for _, fila_csv in df_csv.iterrows():
            jugador_objetivo = fila_csv["player"]
            equipo_jugador = fila_csv["Equipo_propio"]
            jugador_norm = normalizar_texto(aplicar_alias(jugador_objetivo, equipo_jugador))
            if jugador_norm not in jugadores_html:
                errores.append({
                    "player": jugador_objetivo,
                    "campo": "NO ENCONTRADO EN HTML",
                    "html": "-",
                    "csv": "-"
                })
                continue
            row_html = jugadores_html[jugador_norm]
            checks = [
                ("Min_partido",        lambda: (fila_csv.get('Min_partido',''),        row_html.get("summary:Min", ""))),
                ("Gol_partido",        lambda: (fila_csv.get('Gol_partido',''),        row_html.get("summary:Gls", ""))),
                ("Asist_partido",      lambda: (fila_csv.get('Asist_partido',''),      row_html.get("summary:Ast", ""))),
                ("xG_partido",         lambda: (fila_csv.get('xG_partido',''),         row_html.get("summary:xG", ""))),
                ("Tiros",              lambda: (fila_csv.get('Tiros',''),              row_html.get("summary:Sh", ""))),
                ("TiroPuerta_partido", lambda: (fila_csv.get('TiroPuerta_partido',''), row_html.get("summary:SoT", ""))),
                ("Pases_Totales",      lambda: (fila_csv.get('Pases_Totales',''),      row_html.get("summary:Att", ""))),
                ("Amarillas",          lambda: (fila_csv.get('Amarillas',''),          row_html.get("misc:CrdY", ""))),
                ("Rojas",              lambda: (fila_csv.get('Rojas',''),              row_html.get("misc:CrdR", ""))),
            ]
            for campo, getter in checks:
                val_csv, val_html = getter()
                val_csv_n = limpiar_numero(val_csv)
                val_html_n = limpiar_numero(val_html)
                if val_csv_n != val_html_n:
                    errores.append({
                        "player": jugador_objetivo,
                        "campo": campo,
                        "html": fmt(val_html_n),
                        "csv": fmt(val_csv_n)
                    })
    mostrar_errores(errores)


def analizar_partido(num_jornada, num_partido):
    carpeta_html = os.path.join("main", "html", f"j{num_jornada}")
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
    archivos_csv = [n for n in os.listdir(carpeta_csv) if n.startswith(f"p{num_partido}_") and n.endswith(".csv")]
    if not archivos_csv:
        print(f"No se encontró el CSV para el partido {num_partido} de la jornada {num_jornada}")
        return
    archivo_csv = archivos_csv[0]
    path_html = os.path.join(carpeta_html, f"p{num_partido}.html")
    path_csv = os.path.join(carpeta_csv, archivo_csv)
    if not os.path.exists(path_html):
        print(f"Falta HTML: {path_html}")
        return
    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)
    df_csv = pd.read_csv(path_csv)
    df_csv["player_norm"] = df_csv.apply(
        lambda row: normalizar_texto(aplicar_alias(row["player"], row["Equipo_propio"])), axis=1
    )

    errores = []
    for _, fila_csv in df_csv.iterrows():
        jugador_objetivo = fila_csv["player"]
        equipo_jugador = fila_csv["Equipo_propio"]
        jugador_norm = normalizar_texto(aplicar_alias(jugador_objetivo, equipo_jugador))
        if jugador_norm not in jugadores_html:
            errores.append({
                "player": jugador_objetivo,
                "campo": "NO ENCONTRADO EN HTML",
                "html": "-",
                "csv": "-"
            })
            continue
        row_html = jugadores_html[jugador_norm]
        checks = [
            ("Min_partido",        lambda: (fila_csv.get('Min_partido',''),        row_html.get("summary:Min", ""))),
            ("Gol_partido",        lambda: (fila_csv.get('Gol_partido',''),        row_html.get("summary:Gls", ""))),
            ("Asist_partido",      lambda: (fila_csv.get('Asist_partido',''),      row_html.get("summary:Ast", ""))),
            ("xG_partido",         lambda: (fila_csv.get('xG_partido',''),         row_html.get("summary:xG", ""))),
            ("Tiros",              lambda: (fila_csv.get('Tiros',''),              row_html.get("summary:Sh", ""))),
            ("TiroPuerta_partido", lambda: (fila_csv.get('TiroPuerta_partido',''), row_html.get("summary:SoT", ""))),
            ("Pases_Totales",      lambda: (fila_csv.get('Pases_Totales',''),      row_html.get("summary:Att", ""))),
            ("Amarillas",          lambda: (fila_csv.get('Amarillas',''),          row_html.get("misc:CrdY", ""))),
            ("Rojas",              lambda: (fila_csv.get('Rojas',''),              row_html.get("misc:CrdR", ""))),
        ]
        for campo, getter in checks:
            val_csv, val_html = getter()
            val_csv_n = limpiar_numero(val_csv)
            val_html_n = limpiar_numero(val_html)
            if val_csv_n != val_html_n:
                errores.append({
                    "player": jugador_objetivo,
                    "campo": campo,
                    "html": fmt(val_html_n),
                    "csv": fmt(val_csv_n)
                })
    mostrar_errores(errores)


# =========================
# ANALISIS PURO + FUNCION AUXILIAR
# =========================

def analizar_jugador_interno(num_jornada, num_partido, nombre_jugador):
    """
    Analiza un jugador concreto sin imprimir nada.
    Devuelve dict con:
      - ok: bool
      - motivo: str (si ok=False)
      - info: dict (info de comparar_partido_stats)
      - campos_mal: lista de campos con discrepancias
      - discrepancias: lista de dicts {campo, csv, html}
    """
    carpeta_html = os.path.join("main", "html", f"j{num_jornada}")
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")

    archivos_csv = [
        n for n in os.listdir(carpeta_csv)
        if n.startswith(f"p{num_partido}_") and n.endswith(".csv")
    ]
    if not archivos_csv:
        return {
            "ok": False,
            "motivo": f"No se encontró el CSV para el partido {num_partido} de la jornada {num_jornada}",
        }

    archivo_csv = archivos_csv[0]
    path_html = os.path.join(carpeta_html, f"p{num_partido}.html")
    path_csv = os.path.join(carpeta_csv, archivo_csv)

    if not os.path.exists(path_html):
        return {
            "ok": False,
            "motivo": f"Falta HTML: {path_html}",
        }

    info = comparar_partido_stats(path_html, path_csv, nombre_jugador)
    if info is None:
        return {
            "ok": False,
            "motivo": f"No se pudo analizar al jugador '{nombre_jugador}' en j{num_jornada} partido {num_partido}.",
        }

    fila_csv = info["fila_csv"]
    get_summary = info["get_summary"]
    get_passing = info["get_passing"]
    get_misc = info["get_misc"]
    get_keepers = info["get_keepers"]
    get_defense = info["get_defense"]
    get_possession = info["get_possession"]
    es_portero = info["es_portero"]

    campos_a_comprobar = [
        ("Min_partido", lambda: (fila_csv.get('Min_partido',''), get_summary('Min'))),
        ("Gol_partido", lambda: (fila_csv.get('Gol_partido',''), get_summary('Gls'))),
        ("Asist_partido", lambda: (fila_csv.get('Asist_partido',''), get_summary('Ast'))),
        ("xG_partido", lambda: (fila_csv.get('xG_partido',''), get_summary('xG'))),
        ("Tiros", lambda: (fila_csv.get('Tiros',''), get_summary('Sh'))),
        ("TiroFallado_partido", lambda: (
            fila_csv.get('TiroFallado_partido',''),
            (float(get_summary('Sh')) - float(get_summary('SoT'))) if get_summary('Sh') != "" and get_summary('SoT') != "" else 0.0
        )),
        ("TiroPuerta_partido", lambda: (fila_csv.get('TiroPuerta_partido',''), get_summary('SoT'))),
        ("Pases_Totales", lambda: (fila_csv.get('Pases_Totales',''), get_summary('Att'))),
        ("Pases_Completados_Pct", lambda: (
            fila_csv.get('Pases_Completados_Pct',''),
            get_passing('Cmp%') if get_passing('Cmp%') != "" else get_summary('Cmp%')
        )),
        ("Amarillas", lambda: (fila_csv.get('Amarillas',''), get_misc('CrdY'))),
        ("Rojas", lambda: (fila_csv.get('Rojas',''), get_misc('CrdR'))),
        ("Goles_en_contra", lambda: (
            fila_csv.get('Goles_en_contra',''),
            limpiar_numero(get_keepers('GA')) if es_portero else 0
        )),
        ("Porcentaje_paradas", lambda: (
            fila_csv.get('Porcentaje_paradas',''),
            limpiar_numero(get_keepers('Save%')) if es_portero else 0
        )),
        ("PSxG", lambda: (
            fila_csv.get('PSxG',''),
            limpiar_numero(get_keepers('PSxG')) if es_portero else 0
        )),
        ("Entradas", lambda: (fila_csv.get('Entradas',''), get_defense('Tkl'))),
        ("Duelos", lambda: (fila_csv.get('Duelos',''), get_defense('Att'))),
        ("DuelosGanados", lambda: (fila_csv.get('DuelosGanados',''), get_defense('Won'))),
        ("DuelosPerdidos", lambda: (fila_csv.get('DuelosPerdidos',''), get_defense('Lost'))),
        ("Bloqueos", lambda: (fila_csv.get('Bloqueos',''), get_defense('Blocks'))),
        ("BloqueoTiros", lambda: (fila_csv.get('BloqueoTiros',''), get_defense('Sh'))),
        ("BloqueoPase", lambda: (fila_csv.get('BloqueoPase',''), get_defense('Pass'))),
        ("Despejes", lambda: (fila_csv.get('Despejes',''), get_defense('Clr'))),
        ("Regates", lambda: (fila_csv.get('Regates',''), get_possession('Att'))),
        ("RegatesCompletados", lambda: (fila_csv.get('RegatesCompletados',''), get_possession('Succ'))),
        ("RegatesFallidos", lambda: (fila_csv.get('RegatesFallidos',''), get_possession('Tkld'))),
        ("Conducciones", lambda: (fila_csv.get('Conducciones',''), get_possession('Carries'))),
        ("DistanciaConduccion", lambda: (fila_csv.get('DistanciaConduccion',''), get_possession('TotDist'))),
        ("MetrosAvanzadosConduccion", lambda: (fila_csv.get('MetrosAvanzadosConduccion',''), get_possession('PrgDist'))),
        ("ConduccionesProgresivas", lambda: (fila_csv.get('ConduccionesProgresivas',''), get_possession('PrgC'))),
        ("DuelosAereosGanados", lambda: (fila_csv.get('DuelosAereosGanados',''), get_misc('Won'))),
        ("DuelosAereosPerdidos", lambda: (fila_csv.get('DuelosAereosPerdidos',''), get_misc('Lost'))),
        ("DuelosAereosGanadosPct", lambda: (fila_csv.get('DuelosAereosGanadosPct',''), limpiar_numero(get_misc('Won%')))),
    ]

    campos_mal = []
    discrepancias = []
    for campo, getter in campos_a_comprobar:
        val_csv, val_html = getter()
        val_csv_n = limpiar_numero(val_csv)
        val_html_n = limpiar_numero(val_html)
        if val_csv_n != val_html_n:
            campos_mal.append(campo)
            discrepancias.append({
                "campo": campo,
                "csv": fmt(val_csv_n),
                "html": fmt(val_html_n),
            })

    return {
        "ok": True,
        "jugador_objetivo": nombre_jugador,
        "info": info,
        "campos_mal": campos_mal,
        "discrepancias": discrepancias,
    }


def mostrar_analisis_jugador(resultado):
    """
    Imprime solo los campos con error, no toda la comparativa.
    """
    if not resultado["ok"]:
        print(resultado["motivo"])
        return

    nombre = resultado["jugador_objetivo"]
    campos_mal = resultado["campos_mal"]
    discrepancias = resultado["discrepancias"]

    if not campos_mal:
        # Si quieres ver también los OK, descomenta la siguiente línea
        # print(f"[OK] {nombre}")
        return

    print(f"\n[ERROR] {nombre}")
    for d in discrepancias:
        campo = d["campo"]
        csv_val = d["csv"]
        html_val = d["html"]
        print(f"  - {campo}: CSV={csv_val} | HTML={html_val}")


def analizar_jugador(num_jornada, num_partido, nombre_jugador):
    print(f"[LOG] Procesando jugador: {nombre_jugador}")
    resultado = analizar_jugador_interno(num_jornada, num_partido, nombre_jugador)
    mostrar_analisis_jugador(resultado)


def analizar_partido_completo(num_jornada, num_partido):
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
    archivos_csv = [
        n for n in os.listdir(carpeta_csv)
        if n.startswith(f"p{num_partido}_") and n.endswith(".csv")
    ]
    if not archivos_csv:
        print(f"No se encontró el CSV para el partido {num_partido} de la jornada {num_jornada}")
        return

    archivo_csv = archivos_csv[0]
    path_csv = os.path.join(carpeta_csv, archivo_csv)
    df_csv = pd.read_csv(path_csv)

    for _, fila in df_csv.iterrows():
        nombre_jugador = fila["player"]
        print(f"[LOG] Procesando jugador: {nombre_jugador}")
        resultado = analizar_jugador_interno(num_jornada, num_partido, nombre_jugador)

        if not resultado["ok"]:
            print(f"\n[ERROR] {nombre_jugador}")
            print(f"  - {resultado['motivo']}")
        elif resultado["campos_mal"]:
            mostrar_analisis_jugador(resultado)


if __name__ == "__main__":
    # analizar_jugador(1, 10, "kylian mbappe")
    analizar_partido_completo(1, 10)
