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
    "isaac palazon camacho": "isi palazon",
    "jose luis garcia vaya": "pepelu",
    "ezequiel avila": "chimy avila",
    "cunat campos": "pablo cunat",
    "alhassane": "rahim bonkano",
    "tsygankov": "viktor tsyhankov",
    "elabdellaoui": "el abdellaoui",
    "caletacar": "caleta car",
    "alexanderarnold": "trent alexander arnold",
    "sorloth": "alexander sorloth",
}

# Lista de apellidos que sabemos que causan colisiones de hermanos o nombres comunes
APELLIDOS_CRITICOS = {"williams", "garcia", "rodriguez", "gonzalez", "hernandez"}

# ==========================================
# FUNCIONES DE NORMALIZACIÓN
# ==========================================

def normalizar_texto(texto):
    if not texto: return ""
    texto = str(texto).lower().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = texto.replace('.', ' ')
    texto = re.sub(r'[-.]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()

def normalizar_equipo(nombre_equipo):
    nombre_norm = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def aplicar_alias(nombre_jugador):
    nombre_norm = normalizar_texto(nombre_jugador)
    return ALIAS_JUGADORES.get(nombre_norm, nombre_norm)

# Alias contextual: solo para casos como 'Roca' en Espanyol
def aplicar_alias_contextual(nombre_jugador, equipo_norm=None):
    nombre_norm = normalizar_texto(nombre_jugador)
    if nombre_norm == "roca" and equipo_norm == "espanyol":
        return "antoniu"
    return aplicar_alias(nombre_jugador)

def normalizar_puntos(valor):
    if valor in ["-", "–", "", None]: return 0
    try: return int(float(valor))
    except: return valor

# ==========================================
# GESTIÓN DE CASOS CRÍTICOS (HERMANOS WILLIAMS, ETC.)
# ==========================================

def manejar_caso_especifico(nombre_html_norm, candidatos):
    """
    Desempata casos donde el apellido es igual pero la inicial es distinta.
    """
    tokens = nombre_html_norm.split()
    if not tokens: return None, 0
    
    # Tomamos la primera letra de la búsqueda (la inicial)
    inicial_buscada = tokens[0][0] 

    for cand in candidatos:
        # Buscamos qué candidato real empieza por esa letra
        if cand.startswith(inicial_buscada):
            return cand, 100
            
    return candidatos[0], 60

def coincide_por_iniciales(nombre_corto, nombre_largo):
    """
    Valida estructuralmente si las iniciales de uno encajan en el otro.
    """
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

def obtener_match_nombre(nombre_html_raw, nombres_norm_equipo, score_cutoff=85):
    # Caso especial: si el nombre HTML es 'Nombre ApellidoCritico' y en el CSV solo hay 'Nombre', asociar si es único
    if not nombres_norm_equipo:
        return None, 0

    nombre_html_norm = normalizar_texto(nombre_html_raw)
    nombre_html_norm = aplicar_alias(nombre_html_norm)
    nombre_html_norm = nombre_html_norm.replace('.', ' ').strip()
    nombre_html_norm = re.sub(r'\s+', ' ', nombre_html_norm)
    tokens = nombre_html_norm.split()

    if len(tokens) == 2:
        nombre, apellido = tokens
        if apellido.lower() in APELLIDOS_CRITICOS:
            candidatos_nombre = [n for n in nombres_norm_equipo if normalizar_texto(n) == nombre.lower()]
            if len(candidatos_nombre) == 1:
                return candidatos_nombre[0], 100

    # 1. Normalización y Alias
    nombre_html_norm = normalizar_texto(nombre_html_raw)
    nombre_html_norm = aplicar_alias(nombre_html_norm)

    # Limpieza extra para el proceso de tokens
    if not nombres_norm_equipo:
        return None, 0

    nombre_html_norm = normalizar_texto(nombre_html_raw)
    nombre_html_norm = nombre_html_norm.replace('.', ' ').strip()
    nombre_html_norm = re.sub(r'\s+', ' ', nombre_html_norm)
    tokens = nombre_html_norm.split()

    # 1. Apellido crítico: solo un candidato y coincide iniciales y nombre completo
    if len(tokens) >= 2:
        apellido = tokens[-1]
        iniciales_html = [tk[0] for tk in tokens[:-1] if tk]
        apellido_norm = apellido.lower()
        candidatos_apellido = [n for n in nombres_norm_equipo if n.split()[-1] == apellido]
        if apellido_norm in APELLIDOS_CRITICOS:
            if len(candidatos_apellido) == 1:
                n = candidatos_apellido[0]
                n_tokens = n.split()
                iniciales_cand = [tk[0] for tk in n_tokens[:-1] if tk]
                n_norm = normalizar_texto(n)
                if iniciales_html == iniciales_cand[:len(iniciales_html)] and n_norm == nombre_html_norm:
                    return n, 100
                # Si la inicial no coincide, bloquear fuzzy
                return None, 0
            elif len(candidatos_apellido) > 1:
                for n in candidatos_apellido:
                    n_tokens = n.split()
                    iniciales_cand = [tk[0] for tk in n_tokens[:-1] if tk]
                    n_norm = normalizar_texto(n)
                    if iniciales_html == iniciales_cand[:len(iniciales_html)] and n_norm == nombre_html_norm:
                        return n, 100
                # Si hay colisión de inicial y apellido, pero no coincide el nombre completo, bloquear fuzzy
                return None, 0

    # 2. Match por iniciales múltiples (ej: 'A. F. Carreras' ≈ 'Álvaro Fernández Carreras')
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

    # 3. Match difuso estándar
    nombre_match_norm, score_match, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )
    if nombre_match_norm and score_match >= score_cutoff:
        return nombre_match_norm, score_match
    return None, 0