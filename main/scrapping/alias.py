import re

# Alias de equipos, válidos para todas las temporadas
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

# Solo ALIAS_JUGADORES cambia por temporada
# Dirección: nombre_largo_norm (CSV/FBRef) -> alias_corto_norm (Fantasy/HTML)
ALIAS_JUGADORES_POR_TEMPORADA = {
    "25_26": {
        "espanyol": {"antoniu": "roca"},
        "rayo": {"isaac palazon camacho": "isi palazon"},
        "valencia": {"jose luis garcia vaya": "pepelu"},
        "betis": {
            "ezequiel avila": "chimy",
            "daniel guerrero": "dani perez",
        },
        "levante": {"pablo cunat": "cunat campos"},
        "oviedo": {"rahim bonkano": "alhassane"},
        "girona": {
            "lancinet kourouma": "lass",
            "viktor tsyhankov": "tsygankov",
        },
        "celta": {"el abdellaoui": "elabdellaoui"},
        "real sociedad": {
            "caleta car": "caletacar",
            "duje caleta car": "duje caletacar",
        },
        "real madrid": {"trent alexander arnold": "alexanderarnold"},
        "atletico madrid": {"alexander sorloth": "sorloth"},
        "athletic": {
            "nico williams": "n williams",
            "inaki williams": "i williams",
        },
        "sevilla": {"joaquin martinez gauna": "oso"},
    },
    "24_25": {
        "athletic": {  "nico williams": "n williams", "inaki williams": "i williams", },
        "rayo": {"isaac palazon camacho": "isi palazon"},
        "valencia": {"jose luis garcia vaya": "pepelu"},
        "betis": {"ezequiel avila": "chimy", },
        "espanyol": {"antoniu": "roca"},
        "mallorca": {"antonio sanchez": "antonio"},
        "girona": {
        # FBRef: Arnau Martinez  -> Fantasy: Arnau
        "arnau martinez": "arnau",
        "arnaut danjuma": "danjuma",
        # FBRef: Yangel Herrera   -> Fantasy: Herrera (esto ya lo tenías)
        "yangel herrera": "herrera",
        },
        "getafe": {
        # FBRef: Bertuğ Yıldırım  -> Fantasy: Yildirim
        "bertug yıldırım": "yildirim",
        # FBRef: John Joe         -> Fantasy: Patrick Finn
        "john joe": "patrick finn",
        }, 
    },
}


def get_alias_jugadores_reverse(temporada: str) -> dict:
    """
    Devuelve un mapa invertido por temporada:
    { equipo_norm: { alias_corto_norm (HTML) -> nombre_largo_norm (CSV) } }
    a partir de ALIAS_JUGADORES_POR_TEMPORADA (nombre_largo -> alias_corto).
    """
    original = ALIAS_JUGADORES_POR_TEMPORADA.get(temporada, {})
    invertido = {}

    for equipo_norm, mapa in original.items():
        inv_equipo = {}
        for nombre_largo_norm, alias_corto_norm in mapa.items():
            # invertimos: corto -> largo
            inv_equipo[alias_corto_norm] = nombre_largo_norm
        invertido[equipo_norm] = inv_equipo

    return invertido


APELLIDOS_CRITICOS = { "rodriguez", "gonzalez","herrera"}

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

MAPEO_STATS = {
    "summary": {
        "enteros": {
            "Min": "Min_partido",
            "Gls": "Gol_partido",
            "Ast": "Asist_partido",
            "Sh": "Tiros",
            "Att": "Pases_Totales",
        },
        "decimales": {
            "xG": "xG_partido",
            "xAG": "xAG",
        },
    },
    "defense": {
        "enteros": {
            "Tkl": "Entradas",
            "Att": "Duelos",
            "Won": "DuelosGanados",
            "Lost": "DuelosPerdidos",
            "Blocks": "Bloqueos",
            "Sh": "BloqueoTiros",
            "Pass": "BloqueoPase",
            "Clr": "Despejes",
        },
        "decimales": {},
    },
    "possession": {
        "enteros": {
            "Att": "Regates",
            "Succ": "RegatesCompletados",
            "Tkld": "RegatesFallidos",
            "Carries": "Conducciones",
            "PrgC": "ConduccionesProgresivas",
        },
        "decimales": {
            "TotDist": "DistanciaConduccion",
            "PrgDist": "MetrosAvanzadosConduccion",
        },
    },
    "misc": {
        "enteros": {
            "CrdY": "Amarillas",
            "CrdR": "Rojas",
            "Won": "DuelosAereosGanados",
            "Lost": "DuelosAereosPerdidos",
        },
        "decimales": {
            "Won%": "DuelosAereosGanadosPct",
        },
    },
}

COLUMNAS_MODELO = [
    "player",
    "posicion",
    "Equipo_propio",
    "Equipo_rival",
    "Titular",
    "Min_partido",
    "Gol_partido",
    "Asist_partido",
    "xG_partido",
    "xAG",
    "Tiros",
    "TiroFallado_partido",
    "TiroPuerta_partido",
    "Pases_Totales",
    "Pases_Completados_Pct",
    "Amarillas",
    "Rojas",
    "Goles_en_contra",
    "Porcentaje_paradas",
    "PSxG",
    "puntosFantasy",
    "Entradas",
    "Duelos",
    "DuelosGanados",
    "DuelosPerdidos",
    "Bloqueos",
    "BloqueoTiros",
    "BloqueoPase",
    "Despejes",
    "Regates",
    "RegatesCompletados",
    "RegatesFallidos",
    "Conducciones",
    "DistanciaConduccion",
    "MetrosAvanzadosConduccion",
    "ConduccionesProgresivas",
    "DuelosAereosGanados",
    "DuelosAereosPerdidos",
    "DuelosAereosGanadosPct",
]

UMBRAL_MATCH = 72.0


def get_alias_jugadores(temporada: str) -> dict:
    return ALIAS_JUGADORES_POR_TEMPORADA.get(temporada, {})
