import os
import re
import unicodedata

from numpy import nan
import pandas as pd
from bs4 import NavigableString, BeautifulSoup
from rapidfuzz import process, fuzz

from alias import (
    ALIAS_EQUIPOS,
    APELLIDOS_CRITICOS,
    POSICION_MAP,
    MAPEO_STATS,
    COLUMNAS_MODELO,
    UMBRAL_MATCH,
)

# ==========================
# Normalización básica
# ==========================

def normalizar_texto(texto):
    texto = str(texto).lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = re.sub(r'[-.]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def normalizar_equipo(nombre_equipo):
    """
    Normaliza nombre de equipo y aplica ALIAS_EQUIPOS global.
    """
    nombre_norm = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def aplicar_alias(nombre, equipo=None):
    """
    Versión neutra: NO usa ALIAS_JUGADORES global.
    El alias de jugadores por temporada se aplica en fbref.py
    (aplicar_alias_jugador_temporada).
    """
    return nombre


def aplicar_alias_contextual(nombre, equipo_norm):
    """
    Wrapper semántico. De momento hace lo mismo que aplicar_alias.
    """
    return aplicar_alias(nombre, equipo_norm)


def normalizar_puntos(valor):
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except Exception:
        return 0


def limpiar_minuto(nombre):
    if not nombre:
        return nombre
    nombre = nombre.replace("+", "").replace("-", "").strip()
    nombre = re.sub(r"\s*\d+(?:\+\d+)?'?$", "", nombre).strip()
    return nombre


def extraer_nombre_jugador(td_nombre):
    textos = []
    for hijo in td_nombre.children:
        if isinstance(hijo, NavigableString):
            txt = hijo.strip()
            if txt:
                textos.append(txt)
    return " ".join(textos)


# ==========================
# Conversión numérica genérica
# ==========================

def _convertir_a_numero(valor):
    if isinstance(valor, pd.Series):
        valor = valor.iloc[0]
    if valor in (None, "", "-"):
        return nan

    texto = str(valor).split("\n")[0].replace("%", "").strip()
    num = pd.to_numeric(texto, errors="coerce")
    if pd.isna(num):
        return nan
    return float(num)


def to_float(valor):
    return _convertir_a_numero(valor)


def to_int(valor):
    v = _convertir_a_numero(valor)
    if pd.isna(v):
        return nan
    return int(round(v))


def limpiar_numero(valor):
    """
    Versión antigua (devuelve 0.0 en vez de nan).
    La puedes ir reemplazando por limpiar_numero_generico si quieres unificar.
    """
    if isinstance(valor, pd.Series):
        valor = valor.iloc[0]
    if valor is None:
        return 0.0
    s = str(valor).split("\n")[0].replace("%", "").strip()
    if s in ["", "-", "nan", "NaN", "None"]:
        return 0.0
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def formatear_numero(valor):
    try:
        f = float(valor)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(valor)


def limpiar_numero_generico(valor):
    """
    Limpia cualquier valor numérico para comparaciones CSV vs HTML:
    - quita saltos de línea y '%'
    - convierte a float, devolviendo 0.0 si no es numérico
    """
    if isinstance(valor, pd.Series):
        valor = valor.iloc[0]
    if valor is None:
        return 0.0
    s = str(valor).split("\n")[0].replace("%", "").strip()
    if s in ["", "-", "nan", "NaN", "None"]:
        return 0.0
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def fmt_generico(valor):
    """Formatea un número para mostrar en logs de comparativa."""
    try:
        f = float(valor)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(valor)


# ==========================
# Posiciones y mapping
# ==========================

def mapear_posicion(pos):
    pos = (pos or "MC").upper()
    return POSICION_MAP.get(pos, "MC")


def añadir_equipo_y_player_norm(df, col_equipo="Equipo_propio", col_player="player"):
    """
    Ojo: aplicar_alias aquí ya no mete alias de jugadores.
    Si necesitas alias por temporada en CSV, aplícalo fuera (fbref) antes.
    """
    df["equipo_norm"] = df[col_equipo].apply(normalizar_equipo)
    df["player_norm"] = df.apply(
        lambda row: normalizar_texto(
            aplicar_alias(row[col_player], row["equipo_norm"])
        ),
        axis=1,
    )
    return df


def _posicion_csv_es_medio(fila_csv):
    pos = str(fila_csv.get("posicion", "")).upper()
    return any(p in pos for p in ["MC", "MD", "MI", "MCD", "MCO", "MF", "DM", "CM"])


def _posicion_csv_es_defensa(fila_csv):
    pos = str(fila_csv.get("posicion", "")).upper()
    return any(p in pos for p in ["DF", "DC", "LD", "LI", "CB", "LB", "RB"])


def _posicion_html(row_html):
    for key in ["summary:Pos", "summary:position", "Pos", "position"]:
        if key in row_html:
            return str(row_html[key]).upper()
    return ""


# ==========================
# Matching de nombres
# ==========================

def es_apellido_conflictivo(nombre_normalizado_html, nombres_normalizados_equipo):
    partes = nombre_normalizado_html.split()
    if len(partes) != 1:
        return False

    apellido = partes[0]
    if apellido not in APELLIDOS_CRITICOS:
        return False

    jugadores_con_mismo_apellido = [
        nombre for nombre in nombres_normalizados_equipo
        if nombre.startswith(apellido)
    ]
    return len(jugadores_con_mismo_apellido) > 1


def obtener_match_nombre(nombre_html_norm, nombres_norm_equipo, equipo_norm=None, score_cutoff=85):
    """
    nombre_html_norm debe venir YA normalizado (lower, sin acentos, sin guiones)
    y con alias aplicado si corresponde. Aquí solo se aplican reglas de apellidos
    y fuzzy matching sobre nombres_norm_equipo, que también deben estar normalizados.
    """
    if not nombres_norm_equipo:
        return None, 0

    partes = nombre_html_norm.split()

    # 1. Apellidos críticos (dos palabras)
    if len(partes) == 2:
        nombre = partes[0]
        apellido = partes[1]

        if apellido in APELLIDOS_CRITICOS:
            candidatos_nombre = []
            for nombre_equipo in nombres_norm_equipo:
                if normalizar_texto(nombre_equipo) == nombre:
                    candidatos_nombre.append(nombre_equipo)

            if len(candidatos_nombre) == 1:
                unico = candidatos_nombre[0]
                return unico, 100

    # 2. Apodos (una sola palabra) — la mantenemos pero podrías comentarla si molesta
    if len(partes) == 1:
        palabra = partes[0]

        candidatos = []
        for nombre_equipo in nombres_norm_equipo:
            if nombre_equipo.startswith(palabra) or nombre_equipo.endswith(palabra):
                candidatos.append(nombre_equipo)

        if len(candidatos) == 1:
            return candidatos[0], 95

    # 3. Fuzzy normal
    mejor, score, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )

    if mejor and score >= score_cutoff:
        return mejor, score

    return None, 0


def nombre_a_mayus(nombre_norm):
    partes = str(nombre_norm).split()
    partes_capitalizadas = [p.capitalize() for p in partes]
    return " ".join(partes_capitalizadas)


def coincide_inicial_apellido(nombre1, nombre2):
    partes1 = nombre1.split()
    partes2 = nombre2.split()

    if len(partes1) < 2:
        return False
    if len(partes2) < 2:
        return False

    apellido1 = partes1[-1]
    apellido2 = partes2[-1]

    if apellido1 != apellido2:
        return False

    nombre1_pila = partes1[0]
    nombre2_pila = partes2[0]

    def es_abreviado(n):
        if len(n) <= 2:
            return True
        if n.endswith('.'):
            return True
        return False

    if es_abreviado(nombre1_pila) and es_abreviado(nombre2_pila):
        return False

    if es_abreviado(nombre1_pila):
        return nombre1_pila[0] == nombre2_pila[0]

    if es_abreviado(nombre2_pila):
        return nombre2_pila[0] == nombre1_pila[0]

    return nombre1_pila == nombre2_pila


def normalizar_clave_html(nombre_raw, equipo_norm, jugadores_html):
    """
    Devuelve la clave adecuada para jugadores_html.
    Nota: aplicar_alias_contextual es neutro; si quieres alias por temporada,
    pásale nombre_raw ya aliaseado desde fbref.
    """
    equipo_norm_n = normalizar_equipo(equipo_norm) if equipo_norm else None

    nombre_alias = normalizar_texto(
        aplicar_alias_contextual(nombre_raw, equipo_norm_n)
    )
    nombre_sin_alias = normalizar_texto(nombre_raw)

    if nombre_alias in jugadores_html:
        return nombre_alias
    if nombre_sin_alias in jugadores_html:
        return nombre_sin_alias
    return nombre_alias


# ==========================
# FBref: tablas y diccionario jugadores
# ==========================

TABLAS_FBREF = {
    "summary": ["_summary"],
    "passing": ["_passing"],
    "defense": ["_defense"],
    "possession": ["_possession"],
    "misc": ["_misc"],
    "keepers": ["keeper_stats_"],
}


def extraer_tablas_fbref(html_content):
    soup = BeautifulSoup(html_content, "lxml")
    tablas = {}
    from io import StringIO

    for tipo, sufijos in TABLAS_FBREF.items():
        dfs = []
        for tabla in soup.find_all("table"):
            tid = tabla.get("id") or ""
            if tipo == "keepers":
                if not any(suf in tid for suf in sufijos):
                    continue
            else:
                if not any(tid.endswith(suf) for suf in sufijos):
                    continue
            try:
                df = pd.read_html(StringIO(str(tabla)))[0]
            except Exception:
                df = None
            if df is None:
                continue
            try:
                cols = df.columns.get_level_values(-1)
            except Exception:
                cols = df.columns
            df.columns = [
                str(col).split(",")[-1].strip(" ()'").replace(" ", "")
                for col in cols
            ]
            dfs.append(df)
        if dfs:
            tablas[tipo] = pd.concat(dfs, ignore_index=True)
    return tablas


def construir_diccionario_jugadores(tablas):
    jugadores = {}
    for tipo, df in tablas.items():
        posibles_cols_squad = ["Squad", "Team", "Equipo", "Club"]
        col_squad = next((c for c in posibles_cols_squad if c in df.columns), None)

        for _, row in df.iterrows():
            nombre = str(row.get("Player", "")).strip()
            if nombre in ["nan", "Player", "Total", "Players"] or re.match(
                r"^\d+\s+Players$", nombre
            ):
                continue

            equipo = str(row.get(col_squad, "")).strip() if col_squad else None
            equipo_norm = normalizar_equipo(equipo) if equipo else None

            nombre_norm = normalizar_texto(
                aplicar_alias_contextual(nombre, equipo_norm)
            )

            if nombre_norm not in jugadores:
                jugadores[nombre_norm] = {}
            for col in row.index:
                key = f"{tipo}:{col}"
                if key not in jugadores[nombre_norm]:
                    val = row[col]
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    if isinstance(val, str):
                        val = val.split("\n")[0].strip()
                    jugadores[nombre_norm][key] = val
    return jugadores


# ==========================
# Scraping de puntos Fantasy
# ==========================

def scrapear_puntos_fantasy(path_html):
    """
    Lee puntos.html y devuelve:
    dict['equipoLocal-equipoVisitante'] = [(equipo_norm, nombre_completo_limpio, puntos_int)]
    """
    if not os.path.exists(path_html):
        print(f"[SCRAPPING] No existe {path_html}")
        return {}

    with open(path_html, "r", encoding="utf-8") as f:
        contenido_html = f.read()

    soup = BeautifulSoup(contenido_html, "lxml")
    puntos_por_partido = {}
    secciones_partido = soup.find_all("section", class_="over fichapartido")

    for section_partido in secciones_partido:
        header_partido = section_partido.find("header", class_="encabezado-partido")
        if not header_partido:
            continue

        div_local = header_partido.select_one(".equipo.local .nombre")
        div_visit = header_partido.select_one(".equipo.visitante .nombre")
        if not div_local or not div_visit:
            continue

        nombre_local = div_local.get_text(strip=True)
        nombre_visit = div_visit.get_text(strip=True)

        equipo_local_norm = normalizar_equipo(nombre_local)
        equipo_visitante_norm = normalizar_equipo(nombre_visit)
        clave_partido = f"{equipo_local_norm}-{equipo_visitante_norm}"

        lista_jugadores_html = []
        tablas_estadisticas = section_partido.find_all("table", class_="tablestats")

        for indice_tabla, tabla_stats in enumerate(tablas_estadisticas):
            div_contenedor = tabla_stats.find_parent(
                "div", class_=["box-estadisticas", "equipo-stats"]
            )

            if div_contenedor:
                clases = div_contenedor.get("class", [])
                if any("local" in c for c in clases):
                    equipo_actual_norm = equipo_local_norm
                else:
                    equipo_actual_norm = equipo_visitante_norm
            else:
                equipo_actual_norm = (
                    equipo_local_norm if indice_tabla == 0 else equipo_visitante_norm
                )

            filas_jugadores = tabla_stats.select("tbody tr.plegado")
            for tr_jugador in filas_jugadores:
                td_nombre = tr_jugador.find("td", class_="name")
                span_puntos = tr_jugador.select_one("span.laliga-fantasy")
                if not td_nombre or not span_puntos:
                    continue

                texto_puntos = span_puntos.get_text(strip=True)
                if texto_puntos in ["-", "–", ""]:
                    continue

                nombre_visible = td_nombre.get_text(" ", strip=True)
                nombre_visible = limpiar_minuto(nombre_visible)

                nombre_completo = nombre_visible
                if td_nombre.has_attr("title"):
                    nombre_completo = limpiar_minuto(td_nombre["title"].strip())
                elif td_nombre.has_attr("data-fullname"):
                    nombre_completo = limpiar_minuto(td_nombre["data-fullname"].strip())

                try:
                    puntos_int = int(float(texto_puntos))
                except ValueError:
                    continue

                lista_jugadores_html.append(
                    (equipo_actual_norm, nombre_completo, puntos_int)
                )

        puntos_por_partido[clave_partido] = lista_jugadores_html

    return puntos_por_partido


# ==========================
# Registro y salida de errores genéricos
# ==========================

def registrar_error(errores, partido, equipo, nombre_html, puntos_html,
                    nombre_csv=None, puntos_csv=None, score=0):
    errores.append({
        "partido": partido,
        "equipo": equipo,
        "nombre_html": nombre_html,
        "nombre_csv": nombre_csv,
        "puntos_html": puntos_html,
        "puntos_csv": puntos_csv,
        "score": score,
    })


def mostrar_errores(errores):
    if errores:
        print("\nErrores encontrados:")
        print("PARTIDO | EQUIPO | NOMBRE_HTML | NOMBRE_MATCH | PUNTOS_HTML | PUNTOS_CSV | SCORE")
        print("-" * 80)
        for err in errores:
            print(
                f"{err['partido']} | {err['equipo']} | {err['nombre_html']} | "
                f"{err['nombre_csv']} | {err['puntos_html']} | {err['puntos_csv']} | "
                f"{err['score']}"
            )
    else:
        print("\nTodos los jugadores tienen los puntos bien asignados.")
