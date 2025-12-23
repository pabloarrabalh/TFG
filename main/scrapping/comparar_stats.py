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
    ("xA_partido", ["xA", "xA", "xA"]),
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
    "summary": ["stats_standard", "stats_summary"],
    "passing": ["stats_passing"],
    "defense": ["stats_defense"],
    "possession": ["stats_possession"],
    "misc": ["stats_misc"],
    "keepers": ["stats_keeper", "stats_keepers"],
}

def limpiar_float(val):
    # Si es una Serie, coge el primer valor
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if pd.isna(val) or val == "" or val == "-":
        return 0.0
    s_val = str(val).split('\n')[0].replace('%', '').strip()
    try:
        return float(s_val)
    except:
        return 0.0

def extraer_tablas_fbref(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    tablas = {}
    # summary
    tabla_jug = soup.find('table', id=re.compile(r'_summary$'))
    if tabla_jug is not None:
        try:
            df = pd.read_html(str(tabla_jug))[0]
        except Exception:
            df = None
        if df is not None:
            df.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df.columns.get_level_values(-1)
            ]
            tablas["summary"] = df
    # keepers
    tabla_gk = soup.find('table', id=re.compile(r'^keeper_stats_'))
    if tabla_gk is not None:
        try:
            df_gk = pd.read_html(str(tabla_gk))[0]
        except Exception:
            df_gk = None
        if df_gk is not None:
            df_gk.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_gk.columns.get_level_values(-1)
            ]
            tablas["keepers"] = df_gk
    # defense
    tabla_def = soup.find('table', id=re.compile(r'_defense$'))
    if tabla_def is not None:
        try:
            df_def = pd.read_html(str(tabla_def))[0]
        except Exception:
            df_def = None
        if df_def is not None:
            df_def.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_def.columns.get_level_values(-1)
            ]
            tablas["defense"] = df_def
    # possession
    tabla_poss = soup.find('table', id=re.compile(r'_possession$'))
    if tabla_poss is not None:
        try:
            df_poss = pd.read_html(str(tabla_poss))[0]
        except Exception:
            df_poss = None
        if df_poss is not None:
            df_poss.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_poss.columns.get_level_values(-1)
            ]
            tablas["possession"] = df_poss
    # misc
    tabla_misc = soup.find('table', id=re.compile(r'_misc$'))
    if tabla_misc is not None:
        try:
            df_misc = pd.read_html(str(tabla_misc))[0]
        except Exception:
            df_misc = None
        if df_misc is not None:
            df_misc.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_misc.columns.get_level_values(-1)
            ]
            tablas["misc"] = df_misc
    # passing
    tabla_passing = soup.find('table', id=re.compile(r'_passing$'))
    if tabla_passing is not None:
        try:
            df_passing = pd.read_html(str(tabla_passing))[0]
        except Exception:
            df_passing = None
        if df_passing is not None:
            df_passing.columns = [
                str(col).split(',')[-1].strip(" ()'").replace(' ', '')
                for col in df_passing.columns.get_level_values(-1)
            ]
            tablas["passing"] = df_passing
    return tablas

def construir_diccionario_jugadores(tablas):
    jugadores = {}
    for tipo, df in tablas.items():
        for _, row in df.iterrows():
            nombre = str(row.get('Player', '')).strip()
            if nombre in ['nan', 'Player', 'Total', 'Players'] or re.match(r'^\d+\s+Players$', nombre):
                continue
            nombre_norm = normalizar_texto(aplicar_alias(nombre))
            if nombre_norm not in jugadores:
                jugadores[nombre_norm] = {}
            for col in row.index:
                key = f"{tipo}:{col}"
                # Solo guarda el primer valor para cada campo
                if key not in jugadores[nombre_norm]:
                    val = row[col]
                    # Si es una Serie, coge el primer valor
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    # Si es string con saltos de línea, coge solo la primera línea
                    if isinstance(val, str):
                        val = val.split('\n')[0].strip()
                    jugadores[nombre_norm][key] = val
    return jugadores

def buscar_valor(jugador_dict, posibles_campos, preferencia_tipo=None):
    # preferencia_tipo: lista de tipos de tabla en orden de preferencia
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
    
def comparar_partido_stats(path_html, path_csv, jugador_objetivo="kylian mbappe"):
    with open(path_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    tablas = extraer_tablas_fbref(html_content)
    jugadores_html = construir_diccionario_jugadores(tablas)
    df_csv = pd.read_csv(path_csv)
    df_csv["player_norm"] = df_csv["player"].apply(lambda x: normalizar_texto(aplicar_alias(x)))
    jugador_norm = normalizar_texto(aplicar_alias(jugador_objetivo))
    if jugador_norm not in df_csv["player_norm"].values:
        print(f"No se encontró a {jugador_objetivo} en el CSV.")
        return
    fila_csv = df_csv[df_csv["player_norm"] == jugador_norm].iloc[0]
    if jugador_norm not in jugadores_html:
        print(f"No se encontró a {jugador_objetivo} en el HTML.")
        return
    row_html = jugadores_html[jugador_norm]
    # Funciones auxiliares para obtener valores de cada tabla
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
    # Detecta si es portero
    es_portero = str(fila_csv.get('posicion', '')).strip().upper() == 'PT'

    print(f"\nComparativa de campos para {jugador_objetivo.title()}:\n")
    print(f"{'Campo CSV':<25} | {'Valor CSV':<10} | {'Valor HTML':<10} | {'Tabla/Columna HTML'}")
    print("-" * 80)

    print(f"{'Min_partido':<25} | {fmt(fila_csv.get('Min_partido','')):<10} | {fmt(get_summary('Min')):<10} | summary:Min")
    print(f"{'Gol_partido':<25} | {fmt(fila_csv.get('Gol_partido','')):<10} | {fmt(get_summary('Gls')):<10} | summary:Gls")
    print(f"{'Asist_partido':<25} | {fmt(fila_csv.get('Asist_partido','')):<10} | {fmt(get_summary('Ast')):<10} | summary:Ast")
    print(f"{'xG_partido':<25} | {fmt(fila_csv.get('xG_partido','')):<10} | {fmt(get_summary('xG')):<10} | summary:xG")
    xa_val = get_passing('xA')
    tabla_xa = "passing:xA"
    if xa_val in [None, "", "nan"]:
        xa_val = get_summary('xA')
        tabla_xa = "summary:xA"
    print(f"{'xA_partido':<25} | {fmt(fila_csv.get('xA_partido','')):<10} | {fmt(xa_val):<10} | {tabla_xa}")
    print(f"{'xAG':<25} | {fmt(fila_csv.get('xAG','')):<10} | {fmt(get_summary('xAG')):<10} | summary:xAG")
    print(f"{'Tiros':<25} | {fmt(fila_csv.get('Tiros','')):<10} | {fmt(get_summary('Sh')):<10} | summary:Sh")
    sh = get_summary('Sh')
    sot = get_summary('SoT')
    try:
        tiro_fallado_html = float(sh) - float(sot)
    except:
        tiro_fallado_html = ""
    print(f"{'TiroFallado_partido':<25} | {fmt(fila_csv.get('TiroFallado_partido','')):<10} | {fmt(tiro_fallado_html):<10} | summary:Sh-summary:SoT")
    print(f"{'TiroPuerta_partido':<25} | {fmt(fila_csv.get('TiroPuerta_partido','')):<10} | {fmt(get_summary('SoT')):<10} | summary:SoT")
    print(f"{'Pases_Totales':<25} | {fmt(fila_csv.get('Pases_Totales','')):<10} | {fmt(get_summary('Att')):<10} | summary:Att")
    cmp_pct = get_passing('Cmp%') if get_passing('Cmp%') != "" else get_summary('Cmp%')
    tabla_cmp = "passing:Cmp%" if get_passing('Cmp%') != "" else "summary:Cmp%"
    print(f"{'Pases_Completados_Pct':<25} | {fmt(fila_csv.get('Pases_Completados_Pct','')):<10} | {fmt(cmp_pct):<10} | {tabla_cmp}")
    print(f"{'Amarillas':<25} | {fmt(fila_csv.get('Amarillas','')):<10} | {fmt(get_misc('CrdY')):<10} | misc:CrdY")
    print(f"{'Rojas':<25} | {fmt(fila_csv.get('Rojas','')):<10} | {fmt(get_misc('CrdR')):<10} | misc:CrdR")
    # PORTERO: si no es PT, pon 0
    print(f"{'Goles_en_contra':<25} | {fmt(fila_csv.get('Goles_en_contra','')):<10} | {fmt(get_keepers('GA') if es_portero else 0):<10} | keepers:GA")
    print(f"{'Porcentaje_paradas':<25} | {fmt(fila_csv.get('Porcentaje_paradas','')):<10} | {fmt(get_keepers('Save%') if es_portero else 0):<10} | keepers:Save%")
    print(f"{'PSxG':<25} | {fmt(fila_csv.get('PSxG','')):<10} | {fmt(get_keepers('PSxG') if es_portero else 0):<10} | keepers:PSxG")
    print(f"{'Entradas':<25} | {fmt(fila_csv.get('Entradas','')):<10} | {fmt(get_defense('Tkl')):<10} | defense:Tkl")
    print(f"{'Duelos':<25} | {fmt(fila_csv.get('Duelos','')):<10} | {fmt(get_defense('Att')):<10} | defense:Att")
    # DuelosGanados: igual que fbref.py, si no hay valor pon 0
    duelos_ganados = get_defense('Won')
    print(f"{'DuelosGanados':<25} | {fmt(fila_csv.get('DuelosGanados','')):<10} | {fmt(duelos_ganados) if duelos_ganados not in [None, '', 'nan'] else '0':<10} | defense:Won")
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
    print(f"{'DuelosAereosGanados':<25} | {fmt(fila_csv.get('DuelosAereosGanados','')):<10} | {fmt(get_misc('Won')):<10} | misc:Won")
    print(f"{'DuelosAereosPerdidos':<25} | {fmt(fila_csv.get('DuelosAereosPerdidos','')):<10} | {fmt(get_misc('Lost')):<10} | misc:Lost")
    print(f"{'DuelosAereosGanadosPct':<25} | {fmt(fila_csv.get('DuelosAereosGanadosPct','')):<10} | {fmt(get_misc('Won%')):<10} | misc:Won%")
    # puntosFantasy

def mostrar_errores(errores):
    if errores:
        print("\nErrores encontrados:")
        print(f"{'JUGADOR':<25} | {'CAMPO':<25} | {'HTML':<10} | {'CSV':<10}")
        print("-" * 75)
        for err in errores:
            print(f"{err['player'][:25]:<25} | {err['campo']:<25} | {err['html']:<10} | {err['csv']:<10}")
    else:
        print("\nTodos los campos coinciden correctamente.")

def comparar_jornada(num_jornada):
    carpeta_html = os.path.join("main", "html", f"j{num_jornada}")
    carpeta_csv = os.path.join("data", "temporada_25_26", f"jornada_{num_jornada}")
    archivos_csv = [n for n in os.listdir(carpeta_csv) if n.endswith(".csv")]
    for archivo_csv in archivos_csv:
        m = re.search(r"p(\d+)_(.+)-(.+)\.csv", archivo_csv)
        if not m:
            continue
        idx = m.group(1)
        path_html = os.path.join(carpeta_html, f"p{idx}.html")
        path_csv = os.path.join(carpeta_csv, archivo_csv)
        if not os.path.exists(path_html):
            continue
        return

if __name__ == "__main__":
    path_html = r"main\html\j1\p1.html"
    path_csv = r"data\temporada_25_26\jornada_1\p1_girona-rayo vallecano.csv"
    comparar_partido_stats(path_html, path_csv, jugador_objetivo="Daley Blind")
