import os
import re
import unicodedata
from collections import defaultdict

from numpy import nan
import pandas as pd
from bs4 import NavigableString
from rapidfuzz import process, fuzz

from alias import *


# ==========================
# Lectura y rutas
# ==========================


def leer_html(ruta: str, logger=None) -> str:
    if not ruta:
        return ""

    if not os.path.exists(ruta):
        if logger is not None:
            logger.warning("No existe el HTML: %s", ruta)
        return ""

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()
    except Exception as e:
        if logger is not None:
            logger.warning("Error leyendo HTML %s: %s", ruta, e)
        return ""
    return contenido


def build_rutas_temporada(temporada: str):
    carpeta_html = os.path.join("main", "html", f"temporada_{temporada}")
    carpeta_csv = os.path.join("data", f"temporada_{temporada}")
    os.makedirs(carpeta_html, exist_ok=True)
    os.makedirs(carpeta_csv, exist_ok=True)
    return carpeta_html, carpeta_csv


def obtener_rutas_jornada(carpeta_html_base: str, carpeta_csv_base: str, jornada: int):
    sj = str(jornada)
    carpeta_html_j = os.path.join(carpeta_html_base, f"j{jornada}")
    carpeta_csv_j = os.path.join(carpeta_csv_base, f"jornada_{sj}")
    os.makedirs(carpeta_html_j, exist_ok=True)
    os.makedirs(carpeta_csv_j, exist_ok=True)
    return carpeta_html_j, carpeta_csv_j


def normalizar_texto(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)  # Tildes raras
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    texto = re.sub(r"[-.]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def normalizar_equipo(nombre_equipo: str) -> str:
    nombre_norm = normalizar_texto(nombre_equipo)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def normalizar_equipo_temporada(nombre: str) -> str:
    nombre_norm = normalizar_texto(nombre)
    return ALIAS_EQUIPOS.get(nombre_norm, nombre_norm)


def normalizar_puntos(valor):
    if valor in ["-", "–", "", None]:
        return 0
    try:
        return int(float(valor))
    except Exception:
        return 0


def limpiar_minuto(nombre):
    if not nombre:
        return nombre
    nombre = nombre.replace("+", "").replace("-", "").strip()
    nombre = re.sub(r"\s*\d+(?:\+\d+)?'?$", "", nombre).strip()
    return nombre


def extraer_nombre_jugador(td_nombre):
    textos = []
    for h in td_nombre.children:
        if isinstance(h, NavigableString):
            txt = h.strip()
            if txt:
                textos.append(txt)
    return " ".join(textos)


def _convertir_a_numero(valor):
    if isinstance(valor, pd.Series):
        valor = valor.iloc[0]
    if valor in (None, "", "-"):
        return nan

    texto = str(valor).split("\n")[0].replace("%", "").strip()
    num = pd.to_numeric(texto, errors="coerce")
    if pd.isna(num):
        return nan
    return float(num)


def to_float(valor):
    return _convertir_a_numero(valor)


def to_int(valor):
    v = _convertir_a_numero(valor)
    if pd.isna(v):
        return nan
    return int(round(v))


def limpiar_numero(valor):
    if isinstance(valor, pd.Series):
        valor = valor.iloc[0]
    if valor is None:
        return 0.0
    s = str(valor).split("\n")[0].replace("%", "").strip()
    if s in ["", "-", "nan", "NaN", "None"]:
        return 0.0
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def formatear_numero(valor):
    try:
        f = float(valor)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(valor)


def mapear_posicion(pos):
    pos = (pos or "MC").upper()
    return POSICION_MAP.get(pos, "MC")


def añadir_equipo_y_player_norm(df, col_equipo="Equipo_propio", col_player="player"):
    df["equipo_norm"] = df[col_equipo].apply(normalizar_equipo)
    df["player_norm"] = df[col_player].apply(normalizar_texto)
    return df


def normalizar_pos_clave(pos_val: str) -> str:
    # Para matching dentro del mismo equipo
    if pos_val == "PT":
        return "PT"
    if pos_val == "DT":
        return "MDT"
    if pos_val == "DF":
        return "MDF"
    if pos_val == "MC":
        return "MC"
    return pos_val


def es_apellido_conflictivo(nombre_normalizado_html, nombres_normalizados_equipo):
    partes = nombre_normalizado_html.split()
    if len(partes) != 1:
        return False

    apellido = partes[0]
    if apellido not in APELLIDOS_CRITICOS:
        return False

    jugadores_con_mismo_apellido = [
        nombre for nombre in nombres_normalizados_equipo
        if nombre.startswith(apellido)
    ]
    return len(jugadores_con_mismo_apellido) > 1


def obtener_match_nombre(nombre_html_norm, nombres_norm_equipo, equipo_norm=None, score_cutoff=85):
    """
    - Si hay nombre + apellido y el apellido es crítico, intenta match exacto
      por nombre dentro del equipo.
    - Si hay solo una palabra y no es apellido crítico, intenta heurísticas de
      prefix/suffix con un único candidato.
    - Si no se resuelve, usa process.extractOne con WRatio.
    - Devuelve (nombre_match, score) o (None, 0) si no se supera el score_cutoff.
    """
    if not nombres_norm_equipo:
        return None, 0

    partes = nombre_html_norm.split()

    # Caso nombre + apellido y apellido crítico
    if len(partes) == 2:
        nombre = partes[0]
        apellido = partes[1]

        if apellido in APELLIDOS_CRITICOS:
            candidatos_nombre = []
            for nombre_equipo in nombres_norm_equipo:
                if normalizar_texto(nombre_equipo) == nombre:
                    candidatos_nombre.append(nombre_equipo)

            if len(candidatos_nombre) == 1:
                unico = candidatos_nombre[0]
                return unico, 100

    # Caso solo una palabra
    if len(partes) == 1:
        palabra = partes[0]

        if palabra not in APELLIDOS_CRITICOS:
            candidatos = []
            for nombre_equipo in nombres_norm_equipo:
                if (
                    nombre_equipo.startswith(palabra)
                    or nombre_equipo.endswith(palabra)
                ):
                    candidatos.append(nombre_equipo)

            if len(candidatos) == 1:
                return candidatos[0], 95

    mejor, score, _ = process.extractOne(
        nombre_html_norm,
        nombres_norm_equipo,
        scorer=fuzz.WRatio,
    )

    if mejor and score >= score_cutoff:
        return mejor, score

    return None, 0


def nombre_a_mayus(nombre_norm):
    partes = str(nombre_norm).split()
    partes_capitalizadas = [p.capitalize() for p in partes]
    return " ".join(partes_capitalizadas)


def coincide_inicial_apellido(nombre1, nombre2):
    partes1 = nombre1.split()
    partes2 = nombre2.split()

    if len(partes1) < 2:
        return False
    if len(partes2) < 2:
        return False

    apellido1 = partes1[-1]
    apellido2 = partes2[-1]

    if apellido1 != apellido2:
        return False

    nombre1_pila = partes1[0]
    nombre2_pila = partes2[0]

    def es_abreviado(n):
        if len(n) <= 2:
            return True
        if n.endswith("."):
            return True
        return False

    if es_abreviado(nombre1_pila) and es_abreviado(nombre2_pila):
        return False

    if es_abreviado(nombre1_pila):
        return nombre1_pila[0] == nombre2_pila[0]

    if es_abreviado(nombre2_pila):
        return nombre2_pila[0] == nombre1_pila[0]

    return nombre1_pila == nombre2_pila


def normalizar_clave_html(nombre_raw, equipo_norm, jugadores_html):
    equipo_norm_n = normalizar_equipo(equipo_norm) if equipo_norm else None

    nombre_alias = normalizar_texto(nombre_raw)
    nombre_sin_alias = normalizar_texto(nombre_raw)

    if nombre_alias in jugadores_html:
        return nombre_alias
    if nombre_sin_alias in jugadores_html:
        return nombre_sin_alias
    return nombre_alias


def aplicar_alias_jugador_temporada(nombre: str, equipo_norm: str, temporada: str) -> str:
    alias_jug = get_alias_jugadores(temporada)

    equipo_norm = normalizar_texto(equipo_norm or "")
    mapa_equipo = alias_jug.get(equipo_norm, {})

    nombre_norm = normalizar_texto(nombre)

    alias_corto = mapa_equipo.get(nombre_norm)
    if alias_corto:
        return alias_corto
    return nombre


def construir_clave_norm(mejor_norm, equipo_norm, pos_val, jugadores_por_apellido_equipo):
    """
    - Obtiene el apellido de mejor_norm y mira en jugadores_por_apellido_equipo
      cuántos jugadores Fantasy hay para (apellido, equipo).
    - Si no hay ningún jugador para ese (apellido, equipo), clave_norm = (mejor_norm, equipo_norm).
    - Si el apellido NO es crítico o no está duplicado, clave_norm = (mejor_norm, equipo_norm).
    - Si el apellido es crítico y está duplicado, incluye también la posición
      normalizada: clave_norm = (mejor_norm, equipo_norm, pos_clave).
    """
    if not mejor_norm:
        return None

    apellido = mejor_norm.split()[-1]
    clave_ap = (apellido, equipo_norm)
    lista_fantasy_mismo_ap = jugadores_por_apellido_equipo.get(clave_ap, [])
    hay_duplicados = (
        apellido in APELLIDOS_CRITICOS and len(lista_fantasy_mismo_ap) > 1
    )

    if not lista_fantasy_mismo_ap:
        return (mejor_norm, equipo_norm)
    if not hay_duplicados:
        return (mejor_norm, equipo_norm)
    pos_clave = normalizar_pos_clave(pos_val)
    return (mejor_norm, equipo_norm, pos_clave)


def construir_fantasy_por_norm(fantasy_partido: dict):
    """
    - jugadores_por_apellido_equipo:dict[(apellido, equipo_norm)] 
    
    (nombre_norm, equipo_norm)            si no hay conflicto,
    (nombre_norm, equipo_norm, pos_clave) si el apellido es crítico y hay duplicados.
    """
    agrupado = defaultdict(list)
    for clave_ff, info in fantasy_partido.items():
        nombre_norm = info.get("nombre_norm")
        equipo_norm = info.get("equipo_norm")
        pos_val = info.get("posicion", "MC")

        if not nombre_norm or not equipo_norm:
            continue

        minutos = info.get("minutos", 0)
        puntos = info.get("puntos", 0)

        clave_basica = (nombre_norm, equipo_norm)
        agrupado[clave_basica].append(
            {
                "clave_ff": clave_ff,
                "info": info,
                "min": minutos,
                "puntos": puntos,
                "posval": pos_val,
            }
        )

    # Colapsar duplicados por (nombre_norm, equipo_norm)
    colapsado = {}
    for clave_basica, entradas in agrupado.items():
        con_minutos = [e for e in entradas if (e["min"] or 0) > 0]
        if con_minutos:
            mejor = max(con_minutos, key=lambda e: e["min"] or 0)
        else:
            mejor = max(entradas, key=lambda e: e["puntos"] or 0)
        colapsado[clave_basica] = mejor

    jugadores_por_apellido_equipo = defaultdict(list)
    fantasy_por_norm = {}

    # Construir jugadores_por_apellido_equipo
    for (nombre_norm, equipo_norm), entrada in colapsado.items():
        clave_ff = entrada["clave_ff"]
        info = entrada["info"]

        apellido = nombre_norm.split()[-1]
        jugadores_por_apellido_equipo[(apellido, equipo_norm)].append(
            (clave_ff, info)
        )

    # Construir fantasy_por_norm a partir de jugadores_por_apellido_equipo
    for (apellido, equipo_norm), lista_jugadores in jugadores_por_apellido_equipo.items():
        for clave_ff, info in lista_jugadores:
            nombre_norm = info["nombre_norm"]
            pos_val = info.get("posicion", "MC")

            if apellido not in APELLIDOS_CRITICOS:
                clave_norm = (nombre_norm, equipo_norm)
            else:
                if len(lista_jugadores) == 1:
                    clave_norm = (nombre_norm, equipo_norm)
                else:
                    pos_clave = normalizar_pos_clave(pos_val)
                    clave_norm = (nombre_norm, equipo_norm, pos_clave)

            if clave_norm not in fantasy_por_norm:
                fantasy_por_norm[clave_norm] = []

            entrada_ff = {
                "clave_ff": clave_ff,
                "puntos": info["puntos"],
                "info": info,
            }
            fantasy_por_norm[clave_norm].append(entrada_ff)

    return jugadores_por_apellido_equipo, fantasy_por_norm


def postprocesar_df_partido(df):
    """
    Postprocesa el DataFrame de un partido:

    - Normaliza nombres de equipos.
    - Pone a 0 las stats de portero en jugadores que no son PT.
    - Asegura columnas Amarillas/Rojas (int).
    - Rellena NaNs con 0.
    """
    if df.empty:
        return df

    if "Equipo_propio" in df.columns:
        df["Equipo_propio"] = df["Equipo_propio"].apply(normalizar_equipo_temporada)

    if "Equipo_rival" in df.columns:
        df["Equipo_rival"] = df["Equipo_rival"].apply(normalizar_equipo_temporada)

    if "posicion" in df.columns:
        mask_no_portero = df["posicion"] != "PT"
        if "Goles_en_contra" in df.columns:
            df.loc[mask_no_portero, "Goles_en_contra"] = 0.0
        if "Porcentaje_paradas" in df.columns:
            df.loc[mask_no_portero, "Porcentaje_paradas"] = 0.0

    if "Amarillas" not in df.columns:
        df["Amarillas"] = 0
    if "Rojas" not in df.columns:
        df["Rojas"] = 0

    df["Amarillas"] = df["Amarillas"].fillna(0).astype(int)
    df["Rojas"] = df["Rojas"].fillna(0).astype(int)

    df = df.fillna(0)

    return df


def contar_tarjetas_banquillo(df):
    if df is None or df.empty:
        return pd.DataFrame()
    mask = (
        (df["Amarillas"].fillna(0) > 0)
        | (df["Rojas"].fillna(0) > 0)
    ) & (df["Min_partido"].fillna(0) == 0)
    df_banquillo = df[mask].copy()
    df_banquillo["banquillo"] = True
    return df_banquillo


def completar_fantasy_sin_match(bd_partido, fantasy_partido, usadas_ff, local_norm, visit_norm, fecha_partido, jornada, temporada):
    """
    - Usa alias/normalización para detectar equivalencias por inicial + apellido
      con filas ya existentes.
    - Si encuentra equivalencia, rellena puntosFantasy en la fila ya creada.
    - Si no hay equivalencia y el jugador tiene tarjetas con 0 minutos, crea una
      fila nueva 'fantasy_only' para reflejar esas tarjetas.
    """
    claves_canonicas_presentes = set()
    nombres_canonicos_presentes = {}

    # 1) Construir el set de claves canónicas presentes en bd_partido
    for _, fila in bd_partido.items():
        nombre_fb = fila["player"]
        equipo_fb_norm = fila["Equipo_propio"]
        pos_fb = fila["posicion"]

        nombre_canonico_fb = normalizar_texto(
            aplicar_alias_jugador_temporada(
                nombre_fb, equipo_fb_norm, temporada
            )
        )

        claves_canonicas_presentes.add((nombre_canonico_fb, equipo_fb_norm, pos_fb))

        clave_ep = (equipo_fb_norm, pos_fb)
        if clave_ep not in nombres_canonicos_presentes:
            nombres_canonicos_presentes[clave_ep] = set()
        nombres_canonicos_presentes[clave_ep].add(nombre_canonico_fb)

    # 2) Recorrer jugadores Fantasy y ver qué hacer con los que no están en bd_partido
    for clave_ff, info in fantasy_partido.items():
        nombre_original = info["nombre_original"]
        equipo_norm = info["equipo_norm"]
        pos_val = info.get("posicion", "MC")

        nombre_canonico_ff = normalizar_texto(
            aplicar_alias_jugador_temporada(
                nombre_original, equipo_norm, temporada
            )
        )

        if (nombre_canonico_ff, equipo_norm, pos_val) in claves_canonicas_presentes:
            continue

        clave_ep = (equipo_norm, pos_val)
        nombres_presentes = nombres_canonicos_presentes.get(clave_ep, set())

        # 2a) Intentar emparejar por inicial + apellido
        coincidencia = None
        for n in nombres_presentes:
            if coincide_inicial_apellido(nombre_canonico_ff, n):
                coincidencia = n
                break

        if coincidencia:
            for fila in bd_partido.values():
                nombre_canonico_fila = normalizar_texto(
                    aplicar_alias_jugador_temporada(
                        fila["player"], fila["Equipo_propio"], temporada
                    )
                )
                if (
                    nombre_canonico_fila == coincidencia
                    and fila["Equipo_propio"] == equipo_norm
                    and fila["posicion"] == pos_val
                ):
                    fila["puntosFantasy"] = info.get("puntos", 6767)
                    break
            continue

        # 2b) Evitar duplicar jugadores ya usados en matching
        if clave_ff in usadas_ff:
            continue

        puntos = info.get("puntos", 6767)
        amarillas_banquillo = info.get("amarillas", 0)
        rojas_banquillo = info.get("rojas", 0)

        # Si no tiene tarjetas, no lo añadimos como fantasy_only
        if amarillas_banquillo == 0 and rojas_banquillo == 0:
            continue

        equipo_rival_norm = visit_norm if equipo_norm == local_norm else local_norm

        nombre_norm = info["nombre_norm"]
        clave_registro = f"{nombre_norm}|{equipo_norm}|0|{pos_val}|fantasy_only}}"

        fila = {col: 0 for col in COLUMNAS_MODELO}

        fila["temporada"] = temporada
        fila["jornada"] = jornada
        fila["fecha_partido"] = fecha_partido
        fila["player"] = nombre_a_mayus(nombre_canonico_ff)
        fila["posicion"] = pos_val
        fila["Equipo_propio"] = equipo_norm
        fila["Equipo_rival"] = equipo_rival_norm
        fila["local"] = 1 if equipo_norm == local_norm else 0
        fila["Titular"] = 0
        fila["Min_partido"] = 0
        fila["puntosFantasy"] = puntos
        fila["Amarillas"] = amarillas_banquillo
        fila["Rojas"] = rojas_banquillo
        fila["roles"] = []

        bd_partido[clave_registro] = fila

    return bd_partido


def asignar_roles_df(df_partido, roles_destacados):
    """
    Asigna roles (lista de etiquetas) a cada fila del DataFrame de partido,
    usando el diccionario roles_destacados:

    - Intenta primero roles de la misma temporada.
    - Si no hay, busca en otras temporadas por nombre canónico.
    - Si no hay en ninguna, deja la lista vacía.
    """
    def _asignar_roles_fila(fila):
        temporada_fila = fila["temporada"]
        nombre_canonico = normalizar_texto(
            aplicar_alias_jugador_temporada(
                fila["player"], fila["Equipo_propio"], temporada_fila
            )
        )

        roles_temp = roles_destacados.get(temporada_fila, {})
        roles = roles_temp.get(nombre_canonico)
        if roles:
            return [r for r in roles]

        for temp, mapa in roles_destacados.items():
            if temp == temporada_fila:
                continue
            if nombre_canonico in mapa:
                return [r for r in mapa[nombre_canonico]]

        return []

    if "roles" not in df_partido.columns:
        df_partido["roles"] = df_partido.index.to_series().apply(lambda _: [])

    df_partido["roles"] = df_partido.apply(_asignar_roles_fila, axis=1)
    return df_partido


def imprimir_mal_6767(df_partido, columna="puntosFantasy"):
    if columna not in df_partido.columns:
        return
    jugadores = df_partido[df_partido[columna] == 6767]
    if jugadores.empty:
        return
    print(f"\nJugadores con {columna} = {6767} en este partido:")
    for _, fila in jugadores.iterrows():
        print(
            f"- {fila['player']} ({fila['Equipo_propio']}) | "
            f"pos: {fila['posicion']} | min: {fila['Min_partido']}"
        )
