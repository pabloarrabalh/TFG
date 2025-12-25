import re
import unicodedata

from numpy import nan
import pandas as pd
from bs4 import NavigableString
from rapidfuzz import process, fuzz

ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo", "villarreal cf": "villarreal", "real oviedo": "oviedo",
    "celta vigo": "celta", "getafe cf": "getafe", "alaves": "alaves",
    "alavés": "alaves", "athletic club": "athletic", "elche cf": "elche",
    "sevilla fc": "sevilla", "real betis": "betis", "levante ud": "levante",
    "atlético": "atletico madrid", "atletico": "atletico madrid",
    "atletico madrid": "atletico madrid",
}
ALIAS_JUGADORES = {
    "espanyol": { "roca": "antoniu roca" },
    "rayo": { "isaac palazon camacho": "isi palazon"},
    "valencia": { "jose luis garcia vaya": "pepelu"},
    "betis": {"ezequiel avila": "chimy", "dani perez": "dani perez" },
    "levante": {"cunat campos": "pablo cunat"},
    "oviedo": {"alhassane": "rahim bonkano",},
    "girona": {"lass": "lancinet kourouma","tsygankov": "viktor tsyhankov",},
    "celta": { "elabdellaoui": "el abdellaoui"},
    "real sociedad": {  "caletacar": "caleta car"},
    "real madrid": {  "alexanderarnold": "trent alexander arnold"},
    "atletico madrid": { "sorloth": "alexander sorloth"},
    "athletic": { "n williams": "nico williams","i williams": "iñaki williams" },
    "sevilla": {"oso": "joaquin martinez gauna"},
}
APELLIDOS_CRITICOS = {"garcia", "rodriguez", "gonzalez"}
POSICION_MAP = {
    "GK": "PT",
    "DF": "DF",
    "RB": "DF",
    "LB": "DF",
    "CB": "DF",
    "FW": "DT",
    "RW": "DT",
    "LW": "DT",
}

def normalizar_texto(texto):
    texto = str(texto).lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto) #Tildes y caracteres raros
        if unicodedata.category(c) != 'Mn'  
    )
    texto = re.sub(r'[-.]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def normalizar_equipo(nombre_equipo):
    nombre_norm = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def aplicar_alias(nombre, equipo=None):
    nombre_norm = normalizar_texto(nombre)
    equipo_norm = normalizar_texto(equipo) if equipo else None

    if equipo_norm:
        alias_equipo = ALIAS_JUGADORES.get(equipo_norm, {})
        alias = alias_equipo.get(nombre_norm)
        if alias is not None:
            return alias
    return nombre


def normalizar_puntos(valor):
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except Exception:
        return 0

def limpiar_minuto(nombre):
    #Pedri 87' 
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


def obtener_match_nombre(nombre_html_raw, nombres_norm_equipo, equipo_norm=None, score_cutoff=85):
    if not nombres_norm_equipo:
        return None, 0

    equipo_norm = normalizar_equipo(equipo_norm) if equipo_norm else None

    nombre_html_norm = normalizar_texto(
        aplicar_alias(nombre_html_raw, equipo_norm)
    )
    partes = nombre_html_norm.split()

    # --------------------------------------
    # 1. Apellidos críticos en el mismo equipo
    # --------------------------------------
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

    # --------------------------------------
    # 2. Alias (apodos de una sola palabra)
    # --------------------------------------
    if len(partes) == 1:
        palabra = partes[0]

        candidatos = []
        for nombre_equipo in nombres_norm_equipo:
            if nombre_equipo.startswith(palabra) or nombre_equipo.endswith(palabra):
                candidatos.append(nombre_equipo)

        if len(candidatos) == 1:
            return candidatos[0], 95

    # --------------------------------------
    # 3. Normal
    # --------------------------------------
    mejor, score, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    ) 

    if mejor and score >= score_cutoff:
        return mejor, score

    return None, 0
