from rapidfuzz import process as rf_process, fuzz as rf_fuzz
from main.scrapping.commons import *
from main.scrapping.alias import UMBRAL_MATCH


def generar_propuestas(resumen_summary, fantasy_partido, local_norm, visit_norm, nombres_local):
    """
        resumen_summary: dict {nombre_fb_norm -> fila_summary} de FBref.
        fantasy_partido: dict con todos los jugadores Fantasy de ese partido.
        local_norm: nombre normalizado del equipo local.
        visit_norm: nombre normalizado del equipo visitante.
        nombres_local: lista de nombres del once + banquillo 
    
    Returns:
        propuestas: lista de dicts, una por jugador FBref con info del matching.
    """
    propuestas = [] 
    for nombre_fb_norm, fila_sum in resumen_summary.items():
        nombre_fb = str(fila_sum.get("Player", "")).strip()
        nombre_fb = limpiar_minuto(nombre_fb) 

        es_local = any(nombre_local == nombre_fb for nombre_local in nombres_local)
        equipo_fb_norm = local_norm if es_local else visit_norm

        minutos = to_int(fila_sum.get("Min", 0))
        pos_raw = str(fila_sum.get("Pos", "MC")).split(",")[0].strip()
        pos_val = mapear_posicion(pos_raw)

        candidatos_equipo = {}
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


def agrupar_propuestas_por_norm(propuestas, jugadores_por_apellido_equipo):
    """
        -propuestas: lista de propuestas generadas por generar_propuestas.
        -jugadores_por_apellido_equipo: dict de jugadores agrupados por (apellido, equipo).
    
        propuestas_por_norm: dict {clave_norm -> lista de propuestas}.
    """
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
            apellido = nombre_norm.split()[-1]
            clave_ap = (apellido, equipo_fb_norm) 
            lista_fantasy_mismo_ap = jugadores_por_apellido_equipo.get(clave_ap, [])  
            hay_unico_candidato = len(lista_fantasy_mismo_ap) == 1
            if not hay_unico_candidato:  
                continue  

        if clave_norm not in propuestas_por_norm: 
            propuestas_por_norm[clave_norm] = []
        propuestas_por_norm[clave_norm].append(propuesta)  
    return propuestas_por_norm  


def resolver_matching(propuestas, jugadores_por_apellido_equipo, fantasy_por_norm):
    """
    Resuelve conflictos de matching entre múltiples propuestas.
    
    Args:
        propuestas: lista de propuestas de matching.
        jugadores_por_apellido_equipo: dict de jugadores agrupados.
        fantasy_por_norm: dict con jugadores Fantasy normalizados.
    
    Returns:
        tuple: (asignacion_fbref_a_fantasy, debug_matching_por_fbref)
            - asignacion_fbref_a_fantasy: dict {clave_fbref -> clave_ff}
            - debug_matching_por_fbref: dict con información de debug del matching
    """
    asignacion_fbref_a_fantasy = {} 
    propuestas_por_norm = agrupar_propuestas_por_norm(propuestas, jugadores_por_apellido_equipo) 

    for clave_norm, lista_props in propuestas_por_norm.items():
        candidatos_ff = fantasy_por_norm.get(clave_norm, [])  
        if not candidatos_ff: 
            continue

        lista_props_ordenada = sorted(lista_props, key=lambda p: p["minutos"], reverse=True) 
        candidatos_ff_ordenados = sorted(candidatos_ff, key=lambda x: x["puntos"], reverse=True)

        if len(candidatos_ff_ordenados) == 1 and len(lista_props_ordenada) > 1:
            candidato = candidatos_ff_ordenados[0]
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
                if apellido_p == apellido_ff and score_p > mejor_score_local:
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
