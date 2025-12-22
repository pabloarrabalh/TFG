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

# ==========================================
# FUNCIÓN MAESTRA DE MATCHING
# ==========================================

def obtener_match_nombre(nombre_html_raw, nombres_norm_equipo, score_cutoff=85):
    if not nombres_norm_equipo:
        return None, 0

    # 1. Normalización y Alias
    nombre_html_norm = normalizar_texto(nombre_html_raw)
    nombre_html_norm = aplicar_alias(nombre_html_norm)

    # Limpieza extra para el proceso de tokens
    nombre_html_norm = nombre_html_norm.replace('.', ' ').strip()
    nombre_html_norm = re.sub(r'\s+', ' ', nombre_html_norm)
    tokens = nombre_html_norm.split()

    # 2. MATCH POR INICIALES Y APELLIDO (soporta 'A. F. Carreras', 'S. Cardona', 'P. Gueye', etc.)
    if len(tokens) >= 2:
        apellido_buscado = tokens[-1]
        candidatos_apellido = [n for n in nombres_norm_equipo if n.split()[-1] == apellido_buscado]
        if len(candidatos_apellido) == 1:
            return candidatos_apellido[0], 100
        elif len(candidatos_apellido) > 1:
            for cand in candidatos_apellido:
                cand_tokens = cand.split()
                # Solo comparar iniciales si el número de tokens coincide
                if len(cand_tokens) == len(tokens):
                    if all(tokens[i][0].lower() == cand_tokens[i][0].lower() for i in range(len(tokens)-1)):
                        return cand, 100
            # Si no hay match exacto, devolver None (no forzar match por iniciales si hay ambigüedad)
            return None, 0


    # 3. CASO ESPECIAL: nombre corto (ej. 'raul') y solo un jugador contiene ese nombre
    if len(tokens) == 1:
        posibles = [n for n in nombres_norm_equipo if tokens[0] in n.split() or tokens[0] in n]
        if len(posibles) == 1:
            return posibles[0], 100

    # 4. MATCH DIFUSO ESTÁNDAR (El resto de jugadores pasan por aquí)
    nombre_match_norm, score_match, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )

    if nombre_match_norm and score_match >= score_cutoff:
        return nombre_match_norm, score_match

    return None, 0

def es_apellido_ambiguo(nombre_html_norm, nombres_norm_equipo):
    tokens = nombre_html_norm.split()
    return (len(tokens) == 1 and tokens[0] in APELLIDOS_CRITICOS and 
            sum(n.startswith(tokens[0]) for n in nombres_norm_equipo) > 1)