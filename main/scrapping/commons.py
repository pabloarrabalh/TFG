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
        "isi": "isi palazón",
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
    },
    "levante": {
        "cunat campos": "pablo cunat",
    },
    "oviedo": {
        "alhassane": "rahim bonkano",
    },
    "girona": {
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
    },
    "athletic": {
        "n williams": "nico williams",
        "i williams": "iñaki williams",
    },
}

APELLIDOS_CRITICOS = {"williams", "garcia", "rodriguez", "gonzalez", "hernandez"}


# ==========================================
# FUNCIONES DE NORMALIZACIÓN
# ==========================================

def normalizar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    texto = ''.join(
        caracter for caracter in unicodedata.normalize('NFD', texto)
        if unicodedata.category(caracter) != 'Mn'
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
# GESTIÓN DE CASOS CRÍTICOS
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

    for indice in range(len(tokens_corto) - 1):
        if not tokens_largo[indice].startswith(tokens_corto[indice]):
            return False
    return True


def es_apellido_ambiguo(nombre_html_norm, nombres_norm_equipo):
    tokens = nombre_html_norm.split()
    return (
        len(tokens) == 1
        and tokens[0] in APELLIDOS_CRITICOS
        and sum(nombre.startswith(tokens[0]) for nombre in nombres_norm_equipo) > 1
    )


# ==========================================
# MATCHING PRINCIPAL DE NOMBRES
# ==========================================

def obtener_match_nombre(nombre_html_raw, nombres_norm_equipo, equipo_norm=None, score_cutoff=85):
    """
    nombre_html_raw debe venir ya normalizado (normalizar_texto) desde fuera
    o bien se normalizará aquí si hay alias de equipo. [web:35]
    """
    if not nombres_norm_equipo:
        return None, 0

    # si se pasa equipo, aplicamos alias y normalizamos; si no, asumimos ya normalizado
    if equipo_norm is not None:
        nombre_html_norm = normalizar_texto(
            aplicar_alias(nombre_html_raw, equipo=equipo_norm)
        )
    else:
        nombre_html_norm = nombre_html_raw

    tokens = nombre_html_norm.split()

    # 1. Caso especial 'Nombre ApellidoCritico'
    if len(tokens) == 2:
        nombre, apellido = tokens
        if apellido in APELLIDOS_CRITICOS:
            candidatos_nombre = [
                nombre_equipo for nombre_equipo in nombres_norm_equipo
                if normalizar_texto(nombre_equipo) == nombre
            ]
            if len(candidatos_nombre) == 1:
                unico = candidatos_nombre[0]
                return unico, 100

    # 2. Apellido crítico con iniciales
    if len(tokens) >= 2:
        apellido = tokens[-1]
        iniciales_html = [token[0] for token in tokens[:-1] if token]
        apellido_norm = apellido
        candidatos_apellido = [
            nombre_equipo for nombre_equipo in nombres_norm_equipo
            if nombre_equipo.split()[-1] == apellido
        ]
        if apellido_norm in APELLIDOS_CRITICOS:
            if len(candidatos_apellido) == 1:
                candidato = candidatos_apellido[0]
                tokens_cand = candidato.split()
                iniciales_cand = [token[0] for token in tokens_cand[:-1] if token]
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
                    iniciales_cand = [token[0] for token in tokens_cand[:-1] if token]
                    candidato_norm = normalizar_texto(candidato)
                    if (
                        iniciales_html == iniciales_cand[:len(iniciales_html)]
                        and candidato_norm == nombre_html_norm
                    ):
                        return candidato, 100
                return None, 0

    # 3. Match por iniciales múltiples
    if len(tokens) >= 2:
        iniciales = [token[0] for token in tokens[:-1] if token]
        apellido = tokens[-1]
        for candidato in nombres_norm_equipo:
            tokens_cand = candidato.split()
            if len(tokens_cand) >= len(tokens):
                apellido_cand = tokens_cand[-1]
                iniciales_cand = [token[0] for token in tokens_cand[:-1] if token]
                if apellido == apellido_cand and iniciales == iniciales_cand[:len(iniciales)]:
                    return candidato, 100
        candidatos_apellido = [
            nombre_equipo for nombre_equipo in nombres_norm_equipo
            if nombre_equipo.split()[-1] == apellido
        ]
        if len(candidatos_apellido) == 1:
            unico = candidatos_apellido[0]
            return unico, 100

    # 4. Fuzzy estándar
    nombre_match_norm, score_match, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )
    if nombre_match_norm and score_match >= score_cutoff:
        return nombre_match_norm, score_match
    return None, 0
