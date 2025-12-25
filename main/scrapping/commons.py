# commons.py
import unicodedata
import re
from rapidfuzz import process, fuzz


# ==========================================
# CONFIGURACIÓN Y DICCIONARIOS
# ==========================================

ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo", "villarreal cf": "villarreal", "real oviedo": "oviedo",
    "celta vigo": "celta", "getafe cf": "getafe", "alaves": "alaves",
    "alavés": "alaves", "athletic club": "athletic", "elche cf": "elche",
    "sevilla fc": "sevilla", "real betis": "betis", "levante ud": "levante",
    "atlético": "atletico madrid", "atletico": "atletico madrid",
    "atletico madrid": "atletico madrid",
}
ALIAS_JUGADORES = {
    "espanyol": {
        "roca": "antoniu roca",
    },
    "rayo": {
        "isaac palazón camacho": "isi palazon",
        "isaac palazon camacho": "isi palazon",
        "isi": "isi palazon",
    },
    "valencia": {
        "jose luis garcia vaya": "pepelu",
        "jose luis garcia vayá": "pepelu",
        "pepelu": "pepelu",
    },
    "betis": {
        "ezequiel avila": "chimy",
        "ezequiel ávila": "chimy",
        "chimy": "chimy",
        "chimy avila": "chimy",
        "ezequiel chimy avila": "chimy",
        # Dani Pérez: mismo nombre en FBref y puntos, pero unificamos tildes
        "dani perez": "dani perez",
        "dani pérez": "dani perez",
    },
    "levante": {
        "cunat campos": "pablo cunat",
    },
    "oviedo": {
        # Fantasy: Alhassane -> CSV/FBref: Rahim Bonkano
        "alhassane": "rahim bonkano",
    },
    "girona": {
        # Fantasy: Lass -> FBref: Lancinet Kourouma
        "lass": "lancinet kourouma",
        "lancinet kourouma": "lancinet kourouma",
        # Tsygankov abreviado
        "tsygankov": "viktor tsyhankov",
    },
    "celta": {
        "elabdellaoui": "el abdellaoui",
    },
    "real sociedad": {
        "caletacar": "caleta car",
    },
    "real madrid": {
        "alexanderarnold": "trent alexander arnold",
    },
    "atletico madrid": {
        "sorloth": "alexander sorloth",
        "sörloth": "alexander sorloth",
        "alexander sorloth": "alexander sorloth",
    },
    "athletic": {
        "n williams": "nico williams",
        "i williams": "iñaki williams",
    },
    "sevilla": {
        # Fantasy: Oso -> FBref: Joaquín Martínez Gauna
        "oso": "joaquin martinez gauna",
        "joaquin martinez gauna": "joaquin martinez gauna",
    },
}


APELLIDOS_CRITICOS = {"williams", "garcia", "rodriguez", "gonzalez", "hernandez"}


# ==========================================
# NORMALIZACIÓN BÁSICA
# ==========================================

def normalizar_texto(texto):
    if not texto:
        return ""
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
    """
    Devuelve el alias canónico si existe para ese equipo, si no el nombre original.
    """
    nombre_norm = normalizar_texto(nombre)
    equipo_norm = normalizar_texto(equipo) if equipo else None

    if equipo_norm:
        alias_equipo = ALIAS_JUGADORES.get(equipo_norm, {})
        alias = alias_equipo.get(nombre_norm)
        if alias is not None:
            return alias

    return nombre


def aplicar_alias_contextual(nombre_jugador, equipo_norm=None):
    """
    Aplica alias de jugador teniendo en cuenta el equipo (incluyendo reglas especiales).
    """
    equipo_norm = normalizar_equipo(equipo_norm) if equipo_norm else None
    nombre_norm = normalizar_texto(nombre_jugador)

    if nombre_norm == "roca" and equipo_norm == "espanyol":
        return "antoniu roca"

    return aplicar_alias(nombre_jugador, equipo=equipo_norm)


def normalizar_puntos(valor):
    """
    Normaliza puntos de fantasy: vacíos/guiones -> 0, resto a int.
    """
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except Exception:
        return 0


# ==========================================
# NUMÉRICOS GENÉRICOS (HTML/CSV)
# ==========================================

def limpiar_numero_generico(val):
    """
    Normaliza números de HTML/CSV:
    - Acepta Series, str, None, etc.
    - Quita %, saltos de línea y símbolos típicos.
    - Devuelve siempre float (0.0 si no se puede convertir).
    """
    import pandas as pd
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if val is None:
        return 0.0
    s = str(val).split("\n")[0].replace("%", "").strip()
    if s in ["", "-", "nan", "NaN", "None"]:
        return 0.0
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def fmt_generico(val):
    """
    Formatea un número para impresión (quita .0 si es entero).
    """
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(val)


# ==========================================
# HELPERS PARA DATAFRAMES
# ==========================================

def añadir_equipo_y_player_norm(df, col_equipo="Equipo_propio", col_player="player"):
    """
    Añade columnas:
    - equipo_norm: normalizar_equipo(col_equipo)
    - player_norm: normalizar_texto(aplicar_alias_contextual(col_player, equipo_norm))
    """
    df["equipo_norm"] = df[col_equipo].apply(normalizar_equipo)
    df["player_norm"] = df.apply(
        lambda row: normalizar_texto(
            aplicar_alias_contextual(row[col_player], row["equipo_norm"])
        ),
        axis=1,
    )
    return df


# ==========================================
# MATCHING NOMBRES
# ==========================================

def manejar_caso_especifico(nombre_html_norm, candidatos):
    tokens = nombre_html_norm.split()
    if not tokens:
        return None, 0
    inicial_buscada = tokens[0][0]
    for candidato in candidatos:
        if candidato.startswith(inicial_buscada):
            return candidato, 100
    primer_candidato = candidatos[0]
    return primer_candidato, 60


def coincide_por_iniciales(nombre_corto, nombre_largo):
    tokens_corto = nombre_corto.split()
    tokens_largo = nombre_largo.split()

    if len(tokens_corto) < 2 or len(tokens_corto) > len(tokens_largo):
        return False

    if tokens_corto[-1] not in tokens_largo:
        return False

    for i in range(len(tokens_corto) - 1):
        if not tokens_largo[i].startswith(tokens_corto[i]):
            return False
    return True


def es_apellido_ambiguo(nombre_html_norm, nombres_norm_equipo):
    tokens = nombre_html_norm.split()
    return (
        len(tokens) == 1
        and tokens[0] in APELLIDOS_CRITICOS
        and sum(nombre.startswith(tokens[0]) for nombre in nombres_norm_equipo) > 1
    )


def obtener_match_nombre(nombre_html_raw, nombres_norm_equipo, equipo_norm=None, score_cutoff=85):
    """
    nombre_html_raw puede venir sin normalizar.
    nombres_norm_equipo debe ser lista de nombres YA normalizados.
    Devuelve (nombre_match_norm, score).
    """
    if not nombres_norm_equipo:
        return None, 0

    equipo_norm = normalizar_equipo(equipo_norm) if equipo_norm else None

    nombre_html_norm = normalizar_texto(
        aplicar_alias_contextual(nombre_html_raw, equipo_norm)
    )
    tokens = nombre_html_norm.split()

    # 1. Caso especial 'Nombre ApellidoCritico'
    if len(tokens) == 2:
        nombre, apellido = tokens
        if apellido in APELLIDOS_CRITICOS:
            candidatos_nombre = [
                n for n in nombres_norm_equipo
                if normalizar_texto(n) == nombre
            ]
            if len(candidatos_nombre) == 1:
                unico = candidatos_nombre[0]
                return unico, 100

    # 2. Apellido crítico con iniciales
    if len(tokens) >= 2:
        apellido = tokens[-1]
        iniciales_html = [t[0] for t in tokens[:-1] if t]
        apellido_norm = apellido
        candidatos_apellido = [
            n for n in nombres_norm_equipo
            if n.split()[-1] == apellido
        ]
        if apellido_norm in APELLIDOS_CRITICOS:
            if len(candidatos_apellido) == 1:
                candidato = candidatos_apellido[0]
                tokens_cand = candidato.split()
                iniciales_cand = [t[0] for t in tokens_cand[:-1] if t]
                candidato_norm = normalizar_texto(candidato)
                if (
                    iniciales_html == iniciales_cand[:len(iniciales_html)]
                    and candidato_norm == nombre_html_norm
                ):
                    return candidato, 100
                return None, 0
            elif len(candidatos_apellido) > 1:
                for candidato in candidatos_apellido:
                    tokens_cand = candidato.split()
                    iniciales_cand = [t[0] for t in tokens_cand[:-1] if t]
                    candidato_norm = normalizar_texto(candidato)
                    if (
                        iniciales_html == iniciales_cand[:len(iniciales_html)]
                        and candidato_norm == nombre_html_norm
                    ):
                        return candidato, 100
                return None, 0

    # 3. Match por iniciales múltiples (no sólo apellidos críticos)
    if len(tokens) >= 2:
        iniciales = [t[0] for t in tokens[:-1] if t]
        apellido = tokens[-1]
        for candidato in nombres_norm_equipo:
            tokens_cand = candidato.split()
            if len(tokens_cand) >= len(tokens):
                apellido_cand = tokens_cand[-1]
                iniciales_cand = [t[0] for t in tokens_cand[:-1] if t]
                if apellido == apellido_cand and iniciales == iniciales_cand[:len(iniciales)]:
                    return candidato, 100
        candidatos_apellido = [
            n for n in nombres_norm_equipo
            if n.split()[-1] == apellido
        ]
        if len(candidatos_apellido) == 1:
            unico = candidatos_apellido[0]
            return unico, 100

    # 4. Caso apodos tipo 'pepelu'/'chimy' (1 token, prefijo/sufijo)
    if len(tokens) == 1:
        t = tokens[0]
        candidatos = [n for n in nombres_norm_equipo if n.endswith(t) or n.startswith(t)]
        if len(candidatos) == 1:
            return candidatos[0], 95

    # 5. Fuzzy estándar
    nombre_match_norm, score_match, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )
    if nombre_match_norm and score_match >= score_cutoff:
        return nombre_match_norm, score_match
    return None, 0
