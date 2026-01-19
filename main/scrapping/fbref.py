import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import os
import re 
from io import StringIO  
import logging  
from datetime import datetime 
import time  

import numpy as np  
import pandas as pd
from bs4 import BeautifulSoup  
from rapidfuzz import process as rf_process, fuzz as rf_fuzz  
from main.scrapping.commons import *
from main.scrapping.alias import *
from main.scrapping.roles import ROLES_DESTACADOS

logging.basicConfig( 
    level=logging.DEBUG,  
    format="%(asctime)s [%(levelname)s] %(message)s",  
)
logger = logging.getLogger(__name__)  

def log_jugadores_sin_entrada():  
    logger.info("24/25 J10->Villareal:Pau Navarro no tiene entrada en futbolfantasy.com")  
    logger.info("24/25 J15->Villareal:Pau Cabanes no tiene entrada en futbolfantasy.com")  

TEMPORADA_ACTUAL = "25_26"  

CARPETA_HTML, CARPETA_CSV = build_rutas_temporada(TEMPORADA_ACTUAL) 

POS_MAP_FANTASY = {  
    "Portero": "PT",  
    "Defensa": "DF",  
    "Mediocampista": "MC",  
    "Centrocampista": "MC",  
    "Delantero": "DT", 
}


def buscar_fila_portero(keepers, resumen_summary, clave_fbref):
    # 1) Coincde directamente
    fila_portero = keepers.get(clave_fbref)
    if fila_portero is not None:
        return fila_portero

   
    fila_sum = resumen_summary.get(clave_fbref)
    if fila_sum is not None:
        nombre_raw = limpiar_minuto(str(fila_sum.get("Player", "")).strip())
        base_para_apellido = nombre_raw
    else:
        base_para_apellido = clave_fbref

    apellido_ref = normalizar_texto(base_para_apellido).split()[-1]

    # 2) Buscar por apellido
    for clave_k, fila_k in keepers.items():
        if not clave_k:
            continue
        apellido_k = normalizar_texto(clave_k).split()[-1]
        if apellido_k == apellido_ref:
            return fila_k

    return None


def parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante, tipo=None)->dict[str,pd.Series]: #[nombre,fila_stats]
    caption = tabla_html.find("caption")  
    texto_caption = caption.get_text(strip=True) if caption else ""  

    equipo_caption = None  
    if texto_caption.endswith("Player Stats Table"):  # Comprueba si el texto del caption termina con la cadena “Player Stats Table”, patrón típico en tablas de jugador en FBref.
        equipo_caption = texto_caption.replace(" Player Stats Table", "").strip()  # Si coincide, elimina esa coletilla y deja solo el nombre del equipo (sin espacios adicionales).


    try:  
        df_tabla = pd.read_html(StringIO(str(tabla_html)))[0]  
    except Exception:  
        return {}  


    nombres_columnas = []  
    for col in df_tabla.columns.get_level_values(-1):  
        nombre_columna = str(col).split(",")[-1].strip(" ()'").replace(" ", "")
        nombres_columnas.append(nombre_columna)
    df_tabla.columns = nombres_columnas  # Sobreescribo ocn mis nombres


    id_tabla = tabla_html.get("id", "")  
    jugadores = {}  
    
    for _, fila in df_tabla.iterrows(): 
        nombre = str(fila["Player"]).strip()

        if nombre in ["nan", "Player", "Total", "Players"]:  continue  

        if re.match(r"^\d+\s+Players$", nombre):  # Eliminar fila 11 players
            continue  

        nombre = limpiar_minuto(nombre) 

        if equipo_caption:
            equipo_fila = equipo_caption
        elif "_home_" in id_tabla:
            equipo_fila = equipo_local
        elif "_away_" in id_tabla:
            equipo_fila = equipo_visitante
        else:
            equipo_fila = ""

        equipo_norm = normalizar_equipo_temporada(equipo_fila)

        nombre_con_alias = aplicar_alias_jugador_temporada(nombre, equipo_norm, TEMPORADA_ACTUAL)
        nombre_norm = normalizar_texto(nombre_con_alias) 
        nombre_base_norm = normalizar_texto(nombre)  # Clave alternativa en el caso especial de porteros.

        fila_copia = fila.copy()  
        fila_copia["__nombre_norm"] = nombre_norm  
        fila_copia["__equipo_norm"] = equipo_norm 

        jugadores[nombre_norm] = fila_copia 

        if tipo == "keepers": 
            if nombre_base_norm not in jugadores:   
                jugadores[nombre_base_norm] = fila_copia 

    return jugadores 

def rellenar_stats_fila(fila_salida, tablas_por_tipo, clave_fbref, pos_val):  
    for nombre_tipo, cfg in MAPEO_STATS.items():  
        mapa_tipo = tablas_por_tipo.get(nombre_tipo, {})  
        fila_tipo = mapa_tipo.get(clave_fbref)  

        if fila_tipo is None:  
            continue  

        for col_fb, col_dest in cfg["enteros"].items():  
            valor_fb = fila_tipo.get(col_fb, 0)  
            fila_salida[col_dest] = to_int(valor_fb)  

        for col_fb, col_dest in cfg["decimales"].items():  
            valor_fb = fila_tipo.get(col_fb, 0)  
            fila_salida[col_dest] = to_float(valor_fb)

    resumen = tablas_por_tipo.get("summary", {})  # summary
    fila_summary = resumen.get(clave_fbref) 

    if fila_summary is not None: 
        tiros_tot = to_int(fila_summary.get("Sh", 0)) 
        tiros_puerta = to_int(fila_summary.get("SoT", 0))  

        fila_salida["TiroFallado_partido"] = max(tiros_tot - tiros_puerta, 0)  # No viene directamente en FBref
        fila_salida["TiroPuerta_partido"] = tiros_puerta  
        fila_salida["Pases_Completados_Pct"] = to_float(fila_summary["Cmp%"])

    if pos_val == "PT":  
        keepers = tablas_por_tipo.get("keepers", {})  
        fila_portero = buscar_fila_portero(keepers, resumen, clave_fbref)

        if fila_portero is not None:  
            goles_contra = to_int(fila_portero.get("GA", 0))  

            pct_paradas = 0.0  
            for col_sv in ["Save%"]:  
                if col_sv in fila_portero: 
                    pct_paradas = to_float(fila_portero[col_sv])
                    break 

            if "PSxG" in fila_portero:  
                psxg = to_float(fila_portero.get("PSxG", 0))  
            else:  
                psxg = 0.0 

            fila_salida["Goles_en_contra"] = goles_contra  
            fila_salida["Porcentaje_paradas"] = pct_paradas  
            fila_salida["PSxG"] = psxg 

def obtener_calendario() -> dict[str, list[str]]:
    ruta_archivo = "main/html/temporada_25_26/calendario.html" 
    
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Encontrar la tabla correcta
    tabla = soup.find("table", id="sched_2025-2026_12_1")
    if not tabla:
        raise ValueError("No se encontró la tabla de calendario")
    
    calendario_temp = {}
    
    # Iterar sobre las filas (excluyendo header y spacer rows)
    for fila in tabla.find_all("tr"):
        # Omitir filas de espaciador
        if "spacer" in fila.get("class", []):
            continue
        
        # Obtener todas las celdas
        celdas = fila.find_all(["th", "td"])
        if len(celdas) < 9:  # Mínimo de columnas esperadas
            continue
        
        try:
            # Extraer datos usando data-stat
            gameweek = fila.find(attrs={"data-stat": "gameweek"})
            home_team = fila.find(attrs={"data-stat": "home_team"})
            away_team = fila.find(attrs={"data-stat": "away_team"})
            score = fila.find(attrs={"data-stat": "score"})
            date = fila.find(attrs={"data-stat": "date"})
            
            # Verificar que existan datos válidos
            if not (gameweek and home_team and away_team and score):
                continue
            
            # Extraer texto limpio
            jornada = int(gameweek.get_text(strip=True))
            equipo_local_raw = home_team.get_text(strip=True)
            equipo_visitante_raw = away_team.get_text(strip=True)
            
            # ⭐ NORMALIZAR EQUIPOS
            equipo_local_norm = normalizar_equipo_temporada(equipo_local_raw)
            equipo_visitante_norm = normalizar_equipo_temporada(equipo_visitante_raw)
            
            # Crear key por jornada si no existe
            if jornada not in calendario_temp:
                calendario_temp[jornada] = []
            
            # ⭐ Usar nombres normalizados en el partido
            partido = f"{equipo_local_norm} vs {equipo_visitante_norm}"
            calendario_temp[jornada].append(partido)
        
        except Exception as e:
            print(f"Error procesando fila: {e}")
            continue
    
    # Ordenar por jornada de menor a mayor
    calendario = dict(sorted(calendario_temp.items()))
    
    import json
    ruta_json = os.path.join("csv", "csvGenerados", "calendario.json")
    os.makedirs(os.path.dirname(ruta_json), exist_ok=True)
    with open(ruta_json, "w", encoding="utf-8") as f_json:
        json.dump(calendario, f_json, ensure_ascii=False, indent=2)
    print(f"✅ Calendario guardado en {ruta_json}")
    return calendario

def obtener_fantasy_jornada(jornada):  
    """
    resultado = {
        "equipoLocalNorm-equipoVisitanteNorm": {   # clave_partido
            "equipoNorm+NombreJugador": {          # clave_ff
                ... info_jugador ...
            },
        ...
        },
        ...
    }
    id único por equipo+nombre-> evita colisiones de nombres/apellidos entre equipos 
    Si ocurre dentro del equipo introduzco la posición para desempatar
    """
    ruta_puntos = os.path.join(CARPETA_HTML, f"j{jornada}", "puntos.html")  


    if not os.path.exists(ruta_puntos):  
        print(f"     ⚠️ No se encuentra puntos.html en j{jornada}")  
        return {}  


    html = leer_html(ruta_puntos) 
    if not html:  
        return {} 

    soup = BeautifulSoup(html, "lxml")  
    resultado = {}  

    partidos = soup.find_all("section", class_="over fichapartido")  

    for partido in partidos: 
        header_partido = partido.find("header", class_="encabezado-partido")  

        div_local = header_partido.select_one(".equipo.local .nombre")  
        div_visitante = header_partido.select_one(".equipo.visitante .nombre")

        local_norm  = normalizar_equipo_temporada(div_local.get_text(strip=True))
        visit_norm  = normalizar_equipo_temporada(div_visitante.get_text(strip=True))


        clave_partido = f"{local_norm}-{visit_norm}" 

        mapa_puntos = {}  

        tablas_equipos = partido.select("table.tablestats")  
        for indice, tabla_equipo in enumerate(tablas_equipos):  
            filas_jugadores = tabla_equipo.select("tbody tr.plegado")  

            equipo_tabla_norm = local_norm if indice == 0 else visit_norm  # la primera tabla (índice 0) se asocia al local, la segunda al visitante

            for tr_jugador in filas_jugadores:  
                td_nombre = tr_jugador.find("td", class_="name")  
                if not td_nombre:  
                    continue  

                nombre_sin_min = limpiar_minuto(extraer_nombre_jugador(td_nombre))

                pos_fantasy_raw = td_nombre.get(  "data-posicion-laliga-fantasy", "").strip()
                pos_fantasy = POS_MAP_FANTASY.get(pos_fantasy_raw, "MC")

                puntos = 0 
                span_puntos = tr_jugador.select_one("span.laliga-fantasy")

                if span_puntos:
                    try:
                        puntos = int(span_puntos.get_text(strip=True))
                    except ValueError:
                        puntos = 0

                td_eventos = tr_jugador.find("td", class_="events")
                amarillas = 0  
                rojas = 0

                if td_eventos:  
                    imagenes_evento = td_eventos.find_all("img")  
                    for img_evento in imagenes_evento: 
                        tooltip = (img_evento.get("data-tooltip") or "").strip().lower()  
                        alt = (img_evento.get("alt") or "").strip().lower()
                        texto = tooltip if tooltip else alt  # a veces falta 
                        if "amarilla" in texto:  
                            amarillas += 1 
                        elif "roja" in texto:
                            rojas += 1 

                equipo_norm = equipo_tabla_norm
                clave_ff = f"{equipo_norm}|{nombre_sin_min}"

                nombre_con_alias = aplicar_alias_jugador_temporada(nombre_sin_min, equipo_tabla_norm, TEMPORADA_ACTUAL)
                nombre_norm = normalizar_texto(nombre_con_alias)  

                info_jugador = { 
                    "nombre_original": nombre_sin_min, 
                    "nombre_norm": nombre_norm,
                    "puntos": puntos,
                    "equipo": equipo_tabla_norm,  
                    "equipo_norm": equipo_norm, 
                    "amarillas": amarillas,  
                    "rojas": rojas, 
                    "posicion": pos_fantasy,  
                }

                mapa_puntos[clave_ff] = info_jugador
        resultado[clave_partido] = mapa_puntos 
    return resultado  


def obtener_nombres_partido(html_partido)->tuple[str,str]:  #local, visitatne de FBRef
    soup = BeautifulSoup(html_partido, "lxml")  
    tag_title = soup.find("title").get_text()

    try: 
        equipo_local = tag_title.split(" vs. ")[0] 
        equipo_visitante = tag_title.split(" vs. ")[1].split(" Match")[0] 
    except Exception:
        equipo_local = "Local" 
        equipo_visitante = "Visitante"
    return equipo_local, equipo_visitante 


def obtener_fecha_partido(html_partido):  # fbref dd/mm/YYYY
    soup = BeautifulSoup(html_partido, "lxml")  
    div_scorebox = soup.find("div", class_="scorebox_meta")  
    if not div_scorebox:  
        return None

    span_fecha = div_scorebox.find("span", class_="venuetime")
    if not span_fecha: 
        return None  

    fecha_raw = span_fecha.get("data-venue-date") 
    if not fecha_raw:
        return None

    try:  
        dt = datetime.strptime(fecha_raw, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return None 


def _extraer_titulares_y_nombres_local(soup):
    divs_alineacion = soup.find_all("div", class_="lineup")
    titulares = []  
    nombres_local = []  

    if divs_alineacion:
        for div_lineup in divs_alineacion:
            jugadores = div_lineup.find_all("a")
            nombres_equipo = [] 
            for jugador in jugadores:  
                texto_jugador = jugador.get_text().strip()
                texto_jugador = limpiar_minuto(texto_jugador)
                nombres_equipo.append(texto_jugador)
            nombres_equipo = nombres_equipo[:11]
            titulares.extend(nombres_equipo) 

        equipo_local = divs_alineacion[0].find_all("a")  # Sale antes el equipo local
        for jugador in equipo_local:
            txt = jugador.get_text().strip()
            txt = limpiar_minuto(txt)
            nombres_local.append(txt)
    return titulares, nombres_local

def _parsear_tablas_partido(soup, equipo_local, equipo_visitante):
    '''
    {
    "summary":  { "nombre_jugador_norm": fila_summary, "nombre_jugador_norm2": fila_summary2,... },
    "passing":  { "nombre_jugador_norm": fila_passing, ... },
    "defense":  { "nombre_jugador_norm": fila_defense, ... },
    "possession":{ ... },
    "misc":     { ... },
    "keepers":  { ... },
    }
    '''
    tablas_por_tipo = {}  
    tipos = ["summary", "passing", "defense", "possession", "misc", "keepers"]  # Define la lista de tipos de tabla de stats que se quieren extraer del HTML.


    for tipo in tipos:
        jugadores_tipo = {}
        
        if tipo == "keepers":
            tablas = soup.find_all("table", id=re.compile(r"stats_.*_keepers")) 
            for tabla in soup.find_all("table"):
                tid = tabla.get("id") or ""
                if "keeper_stats_" in tid and tabla not in tablas:
                    tablas.append(tabla)
        else:
            tablas = soup.find_all("table", id=re.compile(f"stats_.*_{tipo}"))


        for tabla_html in tablas:
            jugadores_tabla = parsear_tabla_fbref(tabla_html, equipo_local, equipo_visitante, tipo)
            for clave_jugador, fila_jugador in jugadores_tabla.items():  #key:nombre normalizado de jugador // value: filas de stats
                jugadores_tipo[clave_jugador] = fila_jugador  

        tablas_por_tipo[tipo] = jugadores_tipo
    return tablas_por_tipo

# =========================
# Matching FBref - Fantasy
# =========================

def _generar_propuestas(resumen_summary, fantasy_partido, local_norm, visit_norm, nombres_local):
    '''
    resumen_summary: dict {nombre_fb_norm -> fila_summary} de FBref.
    fantasy_partido: dict con todos los jugadores Fantasy de ese partido.
    local_norm, visit_norm: nombres normalizados de los equipos.
    nombres_local: lista de nombres “humanos” del once + banquillo del local.
    SALIDA:propuestas-> lista de dicts, una por jugador FBref
    '''
    propuestas = [] 
    for nombre_fb_norm, fila_sum in resumen_summary.items():
        nombre_fb = str(fila_sum.get("Player", "")).strip()
        nombre_fb = limpiar_minuto(nombre_fb) 

        es_local = any(nombre_local == nombre_fb for nombre_local in nombres_local)
        equipo_fb_norm = local_norm if es_local else visit_norm

        minutos = to_int(fila_sum.get("Min", 0))
        pos_raw = str(fila_sum.get("Pos", "MC")).split(",")[0].strip()
        pos_val = mapear_posicion(pos_raw)

        candidatos_equipo = {} #Separo por equipos
        for clave, info in fantasy_partido.items():
            if info.get("equipo_norm") == equipo_fb_norm:
                candidatos_equipo[clave] = info

        nombres_fantasy_norm = [info["nombre_norm"] for info in candidatos_equipo.values()] 
        nombre_html_norm = nombre_fb_norm

        mejor_norm, mejor_score = obtener_match_nombre(
            nombre_html_norm, 
            nombres_fantasy_norm,
            equipo_norm=equipo_fb_norm,
        )


        if mejor_norm is None or mejor_score < UMBRAL_MATCH: 
            # plan B usar WRatio
            mejor_basico = rf_process.extractOne(  
                nombre_html_norm,  
                nombres_fantasy_norm,
                scorer=rf_fuzz.WRatio, 
            )
            if mejor_basico is not None: 
                candidato_norm, score_basico, _ = mejor_basico
                if score_basico >= UMBRAL_MATCH:
                    mejor_norm = candidato_norm 
                    mejor_score = score_basico

        mejor_original = None 
        if mejor_norm is not None:
          for info in candidatos_equipo.values():
                if info["nombre_norm"] == mejor_norm:  
                    mejor_original = info["nombre_original"] 
                    break 

        propuesta = {  
            "clave_fbref": nombre_fb_norm,
            "nombre_fb": nombre_fb, 
            "nombre_fb_norm": nombre_fb_norm, 
            "equipo_fb_norm": equipo_fb_norm,
            "minutos": minutos,
            "posicion": pos_val,
            "mejor_norm": mejor_norm,  
            "mejor_original": mejor_original, 
            "score": mejor_score, 
        }
        propuestas.append(propuesta) 
    return propuestas  

def _agrupar_propuestas_por_norm(propuestas, jugadores_por_apellido_equipo):
    propuestas_por_norm = {} 

    for propuesta in propuestas: 
        nombre_norm = propuesta["mejor_norm"]
        equipo_fb_norm = propuesta["equipo_fb_norm"]
        pos_val = propuesta["posicion"] 
        score = propuesta["score"]

        if not nombre_norm:
            continue 

        clave_norm = construir_clave_norm(nombre_norm, equipo_fb_norm, pos_val, jugadores_por_apellido_equipo)

        if score < UMBRAL_MATCH: 
            apellido = nombre_norm.split()[-1]  # Apellido
            clave_ap = (apellido, equipo_fb_norm) 
            lista_fantasy_mismo_ap = jugadores_por_apellido_equipo.get(clave_ap, [])  
            hay_unico_candidato = len(lista_fantasy_mismo_ap) == 1  # Caso no ambiguo
            if not hay_unico_candidato:  
                continue  

        if clave_norm not in propuestas_por_norm: 
            propuestas_por_norm[clave_norm] = []
        propuestas_por_norm[clave_norm].append(propuesta)  
    return propuestas_por_norm  


def _resolver_matching(propuestas, jugadores_por_apellido_equipo, fantasy_por_norm):
    asignacion_fbref_a_fantasy = {} 
    propuestas_por_norm = _agrupar_propuestas_por_norm(propuestas, jugadores_por_apellido_equipo) 

    for clave_norm, lista_props in propuestas_por_norm.items():
        candidatos_ff = fantasy_por_norm.get(clave_norm, [])  
        if not candidatos_ff: 
            continue

        lista_props_ordenada = sorted(lista_props, key=lambda p: p["minutos"], reverse=True) 
        candidatos_ff_ordenados = sorted(candidatos_ff, key=lambda x: x["puntos"], reverse=True)

        if len(candidatos_ff_ordenados) == 1 and len(lista_props_ordenada) > 1:  # 1 jugador y varios candidatos
            candidato = candidatos_ff_ordenados[0]  #
            info_ff = candidato["info"] 
            nombre_ff_norm = info_ff["nombre_norm"]  
            apellido_ff = nombre_ff_norm.split()[-1] 
            
            mejor_prop = None  
            mejor_score_local = -1.0 
            for p in lista_props_ordenada:
                mejor_norm_p = p.get("mejor_norm") 
                score_p = p.get("score") or 0.0  
                if not mejor_norm_p:  
                    continue  
                apellido_p = mejor_norm_p.split()[-1]  
                if apellido_p == apellido_ff and score_p > mejor_score_local:  # Si el apellido coincide con el del candidato Fantasy y el score supera al mejor score local.
                    mejor_prop = p 
                    mejor_score_local = score_p

            if mejor_prop is None: 
                mejor_prop = max(lista_props_ordenada, key=lambda p: p.get("score") or 0.0)

            clave_fbref = mejor_prop["clave_fbref"] 
            asignacion_fbref_a_fantasy[clave_fbref] = candidato["clave_ff"] 
        else:  
           for i in range(min(len(lista_props_ordenada), len(candidatos_ff_ordenados))):
                propuesta = lista_props_ordenada[i]
                candidato = candidatos_ff_ordenados[i]
                clave_fbref = propuesta["clave_fbref"]
                clave_ff = candidato["clave_ff"]
                asignacion_fbref_a_fantasy[clave_fbref] = clave_ff


    debug_matching_por_fbref = {} 
    for propuesta in propuestas:  
        clave_fbref = propuesta["clave_fbref"]  
        mejor_norm = propuesta["mejor_norm"] 
        equipo_fb_norm = propuesta["equipo_fb_norm"]  
        pos_val = propuesta["posicion"] 
        score = propuesta["score"] 
        clave_ff_asignada = asignacion_fbref_a_fantasy.get(clave_fbref) 

        clave_norm = construir_clave_norm(mejor_norm, equipo_fb_norm, pos_val, jugadores_por_apellido_equipo)

        debug_matching_por_fbref[clave_fbref] = {
            "mejor_norm": mejor_norm,
            "equipo_fb_norm": equipo_fb_norm, 
            "pos_val": pos_val,
            "score": score, 
            "clave_norm": clave_norm, 
            "clave_ff_asignada": clave_ff_asignada, 
        }
    return asignacion_fbref_a_fantasy, debug_matching_por_fbref  


fantasy_por_norm_global = {} 
def _construir_bd_partido(propuestas,tablas_por_tipo,asignacion_fbref_a_fantasy,debug_matching_por_fbref,fantasy_partido,titulares,local_norm,visit_norm,jornada,fecha_partido,):
    bd_partido = {} 

    for propuesta in propuestas: 
        clave_fbref = propuesta["clave_fbref"] 
        nombre_fb = propuesta["nombre_fb"] 
        nombre_fb_norm = propuesta["nombre_fb_norm"]
        equipo_fb_norm = propuesta["equipo_fb_norm"]
        minutos = propuesta["minutos"] 
        pos_val = propuesta["posicion"] 

        equipo_rival_norm = visit_norm if equipo_fb_norm == local_norm else local_norm 
        clave_ff = asignacion_fbref_a_fantasy.get(clave_fbref)  

        if clave_ff is not None: 
            clave_registro = f"{clave_ff}|{equipo_fb_norm}|{pos_val}" 
        else: 
            clave_registro = f"{nombre_fb_norm}|{equipo_fb_norm}|{minutos}|{pos_val}"
            
        if clave_registro not in bd_partido: 
            fila_nueva = {col: np.nan for col in COLUMNAS_MODELO}  

            fila_nueva["temporada"] = TEMPORADA_ACTUAL  
            fila_nueva["jornada"] = jornada 
            fila_nueva["fecha_partido"] = fecha_partido  
            fila_nueva["player"] = nombre_fb 
            fila_nueva["posicion"] = pos_val  
            fila_nueva["Equipo_propio"] = equipo_fb_norm 
            fila_nueva["Equipo_rival"] = equipo_rival_norm 
            fila_nueva["local"] = 1 if equipo_fb_norm == local_norm else 0  
            fila_nueva["Titular"] = 1 if nombre_fb in titulares else 0  
            fila_nueva["Min_partido"] = minutos
            fila_nueva["Goles_en_contra"] = np.nan
            fila_nueva["Porcentaje_paradas"] = np.nan 
            fila_nueva["roles"] = []  
            bd_partido[clave_registro] = fila_nueva  

        fila_salida = bd_partido[clave_registro] 
        rellenar_stats_fila(fila_salida, tablas_por_tipo, clave_fbref, pos_val) 
        puntos = 6767  
        if clave_ff is not None:  
            puntos = fantasy_partido.get(clave_ff, {}).get("puntos", 6767) 

        fila_salida["puntosFantasy"] = puntos 
    return bd_partido

def procesar_partido(html_partido, mapa_fantasy_partido, idx_partido, jornada):
    global fantasy_por_norm_global  

    soup = BeautifulSoup(html_partido, "lxml")
    fecha_partido = obtener_fecha_partido(html_partido)
    equipo_local, equipo_visitante = obtener_nombres_partido(html_partido)
    local_norm = normalizar_equipo_temporada(equipo_local)
    visit_norm = normalizar_equipo_temporada(equipo_visitante)
    fantasy_partido = mapa_fantasy_partido 
    titulares, nombres_local = _extraer_titulares_y_nombres_local(soup)

    tablas_por_tipo = _parsear_tablas_partido(soup, equipo_local, equipo_visitante)
    resumen_summary = tablas_por_tipo.get("summary", {})
    propuestas = _generar_propuestas(resumen_summary,fantasy_partido,local_norm,visit_norm,nombres_local)

    jugadores_por_apellido_equipo, fantasy_por_norm = construir_fantasy_por_norm(fantasy_partido)
    fantasy_por_norm_global = fantasy_por_norm 
    
    asignacion_fbref_a_fantasy, debug_matching_por_fbref = _resolver_matching(propuestas,jugadores_por_apellido_equipo,fantasy_por_norm)
    bd_partido = _construir_bd_partido(
        propuestas,
        tablas_por_tipo,
        asignacion_fbref_a_fantasy,
        debug_matching_por_fbref,
        fantasy_partido,
        titulares,
        local_norm,
        visit_norm,
        jornada,
        fecha_partido,
    )

    usadas_ff = set(asignacion_fbref_a_fantasy.values())
    bd_partido = completar_fantasy_sin_match( 
        bd_partido,
        fantasy_partido,
        usadas_ff,
        local_norm,
        visit_norm,
        fecha_partido,
        jornada,
        TEMPORADA_ACTUAL,
    )

    df_partido = pd.DataFrame.from_dict(bd_partido, orient="index")
    df_partido = postprocesar_df_partido(df_partido)
    df_partido = asignar_roles_df(df_partido, ROLES_DESTACADOS)
    imprimir_mal_6767(df_partido, columna="puntosFantasy")
    return df_partido, equipo_local, equipo_visitante

def procesar_y_guardar_partido(jornada: int, idx_partido: int, fantasy_por_partido):
    sj = str(jornada) 
    carpeta_html_j, carpeta_csv_j = obtener_rutas_jornada(CARPETA_HTML, CARPETA_CSV, jornada)  # Llama a obtener_rutas_jornada (commons) para obtener o crear las carpetas específicas de HTML y CSV para esta jornada concreta.
    ruta_html = os.path.join(carpeta_html_j, f"p{idx_partido}.html")
    html_partido = leer_html(ruta_html, logger=logger) 
    if not html_partido: 
        print(f"⚠️ No se pudo leer {ruta_html}")
        return None, None, None 

    equipo_local, equipo_visitante = obtener_nombres_partido(html_partido) 
    local_norm = normalizar_equipo_temporada(equipo_local) 
    visit_norm = normalizar_equipo_temporada(equipo_visitante)
    clave_partido = f"{local_norm}-{visit_norm}" 
    fantasy_partido = fantasy_por_partido.get(clave_partido, {})
    df_partido, eq_loc_csv, eq_vis_csv = procesar_partido(html_partido,fantasy_partido,idx_partido,jornada)

    if df_partido is None or df_partido.empty: 
        print("⚠️ DataFrame vacío para este partido")
        return None, None, None


    eq_loc_norm = normalizar_texto(eq_loc_csv)
    eq_vis_norm = normalizar_texto(eq_vis_csv)
    nombre_csv = f"p{idx_partido}_{eq_loc_norm}-{eq_vis_norm}.csv"

    ruta_salida = os.path.join(carpeta_csv_j, nombre_csv) 

    df_partido.to_csv( ruta_salida,index=False,encoding="utf-8-sig")
    print(f"✅ CSV generado: J{sj} P{idx_partido} {eq_loc_norm}-{eq_vis_norm}") 
    return df_partido, eq_loc_csv, eq_vis_csv  


def procesar_jornada(jornada: int): 
    sj = str(jornada) 
    print(f"\n=== JORNADA {sj} (temp {TEMPORADA_ACTUAL}) ===")

    fantasy_por_partido = obtener_fantasy_jornada(sj) 
    jugadores_no_analizados = []  
    for idx_partido in range(1, 10 + 1):  
        df_partido, eq_loc_csv, eq_vis_csv = procesar_y_guardar_partido(jornada, idx_partido, fantasy_por_partido)

        if df_partido is not None and not df_partido.empty: 
            df_banquillo = contar_tarjetas_banquillo(df_partido) 
            if not df_banquillo.empty:
                jugadores_no_analizados.extend(df_banquillo.to_dict("records"))

    if jugadores_no_analizados:  
        print("\nJugadores con tarjetas y 0 minutos (banquillo):")  
        for jugador in jugadores_no_analizados: 
            print( 
                f"- {jugador.get('player','')} ({jugador.get('Equipo_propio','')}) | "
                f"Amarillas: {jugador.get('Amarillas',0)}, "
                f"Rojas: {jugador.get('Rojas',0)} [banquillo]"
            )


def procesar_rango_jornadas(jornada_inicio: int, jornada_fin: int):
    for j in range(jornada_inicio, jornada_fin + 1):  
        procesar_jornada(j)  

def analizar_temporada(codigo_temporada: str, j_ini: int = 1, j_fin: int = 38):
    global TEMPORADA_ACTUAL, CARPETA_HTML, CARPETA_CSV 
    TEMPORADA_ACTUAL = codigo_temporada 
    CARPETA_HTML, CARPETA_CSV = build_rutas_temporada(codigo_temporada) 

    print(f"\n=== ANALIZANDO TEMPORADA {codigo_temporada} ===")  
    procesar_rango_jornadas(j_ini, j_fin)  

def procesar_un_partido(jornada: int, idx_partido: int): 
    sj = str(jornada)
    fantasy_por_partido = obtener_fantasy_jornada(sj) 
    df_partido, _, _ = procesar_y_guardar_partido( jornada, idx_partido, fantasy_por_partido)
    if df_partido is None or df_partido.empty: 
        print("⚠️ DataFrame vacío para este partido")  

if __name__ == "__main__":
    inicio = time.perf_counter()  

    # Generar y guardar el calendario en JSON
    obtener_calendario()

    #analizar_temporada("23_24", 1, 38)  
    #analizar_temporada("24_25", 12, 14) 
    #analizar_temporada("25_26", 1, 17) 
    
    fin = time.perf_counter() 
    duracion = fin - inicio  
    print(f"\nTiempo total de ejecución: {duracion:.2f} segundos")