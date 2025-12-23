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

# ALIAS_JUGADORES por equipo (claves normalizadas)
ALIAS_JUGADORES = {
    "rayo": {
        "isaac palazon camacho": "isi palazon", 
        "isi":"isi palazón"
    },
    "valencia": {
        "jose luis garcia vaya": "pepelu", 
        "pepelu": "pepelu",
    },
    "betis": {
        "ezequiel avila": "chimy",
        "chimy": "chimy",
    },
    "levante": {
        "cunat campos": "pablo cunat",           # levante
    },
    "oviedo": {
        "alhassane": "rahim bonkano",           # oviedo
    },
    "girona": {
        "tsygankov": "viktor tsyhankov",        # girona
    },
    "celta": {
        "elabdellaoui": "el abdellaoui",        # celta
    },
    "real sociedad": {
        "caletacar": "caleta car",              # real sociedad
    },
    "real madrid": {
        "alexanderarnold": "trent alexander arnold",  # madrid
    },
    "atletico madrid": {
        "sorloth": "alexander sorloth",         # atletico madrid
    },
    "athletic": {
        "n williams": "nico williams",          # athletic club
        "i williams": "iñaki williams",         # athletic club
    },
}

# Lista de apellidos que sabemos que causan colisiones de hermanos o nombres comunes
APELLIDOS_CRITICOS = {"williams", "garcia", "rodriguez", "gonzalez", "hernandez"}

# ==========================================
# FUNCIONES DE NORMALIZACIÓN
# ==========================================

def normalizar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = texto.replace('.', ' ')
    texto = re.sub(r'[-.]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()

def normalizar_equipo(nombre_equipo):
    nombre_norm = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)

def aplicar_alias(nombre, equipo=None):
    """
    Devuelve el alias canónico si existe para ese equipo, si no el nombre original.
    El normalizado se hace fuera con normalizar_texto.
    """
    nombre_norm = normalizar_texto(nombre)
    equipo_norm = normalizar_texto(equipo) if equipo else None

    if equipo_norm:
        alias_equipo = ALIAS_JUGADORES.get(equipo_norm, {})
        alias = alias_equipo.get(nombre_norm)
        if alias is not None:
            return alias

    return nombre

# Alias contextual: solo para casos como 'Roca' en Espanyol
def aplicar_alias_contextual(nombre_jugador, equipo_norm=None):
    nombre_norm = normalizar_texto(nombre_jugador)

    if nombre_norm == "roca" and equipo_norm == "espanyol":
        return "antoniu"

    return aplicar_alias(nombre_jugador, equipo=equipo_norm)

def normalizar_puntos(valor):
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except:
        return valor

# ==========================================
# GESTIÓN DE CASOS CRÍTICOS (HERMANOS WILLIAMS, ETC.)
# ==========================================

def manejar_caso_especifico(nombre_html_norm, candidatos):
    tokens = nombre_html_norm.split()
    if not tokens:
        return None, 0
    inicial_buscada = tokens[0][0]
    for cand in candidatos:
        if cand.startswith(inicial_buscada):
            return cand, 100
    return candidatos[0], 60

def coincide_por_iniciales(nombre_corto, nombre_largo):
    tokens_c = nombre_corto.split()
    tokens_l = nombre_largo.split()

    if len(tokens_c) < 2 or len(tokens_c) > len(tokens_l):
        return False

    if tokens_c[-1] not in tokens_l:
        return False

    for i in range(len(tokens_c) - 1):
        if not tokens_l[i].startswith(tokens_c[i]):
            return False
    return True

def es_apellido_ambiguo(nombre_html_norm, nombres_norm_equipo):
    tokens = nombre_html_norm.split()
    return (
        len(tokens) == 1 and tokens[0] in APELLIDOS_CRITICOS and
        sum(n.startswith(tokens[0]) for n in nombres_norm_equipo) > 1
    )

# ==========================================
# FUNCIÓN MAESTRA DE MATCHING
# ==========================================

def obtener_match_nombre(nombre_html_raw, nombres_norm_equipo, equipo_norm=None, score_cutoff=85):
    """
    Recibe el nombre tal como viene (con iniciales, tildes, etc.),
    una lista de nombres ya normalizados del equipo (claves de jugadores_html),
    y el equipo_norm para aplicar alias por equipo.
    Devuelve (nombre_match_norm, score).
    """
    if not nombres_norm_equipo:
        return None, 0

    # Normalizar y aplicar alias al nombre de entrada usando equipo
    nombre_html_norm = normalizar_texto(
        aplicar_alias(nombre_html_raw, equipo=equipo_norm)
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
                return candidatos_nombre[0], 100

    # 2. Apellido crítico con iniciales
    if len(tokens) >= 2:
        apellido = tokens[-1]
        iniciales_html = [tk[0] for tk in tokens[:-1] if tk]
        apellido_norm = apellido
        candidatos_apellido = [n for n in nombres_norm_equipo if n.split()[-1] == apellido]
        if apellido_norm in APELLIDOS_CRITICOS:
            if len(candidatos_apellido) == 1:
                n = candidatos_apellido[0]
                n_tokens = n.split()
                iniciales_cand = [tk[0] for tk in n_tokens[:-1] if tk]
                n_norm = normalizar_texto(n)
                if iniciales_html == iniciales_cand[:len(iniciales_html)] and n_norm == nombre_html_norm:
                    return n, 100
                return None, 0
            elif len(candidatos_apellido) > 1:
                for n in candidatos_apellido:
                    n_tokens = n.split()
                    iniciales_cand = [tk[0] for tk in n_tokens[:-1] if tk]
                    n_norm = normalizar_texto(n)
                    if iniciales_html == iniciales_cand[:len(iniciales_html)] and n_norm == nombre_html_norm:
                        return n, 100
                return None, 0

    # 3. Match por iniciales múltiples (A. F. Carreras ≈ Álvaro Fernández Carreras)
    if len(tokens) >= 2:
        iniciales = [t[0] for t in tokens[:-1] if t]
        apellido = tokens[-1]
        for n in nombres_norm_equipo:
            n_tokens = n.split()
            if len(n_tokens) >= len(tokens):
                ape_cand = n_tokens[-1]
                iniciales_cand = [tk[0] for tk in n_tokens[:-1] if tk]
                if apellido == ape_cand and iniciales == iniciales_cand[:len(iniciales)]:
                    return n, 100
        candidatos_apellido = [n for n in nombres_norm_equipo if n.split()[-1] == apellido]
        if len(candidatos_apellido) == 1:
            return candidatos_apellido[0], 100

    # 4. Fuzzy estándar
    nombre_match_norm, score_match, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )
    if nombre_match_norm and score_match >= score_cutoff:
        return nombre_match_norm, score_match
    return None, 0
