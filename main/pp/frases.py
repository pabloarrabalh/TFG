DESCRIPCIONES_POS = {
    # Rachas de puntos / forma
    "pf_last5_mean": "viene en buena racha de puntos fantasy",
    "pf_last3_mean": "viene con una dinámica reciente de puntos muy positiva",
    "pf_media_historica": "su nivel medio de puntos fantasy le respalda",
    "form_vs_class_keeper_3": "últimamente está rindiendo mejor de lo que se esperaba por su nivel",
    "form_vs_class_keeper3": "últimamente está rindiendo mejor de lo que se esperaba por su nivel",
    "form_vs_class_keeper": "su tendencia reciente va por encima de lo que marca su trayectoria",

    # Apuestas / contexto partido
    "p_win_minus_loss": "su equipo llega como claro favorito o con el partido bastante controlado",
    "p_loss_soft": "se espera un partido duro donde puede tener mucho trabajo bajo palos",
    "partido_muy_desequilibrado": "el partido se presenta muy desnivelado y eso marca el guion",

    # Ataque rival (xG/goles/tiros)
    "xg_last3_mean_rival": "el rival viene generando ocasiones de calidad en los últimos partidos",
    "xg_last5_mean_rival": "se enfrenta a un rival que está generando mucho peligro de forma sostenida",
    "gf_last5_mean_rival": "se mide a un rival que llega con bastante gol en las últimas jornadas",
    "shots_on_target_ratio_rival": "el rival acostumbra a acabar muchas jugadas con tiros a puerta",
    "shots_on_target_ratio_rival_last3": "el rival viene tirando mucho a puerta en los últimos partidos",

    # Goles encajados / dificultad de los tiros
    "gc_per90_last3": "en la racha corta está gestionando bien los goles encajados por partido",
    "gc_per90_last5": "en los últimos partidos está controlando los goles encajados por partido",
    "psxg_gc_diff_last3_mean": "últimamente está sacando más de lo que debería según la calidad de los tiros",
    "psxg_gc_diff_last5_mean": "en una racha más larga está rindiendo mejor de lo que marcan las ocasiones recibidas",
    "psxg_per90_last3": "en los últimos partidos le están llegando tiros especialmente exigentes",
    "psxg_per90_last5": "en una ventana más larga ha tenido que lidiar con tiros de bastante dificultad",

    # Bombardeo y volumen de trabajo
    "bombardeo_last3_mean": "sus últimos 3 partidos han sido de mucho trabajo bajo palos",
    "bombardeo_last5_mean": "lleva tiempo acumulando partidos con bastante trabajo bajo palos",
    "saves_last3_mean": "lleva varios partidos sumando muchas paradas por encuentro",
    "saves_last5_mean": "su media de paradas en los últimos partidos es muy alta",
    "saves_last3_mean_extra": "en la racha más reciente se está luciendo con varias paradas por partido",
    "saves_last5_mean_extra": "en la racha larga viene aportando muchas paradas",

    # Porcentaje de paradas / porterías a cero
    "savepct_hist": "su porcentaje de paradas histórico es muy sólido",
    "savepct_last3_mean": "en los últimos partidos está dejando un porcentaje de paradas muy alto",
    "savepct_last5_mean": "en los últimos 5 partidos su porcentaje de paradas está siendo muy relevante",
    "clean_last3_ratio": "en los últimos encuentros está sumando bastantes porterías a cero",
    "clean_last3_ratio_extra": "en la racha más reciente sus porterías a cero pesan bastante",
    "clean_last5_ratio": "en una ventana de 5 partidos está dejando la portería a cero con frecuencia",
    "clean_last5_ratio_extra": "en una racha algo más larga acumula varias porterías a cero",

    # Rol/calidad global
    "score_save_pct": "sus números bajo palos son de portero muy fiable",
    "score_porterias_cero": "es un portero que suele dejar la portería a cero",
    "elite_keeper": "el modelo le considera un portero de nivel élite",
    "is_top5_porterias_cero": "está entre los mejores de la liga en porterías a cero",
    "is_top5_save_pct": "está entre los mejores de la liga en porcentaje de paradas",
    "is_top5_en_algo": "destaca claramente en métricas defensivas importantes",

    # Boosts y mezclas portero x rival
    "score_pc_boost": "suele mantener la portería a cero incluso ante ataques fuertes",
    "score_sp_boost": "responde muy bien cuando el rival llega con peligro",
    "rol_x_xg_rival": "su nivel y el volumen de ocasiones del rival le dan opciones de lucirse",
    "rol_x_xg_rival_boost": "tiene un escenario perfecto para destacar ante un rival que genera mucho",
    "ataque_top_rival": "se enfrenta a un ataque top, ideal para sumar por volumen de acciones",
    "ataque_top_rival_x_elite": "es un duelo de portero élite contra ataque de máximo nivel",

    # Mix xG/goles rival con defensa propia
    "xg_rival_x_savepct": "el peligro del rival y su capacidad de parada se combinan a su favor",
    "xg_rival_x_gc_per90": "el xG del rival y cómo viene encajando su equipo dibujan un buen escenario de trabajo",
    "gf_rival_last5_x_gc_per90": "el rival llega con gol y su defensa viene encajando, partido propicio para sumar",

    # Titularidad
    "titular_last3_ratio": "viene siendo titular con continuidad en los últimos partidos",
    "titular_last5_ratio": "su rol de titular está muy consolidado en esta racha",

    # Contexto extra
    "local": "juega en casa, algo que también pesa en el pick",
}

DESCRIPCIONES_NEG = {
    # Rachas de puntos / forma
    "pf_last5_mean": "su racha reciente de puntos fantasy es floja",
    "pf_last3_mean": "sus últimos 3 partidos no están siendo especialmente buenos en puntos",
    "pf_media_historica": "su nivel medio de puntos fantasy no acompaña tanto",
    "form_vs_class_keeper_3": "últimamente está rindiendo por debajo de lo que se esperaba por su nivel",
    "form_vs_class_keeper3": "últimamente está rindiendo por debajo de lo que se esperaba por su nivel",
    "form_vs_class_keeper": "su tendencia reciente va por debajo de lo que marca su trayectoria",

    # Apuestas / contexto partido
    "p_win_minus_loss": "su equipo no llega tan favorito y el guion del partido le complica sumar",
    "p_loss_soft": "no se espera un partido tan exigente como para que pueda lucirse mucho",
    "partido_muy_desequilibrado": "el partido se presenta muy desnivelado en su contra",

    # Ataque rival (xG/goles/tiros)
    "xg_last3_mean_rival": "el rival no viene generando tantas ocasiones claras en los últimos partidos",
    "xg_last5_mean_rival": "el rival no está generando tanto peligro en esta racha",
    "gf_last5_mean_rival": "se mide a un rival con menos gol del que podría venirle bien para lucirse",
    "shots_on_target_ratio_rival": "el rival no acostumbra a acabar tantas jugadas con tiros a puerta",
    "shots_on_target_ratio_rival_last3": "el rival no viene generando tantos tiros claros últimamente",

    # Goles encajados / dificultad de los tiros
    "gc_per90_last3": "en la racha corta está encajando demasiados goles por partido",
    "gc_per90_last5": "en los últimos partidos está recibiendo más goles de los deseados",
    "psxg_gc_diff_last3_mean": "últimamente no está salvando tanto como podría según las ocasiones que recibe",
    "psxg_gc_diff_last5_mean": "en una racha más larga está encajando más de lo que indican las ocasiones",
    "psxg_per90_last3": "en los últimos partidos los tiros que recibe no son tan exigentes",
    "psxg_per90_last5": "en una ventana más larga la dificultad de los tiros no le exige tanto",

    # Bombardeo y volumen de trabajo
    "bombardeo_last3_mean": "sus últimos 3 partidos no le han exigido tanto trabajo bajo palos",
    "bombardeo_last5_mean": "lleva una racha con menos trabajo del que podría hacerle brillar",
    "saves_last3_mean": "no viene sumando tantas paradas en los últimos encuentros",
    "saves_last5_mean": "su media de paradas en los últimos partidos es más discreta",
    "saves_last3_mean_extra": "en la racha más reciente no se está viendo tan exigido",
    "saves_last5_mean_extra": "en la racha larga no está acumulando tantas intervenciones",

    # Porcentaje de paradas / porterías a cero
    "savepct_hist": "su porcentaje de paradas histórico no es especialmente brillante",
    "savepct_last3_mean": "en los últimos partidos su porcentaje de paradas no está siendo tan bueno",
    "savepct_last5_mean": "en los últimos 5 partidos su porcentaje de paradas baja algo el optimismo",
    "clean_last3_ratio": "en los últimos encuentros no está dejando tantas porterías a cero",
    "clean_last3_ratio_extra": "en la racha más reciente le cuesta más salir a cero",
    "clean_last5_ratio": "en una ventana de 5 partidos no acumula tantas porterías a cero",
    "clean_last5_ratio_extra": "en una racha algo más larga le está costando más mantener la portería a cero",

    # Rol/calidad global
    "score_save_pct": "sus números bajo palos no están siendo especialmente brillantes",
    "score_porterias_cero": "no está destacando precisamente por dejar la portería a cero",
    "elite_keeper": "no está mostrando números de portero élite en este tramo",
    "is_top5_porterias_cero": "ya no está tan arriba en porterías a cero como otras opciones",
    "is_top5_save_pct": "su porcentaje de paradas no está tan arriba como antes",
    "is_top5_en_algo": "no destaca tanto en métricas defensivas importantes ahora mismo",

    # Boosts y mezclas portero x rival
    "score_pc_boost": "ante ataques fuertes no está consiguiendo tantas porterías a cero",
    "score_sp_boost": "cuando el rival llega con peligro le está costando más brillar",
    "rol_x_xg_rival": "la combinación de su nivel y el contexto de ocasiones no le favorece tanto",
    "rol_x_xg_rival_boost": "el contexto del partido no le invita tanto a destacar",
    "ataque_top_rival": "el ataque rival puede castigarle más de la cuenta",
    "ataque_top_rival_x_elite": "el duelo contra un ataque top puede castigarle si no está fino",

    # Mix xG/goles rival con defensa propia
    "xg_rival_x_savepct": "el peligro del rival y sus números de paradas no terminan de cuadrar a su favor",
    "xg_rival_x_gc_per90": "el xG del rival y cómo viene encajando su equipo le pueden penalizar",
    "gf_rival_last5_x_gc_per90": "el rival llega con gol y su defensa viene sufriendo, puede salirle caro",

    # Titularidad
    "titular_last3_ratio": "su continuidad como titular no está siendo tan clara",
    "titular_last5_ratio": "su rol como titular ha sido más inestable en esta racha",

    # Contexto extra
    "local": "el hecho de jugar en casa no le está aportando tanto en este caso",
}


def describir_feature_generico(nombre: str, positivo: bool) -> str:
    base = f"[ALERTA🔴 ] La feature **{nombre}**, relacionada con su rendimiento y el contexto del partido"
    if positivo:
        return base + " le ayuda en este pick"
    else:
        return base + " le perjudica en este pick"

def generar_texto_xai(explicacion_shap: dict) -> str:
    """
    Recibe el dict con top_pos/top_neg (cada uno con feature, shap)
    y devuelve texto XAI usando diccionarios positivo/negativo
    según el signo del SHAP.
    """
    if not explicacion_shap or explicacion_shap.get("error"):
        return "No se ha podido generar una explicación clara para este pick."

    frases = []

    # Positivas (SHAP > 0)
    for f in explicacion_shap.get("top_pos", []):
        nombre = f["feature"]
        valor = float(f["shap"])
        desc = DESCRIPCIONES_POS.get(
            nombre,
            describir_feature_generico(nombre, positivo=True)
        )
        frases.append(
            f"- SUMA: {desc} (impacto +{valor:.2f} puntos)."
        )

    # Negativas (SHAP < 0)
    for f in explicacion_shap.get("top_neg", []):
        nombre = f["feature"]
        valor = float(f["shap"])
        impacto = abs(valor)
        desc = DESCRIPCIONES_NEG.get(
            nombre,
            describir_feature_generico(nombre, positivo=False)
        )
        frases.append(
            f"- PENALIZA: {desc} (impacto -{impacto:.2f} puntos)."
        )

    if not frases:
        return "Para este pick ninguna feature destaca claramente por encima del resto."

    return "Motivo del pick:\n" + "\n".join(frases)
