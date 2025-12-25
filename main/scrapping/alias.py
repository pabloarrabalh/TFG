import re

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
    "oviedo": {"alhassane": "rahim bonkano"},
    "girona": {"lass": "lancinet kourouma", "tsygankov": "viktor tsyhankov"},
    "celta": { "elabdellaoui": "el abdellaoui"},
    "real sociedad": { "caletacar": "caleta car"},
    "real madrid": { "alexanderarnold": "trent alexander arnold"},
    "atletico madrid": { "sorloth": "alexander sorloth"},
    "athletic": { "n williams": "nico williams", "i williams": "iñaki williams" },
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
    'player', 'posicion', 'Equipo_propio', 'Equipo_rival', 'Titular',
    'Min_partido', 'Gol_partido', 'Asist_partido', 'xG_partido',
    'xAG',
    'Tiros', 'TiroFallado_partido', 'TiroPuerta_partido', 'Pases_Totales', 'Pases_Completados_Pct',
    'Amarillas', 'Rojas', 'Goles_en_contra', 'Porcentaje_paradas', 'PSxG', 'puntosFantasy',
    'Entradas', 'Duelos', 'DuelosGanados', 'DuelosPerdidos',
    'Bloqueos', 'BloqueoTiros', 'BloqueoPase', 'Despejes',
    'Regates', 'RegatesCompletados', 'RegatesFallidos',
    'Conducciones', 'DistanciaConduccion', 'MetrosAvanzadosConduccion', 'ConduccionesProgresivas',
    'DuelosAereosGanados', 'DuelosAereosPerdidos', 'DuelosAereosGanadosPct'
]

UMBRAL_MATCH = 75.0
