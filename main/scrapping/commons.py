# commons.py
import unicodedata
import re

from rapidfuzz import process, fuzz


# Alias equipos (compartido)
ALIAS_EQUIPOS = {
    "rayo vallecano": "rayo",
    "villarreal cf": "villarreal",
    "real oviedo": "oviedo",
    "celta vigo": "celta",
    "getafe cf": "getafe",
    "alaves": "alaves",
    "alavés": "alaves",
    "athletic club": "athletic",
    "elche cf": "elche",
    "sevilla fc": "sevilla",
    "real betis": "betis",
    "levante ud": "levante",
    "atlético": "atletico madrid",
    "atletico": "atletico madrid",
    "atletico madrid": "atletico madrid",
}


# Alias jugadores unificado (scrapper + testing)
ALIAS_JUGADORES = {
    # Osasuna: Raúl García y Rubén García
    "raul garcia": "raul garcia",
    "r. garcia": "raul garcia",
    "r garcia": "raul garcia",
    "rubén garcia": "ruben garcia",
    "ruben garcia": "ruben garcia",
    "rubén": "ruben garcia",
    "ruben": "ruben garcia",

    # Mallorca: Antonio Raíllo y Antonio Sánchez
    "antonio raillo": "antonio raillo",
    "a. raillo": "antonio raillo",
    "a raillo": "antonio raillo",
    "raillo": "antonio raillo",
    "antonio sanchez": "antonio sanchez",
    "a. sanchez": "antonio sanchez",
    "a sanchez": "antonio sanchez",
    "sanchez": "antonio sanchez",

    # Elche: Álvaro Rodríguez y Álvaro Núñez
    "alvaro rodriguez": "alvaro rodriguez",
    "a. rodriguez": "alvaro rodriguez",
    "a rodriguez": "alvaro rodriguez",
    "alvaro nunez": "alvaro nunez",
    "a. nunez": "alvaro nunez",
    "a nunez": "alvaro nunez",

    # Criterio “por defecto” para nombres sueltos
    "antonio": "antonio sanchez",
    "alvaro": "alvaro rodriguez",

    # Hermanos Williams (Athletic)
    "n. williams": "nico williams",
    "n williams": "nico williams",
    "nico williams": "nico williams",
    "i. williams": "inaki williams",
    "i williams": "inaki williams",
    "iñaki williams": "inaki williams",
    "inaki williams": "inaki williams",
    "williams": "nico williams",

    # Otros alias “originales”
    "isaac palazon camacho": "isi palazon",
    "isaac palazon": "isi palazon",
    "isi palazon": "isi palazon",
    "cristian portugues manzanera": "portu",
    "cristian portugues": "portu",
    "jose luis garcia vaya": "pepelu",
    "jose luis garcia": "pepelu",
    "ezequiel avila": "chimy avila",
    "chimy avila": "chimy avila",

    # Desambiguación Barcelona
    "eric garcia": "eric garcia",
    "sergi garcia": "sergi garcia",
    "garcia": "eric garcia",

    # Desambiguación Levante
    "pablo martinez": "pablo martinez",
    "pablo": "pablo martinez",

    # Alias extra del módulo de testing
    "tsygankov": "viktor tsyhankov",
    "s cardona": "sergi cardona",
    "p gueye": "pape gueye",
    "elabdellaoui": "el abdellaoui",
    "sorloth": "alexander sorloth",
    "caletacar": "caleta car",
    "cunat campos": "pablo cunat",
    "alhassane": "rahim bonkano",
    "a f carreras": "alvaro carreras",
    "alexanderarnold": "trent alexander arnold",
}


APELLIDOS_AMBIGUOS = {"garcia", "williams", "alvaro"}


def normalizar_texto(texto):
    """
    Normalización común:
    - str + lower + strip
    - quita tildes (NFD)
    - sustituye '.' y guiones por espacios
    - compacta espacios
    """
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = texto.replace('.', ' ')
    texto = re.sub(r'[-–—]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def normalizar_equipo(nombre_equipo):
    nombre_normalizado = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_normalizado, nombre_normalizado)


def aplicar_alias(nombre_jugador):
    nombre_normalizado = normalizar_texto(nombre_jugador)
    return ALIAS_JUGADORES.get(nombre_normalizado, nombre_normalizado)


def normalizar_puntos(valor):
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except Exception:
        return valor


def es_apellido_ambiguo(nombre_html_norm, nombres_norm_equipo):
    tokens = nombre_html_norm.split()
    return (
        len(tokens) == 1
        and tokens[0] in APELLIDOS_AMBIGUOS
        and sum(n.startswith(tokens[0]) for n in nombres_norm_equipo) > 1
    )


def obtener_match_nombre(nombre_html_norm, nombres_norm_equipo, score_cutoff=85):
    """
    Helper común para RapidFuzz (comprobador más cómodo).
    """
    if not nombres_norm_equipo:
        return None, 0
    nombre_match_norm, score_match, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )
    if nombre_match_norm is None:
        return None, 0
    if score_match < score_cutoff:
        return None, score_match
    return nombre_match_norm, score_match
