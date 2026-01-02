import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from commons import (
    normalizar_texto,
    normalizar_equipo_temporada,
    aplicar_alias_jugador_temporada,
)


MAPEO_CAPTION_A_ROL = {
    "Goals": "goles",
    "Goals/90": "goles_90",
    "Assists": "asistencias",
    "Assists/90": "asistencias_90",
    "Penalty Kicks Made": "penaltis_marcados",
    "Shots on Target": "tiros_puerta",
    "Goals/Shot": "goles_por_tiro",
    "Key Passes": "pases_clave",
    "Pass Completion %": "pases_completados_pct",
    "Passes into Final Third": "pases_ultimo_tercio",
    "Crosses into Penalty Area": "centros_area",
    "Corner Kicks": "corners",
    "Tackles": "entradas",
    "Interceptions": "intercepciones",
    "Clearances": "despejes",
    "Successful Take-Ons": "regates_exitosos",
    "Minutes": "minutos",
    "Substitute Appearances": "apariciones_suplente",
    "Yellow Cards": "amarillas",
    "Red Cards": "rojas",
    "Fouls Committed": "faltas_cometidas",
    "Fouls Drawn": "faltas_recibidas",
    "Clean Sheets": "porterias_cero",
    "Saves": "paradas",
    "Save Percentage": "save_pct",
}


def _normalizar_nombre_jugador_fbref(nombre_raw: str, equipo_raw: str, temporada: str) -> str:
    equipo_norm = normalizar_equipo_temporada(equipo_raw) if equipo_raw else None
    nombre_con_alias = aplicar_alias_jugador_temporada(
        nombre_raw, equipo_norm, temporada
    )
    return normalizar_texto(nombre_con_alias)


def _parsear_div_leaders(html: str, temporada: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    comments = soup.find_all(string=lambda text: isinstance(text, Comment))

    fragmento = None
    for c in comments:
        if 'id="div_leaders"' in c:
            fragmento = c
            break

    if fragmento is None:
        print("⚠️ No se encontró fragmento con div_leaders en comentarios")
        return {}

    frag_soup = BeautifulSoup(fragmento, "lxml")

    div_leaders = frag_soup.find("div", id="div_leaders")
    if not div_leaders:
        print("⚠️ No se encontró div#div_leaders en el fragmento")
        return {}

    roles_por_jugador = {}

    cajas = div_leaders.find_all("div", class_="data_grid_box")
    for caja in cajas:
        tabla = caja.find("table", class_="columns")
        if not tabla:
            continue

        caption_tag = tabla.find("caption")
        if not caption_tag:
            continue

        caption_txt = caption_tag.get_text(strip=True)
        if caption_txt not in MAPEO_CAPTION_A_ROL:
            continue
        clave_rol = MAPEO_CAPTION_A_ROL[caption_txt]

        last_rank = None

        for tr in tabla.find_all("tr"):
            td_rank = tr.find("td", class_="rank")
            td_who = tr.find("td", class_="who")
            td_value = tr.find("td", class_="value")
            if not td_who or not td_value:
                continue

            if td_rank and td_rank.get_text(strip=True):
                rank_txt = td_rank.get_text(strip=True).replace(".", "")
                try:
                    pos = int(rank_txt)
                    last_rank = pos
                except ValueError:
                    pos = last_rank
            else:
                pos = last_rank

            a_jugador = td_who.find("a")
            if not a_jugador:
                continue
            nombre_raw = a_jugador.get_text(strip=True)

            span_desc = td_who.find("span", class_="desc")
            if span_desc:
                a_eq = span_desc.find("a")
                equipo_raw = (
                    a_eq.get_text(strip=True)
                    if a_eq
                    else span_desc.get_text(strip=True)
                )
            else:
                equipo_raw = ""

            valor_txt = td_value.get_text(strip=True).replace(",", ".")
            try:
                valor = float(valor_txt)
            except ValueError:
                continue

            nombre_canonico = _normalizar_nombre_jugador_fbref(
                nombre_raw, equipo_raw, temporada
            )

            if nombre_canonico not in roles_por_jugador:
                roles_por_jugador[nombre_canonico] = []

            roles_por_jugador[nombre_canonico].append(
                {clave_rol: [pos, valor]}
            )

    return roles_por_jugador


def generar_roles_para_temporada(codigo_temporada: str) -> dict:
    ruta_html = Path(f"main/html/temporada_{codigo_temporada}/tablas.html")
    html = ruta_html.read_text(encoding="utf-8")
    return _parsear_div_leaders(html, codigo_temporada)


# ===== Construir ROLES_DESTACADOS en el propio módulo =====

ROLES_DESTACADOS = {
    "23_24": generar_roles_para_temporada("23_24"),
    "24_25": generar_roles_para_temporada("24_25"),
    "25_26": generar_roles_para_temporada("25_26"),
}


if __name__ == "__main__":
    # Debug: imprimir la temporada 25_26 en formato pegable
    temporada = "25_26"
    roles_por_jugador = ROLES_DESTACADOS[temporada]

    print(f'ROLES_DESTACADOS["{temporada}"] = {{')
    for jugador, roles in roles_por_jugador.items():
        print(f'    "{jugador}": [')
        for rol_dict in roles:
            clave_rol, (pos, valor) = next(iter(rol_dict.items()))
            if isinstance(valor, float) and valor.is_integer():
                valor_repr = int(valor)
            else:
                valor_repr = valor
            print(f'        {{"{clave_rol}":[{pos}, {valor_repr}]}},')
        print("    ],")
    print("}")
