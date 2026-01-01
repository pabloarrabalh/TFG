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
    nombre_norm = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)

def aplicar_alias(nombre, equipo=None):
    return nombre

def aplicar_alias_contextual(nombre, equipo_norm):
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
    nombre_html_norm y nombres_norm_equipo deben estar ya normalizados.
    Se endurece el comportamiento para APELLIDOS_CRITICOS (incluye herrera).
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

    # 2. Apodos (una sola palabra), PERO no se aplica para apellidos conflictivos
    if len(partes) == 1:
        palabra = partes[0]

        # si la palabra es un apellido conflictivo (herrera, garcia, etc.), no hagas apodo
        if palabra not in APELLIDOS_CRITICOS:
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
