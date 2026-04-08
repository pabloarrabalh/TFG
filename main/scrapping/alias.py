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

# Nombre normalizado -> nombre exacto en BD
EQUIPOS_BD_ALIAS = {
    "rayo vallecano": "Rayo Vallecano",
    "rayo": "Rayo Vallecano",
    "sevilla": "Sevilla",
    "sevilla fc": "Sevilla",
    "valencia": "Valencia",
    "valencia cf": "Valencia",
    "real sociedad": "Real Sociedad",
    "girona": "Girona",
    "girona fc": "Girona",
    "villarreal": "Villarreal",
    "real betis": "Real Betis",
    "betis": "Real Betis",
    "athletic": "Athletic Club",
    "athletic club": "Athletic Club",
    "barcelona": "Barcelona",
    "fc barcelona": "Barcelona",
    "real madrid": "Real Madrid",
    "getafe": "Getafe",
    "getafe cf": "Getafe",
    "celta vigo": "Celta Vigo",
    "celta": "Celta Vigo",
    "rc celta": "Celta Vigo",
    "alaves": "Alavés",
    "osasuna": "Osasuna",
    "ca osasuna": "Osasuna",
    "levante": "Levante",
    "mallorca": "Real Mallorca",
    "real mallorca": "Real Mallorca",
    "rcd mallorca": "Real Mallorca",
    "las palmas": "Las Palmas",
    "ud las palmas": "Las Palmas",
    "cadiz": "Cádiz",
    "cadiz cf": "Cádiz",
    "oviedo": "Real Oviedo",
    "real oviedo": "Real Oviedo",
    "elche": "Elche",
    "almeria": "Almería",
    "ud almeria": "Almería",
    "granada": "Granada",
    "granada cf": "Granada",
    "atletico madrid": "Atlético Madrid",
    "atletico": "Atlético Madrid",
    "espanyol": "RCD Espanyol",
    "rcd espanyol": "RCD Espanyol",
    "leganes": "Leganés",
    "cd leganes": "Leganés",
    "valladolid": "Real Valladolid",
    "real valladolid": "Real Valladolid",
}

# (CSV/FBRef) -> (Fantasy/HTML)
ALIAS_JUGADORES_POR_TEMPORADA = {
    "25_26": {
        "espanyol": {"antoniu": "roca"},
        "rayo": {"isaac palazon camacho": "isi"},
        "valencia": {"jose luis garcia vaya": "pepelu"},
        "betis": {"ezequiel avila": "chimy", "daniel guerrero": "dani perez"},
        "levante": {"pablo cunat": "cunat campos"},
        "oviedo": {"rahim bonkano": "alhassane"},
        "girona": {"lancinet kourouma": "lass", "viktor tsyhankov": "tsygankov"},
        "celta": {"el abdellaoui": "elabdellaoui"},
        "real sociedad": {"caleta car": "caletacar"},
        "real madrid": {"trent alexander arnold": "alexanderarnold"},
        "atletico madrid": {"alexander sorloth": "sorloth"},
        "athletic": {"nico williams": "n williams", "inaki williams": "i williams"},
        "sevilla": {"joaquin martinez gauna": "oso"},
    },
    "24_25": {
        "atletico madrid": {"alexander sorloth": "sorloth"},
        "las palmas": {"fabio": "fabio gonzalez", "jose carlos gonzalez": "josito"},
        "athletic": {"nico williams": "n williams", "inaki williams": "i williams"},
        "rayo": {"isaac palazon camacho": "isi"},
        "valencia": {"jose luis garcia vaya": "pepelu"},
        "betis": {"ezequiel avila": "chimy"},
        "espanyol": {"antoniu": "roca"},
        "girona": {"arnaut danjuma": "danjuma", "viktor tsyhankov": "tsygankov"},
        "getafe": {"bertug yıldırım": "yildirim", "john joe": "patrick finn"},
        "sevilla": {"alvaro pascual": "garcia pascual", "diego iturralde": "hormigo"},
        "valladolid": {"adrian baquerin": "arnu"},
        "leganes": {"adria altimira": "altimira"},
    },
    "23_24": {
        "athletic": {"nico williams": "n williams", "inaki williams": "i williams"},
        "villarreal": {"alexander sorloth": "sorloth", "alberto moreno": "a moreno"},
        "valencia": {
            "jose luis garcia vaya": "pepelu",
            "cristian": "rivero",
            "ruben lendinez": "iranzo",
        },
        "almeria": {"marko milovanovic": "marezi"},
        "rayo": {"isaac palazon camacho": "isi"},
        "sevilla": {
            "yassine bounou": "bono",
            "jesus corona": "tecatito",
            "diego iturralde": "hormigo",
        },
        "mallorca": {"samu costa": "samu", "jaume costa": "costa"},
        "alaves": {"xeber": "alkain"},
        "osasuna": {"ezequiel avila": "chimy"},
        "cadiz": {"mamadou mbaye": "momo"},
        "granada": {"adri bosch": "miki bosch"},
        "betis": {"ezequiel avila": "chimy"},
        "girona": {"viktor tsyhankov": "tsygankov", "savio": "savinho"},
        "las palmas": {"sergi cardona": "s cardona"},
    },
}

def get_alias_jugadores(temporada: str) -> dict:
    return ALIAS_JUGADORES_POR_TEMPORADA.get(temporada, {})

def get_alias_jugadores_reverse(temporada: str) -> dict:
    original = ALIAS_JUGADORES_POR_TEMPORADA.get(temporada, {})
    invertido = {}
    for equipo_norm, mapa in original.items():
        inv_equipo = {alias_corto_norm: nombre_largo_norm for nombre_largo_norm, alias_corto_norm in mapa.items()}
        invertido[equipo_norm] = inv_equipo
    return invertido

APELLIDOS_CRITICOS = {"rodriguez", "gonzalez", "herrera"}

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
        "enteros": {"Min": "min_partido", "Gls": "gol_partido", "Ast": "asist_partido","Sh": "tiros", "Att": "pases_totales","#":"dorsal"},
        "decimales": {"xG": "xg_partido", "xAG": "xag"},
    },
    "defense": {
        "enteros": {"Tkl": "entradas", "Att": "duelos", "Won": "duelos_ganados","Lost": "duelos_perdidos", "Blocks": "bloqueos", "Sh": "bloqueo_tiros",
                    "Pass": "bloqueo_pase", "Clr": "despejes"},
        "decimales": {},
    },
    "possession": {
        "enteros": {"Att": "regates", "Succ": "regates_completados", "Tkld": "regates_fallidos",
                    "Carries": "conducciones", "PrgC": "conducciones_progresivas"},
        "decimales": {"TotDist": "distancia_conduccion", "PrgDist": "metros_avanzados_conduccion"},
    },
    "misc": {
        "enteros": {"CrdY": "amarillas", "CrdR": "rojas",
                    "Won": "duelos_aereos_ganados", "Lost": "duelos_aereos_perdidos"},
        "decimales": {"Won%": "duelos_aereos_ganados_pct"},
    },
}

COLUMNAS_MODELO = [
    "player", "nacionalidad", "edad", "posicion", "dorsal", "equipo_propio", "equipo_rival", "titular",
    "min_partido", "gol_partido", "asist_partido", "xg_partido", "xag",
    "tiros", "tiro_fallado_partido", "tiro_puerta_partido", "pases_totales",
    "pases_completados_pct", "amarillas", "rojas", "goles_en_contra",
    "porcentaje_paradas", "psxg", "puntos_fantasy",
    "entradas", "duelos", "duelos_ganados", "duelos_perdidos",
    "bloqueos", "bloqueo_tiros", "bloqueo_pase", "despejes",
    "regates", "regates_completados", "regates_fallidos",
    "conducciones", "distancia_conduccion", "metros_avanzados_conduccion",
    "conducciones_progresivas", "duelos_aereos_ganados",
    "duelos_aereos_perdidos", "duelos_aereos_ganados_pct",
    "temporada", "jornada", "fecha_partido", "local", "roles",
]

UMBRAL_MATCH = 72.0

MAPEO_POSICIONES_INVERSO = {
    "PT": "Portero",          
    "DF": "Defensa",           
    "MC": "Centrocampista",    
    "DT": "Delantero",         
}