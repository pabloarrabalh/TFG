"""
commons.py

Módulo de utilidades genéricas:
- Normalización de textos, equipos y jugadores.
- Conversión numérica segura (int/float) desde strings HTML/CSV.
- Mapping de posiciones.
- Lógica de fuzzy matching de nombres (RapidFuzz).
- Helpers de alias por temporada.
- Lógica genérica de colapso de registros de Fantasy y postprocesado de DataFrames.
"""

import re
import unicodedata
from collections import defaultdict

from numpy import nan
import numpy as np
import pandas as pd
from bs4 import NavigableString
from rapidfuzz import process, fuzz

from alias import (
    ALIAS_EQUIPOS,
    APELLIDOS_CRITICOS,
    POSICION_MAP,
    MAPEO_STATS,
    COLUMNAS_MODELO,
    UMBRAL_MATCH,
    get_alias_jugadores,
)


# ==========================
# Normalización básica
# ==========================


def normalizar_texto(texto):
    """
    Normaliza un texto para comparación:
    - Convierte a str.
    - Pasa a minúsculas.
    - Elimina tildes/acentos (NFD).
    - Sustituye '-' y '.' por espacios.
    - Colapsa espacios múltiples en uno solo.
    """
    texto = str(texto).lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"[-.]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def normalizar_equipo(nombre_equipo: str) -> str:
    """
    Normaliza un nombre de equipo y aplica ALIAS_EQUIPOS.

    Devuelve un identificador canónico de equipo (ej: "atletico madrid").
    """
    nombre_norm = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def aplicar_alias(nombre, equipo=None):
    """
    Punto de extensión para alias genéricos (no por temporada).
    Actualmente no hace nada, pero se mantiene por compatibilidad.
    """
    return nombre


def aplicar_alias_contextual(nombre, equipo_norm):
    """
    Wrapper por compatibilidad: aplica alias teniendo en cuenta el equipo.
    Ahora mismo llama directamente a aplicar_alias, pero se puede extender.
    """
    return aplicar_alias(nombre, equipo_norm)


def normalizar_puntos(valor):
    """
    Normaliza un valor de puntos de Fantasy:
    - Si viene como '-', '–', '', None -> 0.
    - Si no, intenta convertir a int (aceptando floats como '3.0').
    """
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except Exception:
        return 0


def limpiar_minuto(nombre):
    """
    Elimina sufijos de minuto en nombres de jugador tipo "Fulano 90+2'".
    También quita '+' o '-' sueltos al final.
    """
    if not nombre:
        return nombre
    nombre = nombre.replace("+", "").replace("-", "").strip()
    nombre = re.sub(r"\s*\d+(?:\+\d+)?'?$", "", nombre).strip()
    return nombre


def extraer_nombre_jugador(td_nombre):
    """
    Extrae el texto de un TD de nombre de jugador en HTML,
    ignorando etiquetas internas y quedándose solo con el texto directo.
    """
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
    """
    Intenta convertir un valor que viene de HTML/CSV a float, de forma robusta.
    - Si es una Serie de pandas, toma el primer valor.
    - Quita porcentajes y saltos de línea.
    - Devuelve nan si no puede convertir.
    """
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
    """
    Envuelve _convertir_a_numero para dejar claro el tipo de salida.
    """
    return _convertir_a_numero(valor)


def to_int(valor):
    """
    Convierte a entero, redondeando si es float.
    Devuelve nan si no se puede convertir.
    """
    v = _convertir_a_numero(valor)
    if pd.isna(v):
        return nan
    return int(round(v))


def limpiar_numero(valor):
    """
    Conversión a float, con fallback 0.0 en caso de error.
    Útil para columnas donde no quieres nan, sino cero.
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
    """
    Devuelve el número formateado como string, sin decimales si es entero.
    """
    try:
        f = float(valor)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(valor)


def limpiar_numero_generico(valor):
    """
    Alias de limpiar_numero; se deja para compatibilidad con código antiguo.
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
    """
    Alias de formatear_numero; se mantiene por compatibilidad.
    """
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
    """
    Mapear una abreviatura de posición (FBRef u otros) a la posición interna
    usando POSICION_MAP. Por defecto 'MC'.
    """
    pos = (pos or "MC").upper()
    return POSICION_MAP.get(pos, "MC")


def añadir_equipo_y_player_norm(df, col_equipo="Equipo_propio", col_player="player"):
    """
    Añade columnas:
      - 'equipo_norm': normalizada usando normalizar_equipo.
      - 'player_norm': nombre del jugador normalizado con alias (si hubiera).
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


def normalizar_pos_clave(pos_val: str) -> str:
    """
    Normaliza posición a una clave agregada usada para distinguir jugadores
    con mismo apellido:
      - PT -> PT
      - MC/DT -> MDT (ataque/medio)
      - MC/DF -> MDF (medio/defensa)
    """
    if pos_val == "PT":
        return "PT"
    if pos_val in ("MC", "DT"):
        return "MDT"
    if pos_val in ("MC", "DF"):
        return "MDF"
    return pos_val


# ==========================
# Matching de nombres
# ==========================


def es_apellido_conflictivo(nombre_normalizado_html, nombres_normalizados_equipo):
    """
    Determina si un nombre compuesto por una sola palabra es un apellido
    conflictivo (varios jugadores con ese apellido en el mismo equipo).
    """
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
    Resuelve el mejor match fuzzy entre un nombre de HTML (FBRef) y una lista
    de nombres normalizados de Fantasy/CSV.

    Lógica:
      1. Si son dos palabras y el segundo es apellido crítico, intenta matchear
         solo por el nombre.
      2. Si es una palabra y no es apellido crítico, se trata como apodo
         (inicio/fin de nombre).
      3. Fuzzy matching con WRatio (RapidFuzz) con score_cutoff.
    """
    if not nombres_norm_equipo:
        return None, 0

    partes = nombre_html_norm.split()

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

    if len(partes) == 1:
        palabra = partes[0]

        if palabra not in APELLIDOS_CRITICOS:
            candidatos = []
            for nombre_equipo in nombres_norm_equipo:
                if (
                    nombre_equipo.startswith(palabra)
                    or nombre_equipo.endswith(palabra)
                ):
                    candidatos.append(nombre_equipo)

            if len(candidatos) == 1:
                return candidatos[0], 95

    mejor, score, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )

    if mejor and score >= score_cutoff:
        return mejor, score

    return None, 0


def nombre_a_mayus(nombre_norm):
    """
    Pasa un nombre normalizado (minúsculas) a formato "Nombre Apellido".
    """
    partes = str(nombre_norm).split()
    partes_capitalizadas = [p.capitalize() for p in partes]
    return " ".join(partes_capitalizadas)


def coincide_inicial_apellido(nombre1, nombre2):
    """
    Comprueba si dos nombres coinciden en:
      - apellido exacto
      - y la inicial del nombre de pila (permitiendo abreviaturas tipo 'J.')

    Se usa como heurística cuando no hay match directo entre Fantasy y FBRef.
    """
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
        if n.endswith("."):
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
    Normaliza la clave de un jugador que viene del HTML (nombre + equipo),
    aplicando alias y comparando con el conjunto de claves ya conocidas.
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
# Helpers dependientes de temporada
# ==========================


def normalizar_equipo_temporada(nombre: str) -> str:
    """
    Normaliza un nombre de equipo para una temporada concreta,
    usando ALIAS_EQUIPOS (actualmente compartido para todas).
    """
    nombre_norm = normalizar_texto(nombre)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def aplicar_alias_jugador_temporada(nombre: str, equipo_norm: str, temporada: str) -> str:
    """
    Aplica alias de jugadores específicos de una temporada y un equipo:

        nombre_largo_norm -> alias_corto_norm

    Si no hay alias definido, devuelve el nombre original.
    """
    alias_jug = get_alias_jugadores(temporada)

    equipo_norm = normalizar_texto(equipo_norm or "")
    mapa_equipo = alias_jug.get(equipo_norm, {})

    nombre_norm = normalizar_texto(nombre)

    alias_corto = mapa_equipo.get(nombre_norm)
    if alias_corto:
        return alias_corto
    return nombre


# ==========================
# Lógica genérica Fantasy y DF
# ==========================


def construir_fantasy_por_norm(fantasy_partido: dict):
    """
    A partir de un diccionario de Fantasy de partido:

        { clave_ff: info }

    donde info contiene:
        - nombre_norm
        - equipo_norm
        - posicion
        - minutos (opcional)
        - puntos

    construye:
        - jugadores_por_apellido_equipo:
            { (apellido, equipo_norm): [(clave_ff, info), ...] }

        - fantasy_por_norm:
            clave_norm -> lista de entradas Fantasy

      clave_norm:
        - (nombre_norm, equipo_norm) si apellido NO crítico
        - (nombre_norm, equipo_norm) si apellido crítico pero único
        - (nombre_norm, equipo_norm, pos_clave) si apellido crítico y duplicado

    Además colapsa duplicados por (nombre_norm, equipo_norm) quedándose con:
      - Si alguno tiene minutos > 0, el de más minutos.
      - Si todos tienen minutos = 0, el de más puntos.
    """
    agrupado = defaultdict(list)
    for clave_ff, info in fantasy_partido.items():
        nombre_norm = info.get("nombre_norm")
        equipo_norm = info.get("equipo_norm")
        pos_val = info.get("posicion", "MC")

        if not nombre_norm or not equipo_norm:
            continue

        minutos = info.get("minutos", 0)
        puntos = info.get("puntos", 0)

        clave_basica = (nombre_norm, equipo_norm)
        agrupado[clave_basica].append(
            {
                "clave_ff": clave_ff,
                "info": info,
                "min": minutos,
                "puntos": puntos,
                "posval": pos_val,
            }
        )

    colapsado = {}
    for clave_basica, entradas in agrupado.items():
        con_minutos = [e for e in entradas if (e["min"] or 0) > 0]
        if con_minutos:
            mejor = max(con_minutos, key=lambda e: e["min"] or 0)
        else:
            mejor = max(entradas, key=lambda e: e["puntos"] or 0)
        colapsado[clave_basica] = mejor

    jugadores_por_apellido_equipo = defaultdict(list)
    fantasy_por_norm = {}

    for (nombre_norm, equipo_norm), entrada in colapsado.items():
        clave_ff = entrada["clave_ff"]
        info = entrada["info"]
        pos_val = info.get("posicion", "MC")

        apellido = nombre_norm.split()[-1]
        jugadores_por_apellido_equipo[(apellido, equipo_norm)].append((clave_ff, info))

    for (apellido, equipo_norm), lista_jugadores in jugadores_por_apellido_equipo.items():
        for clave_ff, info in lista_jugadores:
            nombre_norm = info["nombre_norm"]
            pos_val = info.get("posicion", "MC")

            if apellido not in APELLIDOS_CRITICOS:
                clave_norm = (nombre_norm, equipo_norm)
            else:
                if len(lista_jugadores) == 1:
                    clave_norm = (nombre_norm, equipo_norm)
                else:
                    pos_clave = normalizar_pos_clave(pos_val)
                    clave_norm = (nombre_norm, equipo_norm, pos_clave)

            if clave_norm not in fantasy_por_norm:
                fantasy_por_norm[clave_norm] = []

            entrada_ff = {
                "clave_ff": clave_ff,
                "puntos": info["puntos"],
                "info": info,
            }
            fantasy_por_norm[clave_norm].append(entrada_ff)

    return jugadores_por_apellido_equipo, fantasy_por_norm


def postprocesar_df_partido(df):
    """
    Postprocesa el DataFrame de un partido antes de guardarlo:
      - Normaliza equipos propios/rivales.
      - Pone a 0 stats de portero para no-porteros.
      - Asegura columnas de tarjetas y rellena NaN con 0.
    """
    if df.empty:
        return df

    if "Equipo_propio" in df.columns:
        df["Equipo_propio"] = df["Equipo_propio"].apply(normalizar_equipo_temporada)

    if "Equipo_rival" in df.columns:
        df["Equipo_rival"] = df["Equipo_rival"].apply(normalizar_equipo_temporada)

    mask_no_portero = df["posicion"] != "PT"
    df.loc[mask_no_portero, "Goles_en_contra"] = 0.0
    df.loc[mask_no_portero, "Porcentaje_paradas"] = 0.0

    if "Amarillas" not in df.columns:
        df["Amarillas"] = 0

    if "Rojas" not in df.columns:
        df["Rojas"] = 0

    df["Amarillas"] = df["Amarillas"].fillna(0).astype(int)
    df["Rojas"] = df["Rojas"].fillna(0).astype(int)

    df = df.fillna(0)

    return df


def contar_tarjetas_banquillo(df):
    """
    Devuelve un DataFrame con los jugadores que:
      - Tienen al menos una amarilla o roja.
      - Tienen 0 minutos jugados.

    Se usa para detectar expulsiones/sanciones desde el banquillo.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    mask = (
        (df["Amarillas"].fillna(0) > 0)
        | (df["Rojas"].fillna(0) > 0)
    ) & (df["Min_partido"].fillna(0) == 0)
    df_banquillo = df[mask].copy()
    df_banquillo["banquillo"] = True
    return df_banquillo
