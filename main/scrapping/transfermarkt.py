import os
import csv
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from main.scrapping.commons import normalizar_equipo  # para mapear nombres TM -> tus nombres
from main.models import Equipo  # para guardar estadios extraídos


# ======================== MAPEO DE NOMBRES DE EQUIPOS ========================
# Mapeo manual: nombre_normalizado_tm -> nombre_exacto_bd
EQUIPO_TM_TO_BD = {
    'barcelona': 'Barcelona',
    'fc barcelona': 'Barcelona',
    'real madrid': 'Real Madrid',
    'atletico madrid': 'Atlético Madrid',
    'atletico': 'Atlético Madrid',
    'athletic': 'Athletic Club',
    'athletic bilbao': 'Athletic Club',
    'villarreal': 'Villarreal',
    'fc villarreal': 'Villarreal',
    'betis': 'Real Betis',
    'real betis': 'Real Betis',
    'real betis sevilla': 'Real Betis',
    'rc celta': 'Celta Vigo',
    'celta': 'Celta Vigo',
    'celta vigo': 'Celta Vigo',
    'rayo': 'Rayo Vallecano',
    'rayo vallecano': 'Rayo Vallecano',
    'ca osasuna': 'Osasuna',
    'osasuna': 'Osasuna',
    'rcd mallorca': 'Real Mallorca',
    'mallorca': 'Real Mallorca',
    'real mallorca': 'Real Mallorca',
    'real sociedad': 'Real Sociedad',
    'real sociedad san sebastian': 'Real Sociedad',
    'sociedad': 'Real Sociedad',
    'valencia cf': 'Valencia',
    'valencia': 'Valencia',
    'fc valencia': 'Valencia',
    'getafe': 'Getafe',
    'fc getafe': 'Getafe',
    'rcd espanyol': 'RCD Espanyol',
    'espanyol': 'RCD Espanyol',
    'espanyol barcelona': 'RCD Espanyol',
    'alaves': 'Alavés',
    'alavés': 'Alavés',
    'deportivo alaves': 'Alavés',
    'girona fc': 'Girona',
    'girona': 'Girona',
    'fc girona': 'Girona',
    'sevilla': 'Sevilla',
    'fc sevilla': 'Sevilla',
    'cd leganes': 'Leganés',
    'leganes': 'Leganés',
    'leganés': 'Leganés',
    'ud las palmas': 'Las Palmas',
    'las palmas': 'Las Palmas',
    'real valladolid': 'Real Valladolid',
    'valladolid': 'Real Valladolid',
}

def mapear_equipo_tm_a_bd(equipo_norm):
    """Mapea nombre normalizado de TM al nombre exacto en BD."""
    return EQUIPO_TM_TO_BD.get(equipo_norm, equipo_norm)


BASE_URL = "https://www.transfermarkt.es/laliga/spieltagtabelle/wettbewerb/ES1"
MATCHES_BASE_URL = "https://www.transfermarkt.es/laliga/spieltag/wettbewerb/ES1"


def parse_tabla_jornada_transfermarkt(html: str, temporada: str, jornada: int):
    """
    Parsea el HTML de la tabla de jornada de Transfermarkt y devuelve
    una lista de dicts, una fila por equipo, SIN racha (la racha
    se calcula fuera, con estado entre jornadas).
    """
    soup = BeautifulSoup(html, "lxml")

    tabla = soup.find("table", class_="items")
    if not tabla or not tabla.tbody:
        return []

    filas_out = []
    trs = tabla.tbody.find_all("tr")

    for idx, tr in enumerate(trs, start=1):
        tds = tr.find_all("td")
        if len(tds) < 10:
            continue

        # Posición
        pos_text = tds[0].get_text(strip=True).replace(".", "")
        try:
            posicion = int(pos_text)
        except Exception:
            posicion = None

        # Nombre equipo
        name_td = tds[2]
        a_team = name_td.find("a")
        equipo_raw = a_team.get_text(strip=True) if a_team else name_td.get_text(strip=True)
        equipo = normalizar_equipo(equipo_raw)

        def to_int_td(td):
            try:
                return int(td.get_text(strip=True).replace("+", ""))
            except Exception:
                return None

        pj = to_int_td(tds[3])
        pg = to_int_td(tds[4])
        pe = to_int_td(tds[5])
        pp = to_int_td(tds[6])

        goles_str = tds[7].get_text(strip=True)  # "3:0"
        try:
            gf, gc = map(int, goles_str.split(":"))
        except Exception:
            gf, gc = None, None

        dg = to_int_td(tds[8])
        pts = to_int_td(tds[9])

        fila = {
            "temporada": temporada,
            "jornada": jornada,
            "equipo": equipo,
            "posicion": posicion,
            "pj": pj,
            "pg": pg,
            "pe": pe,
            "pp": pp,
            "gf": gf,
            "gc": gc,
            "dg": dg,
            "pts": pts,
        }
        filas_out.append(fila)

    return filas_out


def scrapear_rango_jornadas_online(
    codigo_temporada: str,
    temporada_transfermarkt: int,
    j_ini: int,
    j_fin: int,
    carpeta_salida: str,  # <-- carpeta donde quieres guardar el CSV
):
    """
    Descarga TODAS las jornadas indicadas y las mete en un único CSV:

        <carpeta_salida>/clasificacion_temporada.csv

    Una fila = un equipo en una jornada, con racha5partidos ya calculada
    dinámicamente a medida que se recorre la temporada.
    """
    # Asegurar que la carpeta de salida existe
    os.makedirs(carpeta_salida, exist_ok=True)
    ruta_csv = os.path.join(carpeta_salida, "clasificacion_temporada.csv")

    campos = [
        "temporada",
        "jornada",
        "equipo",
        "posicion",
        "pj",
        "pg",
        "pe",
        "pp",
        "gf",
        "gc",
        "dg",
        "pts",
        "racha5partidos",
    ]

    # historial_por_equipo mantiene la secuencia de resultados y acumulados previos
    historial_por_equipo = {}  # equipo -> dict(pg_prev, pe_prev, pp_prev, resultados[list])

    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for jornada in range(j_ini, j_fin + 1):
            # pequeña espera aleatoria entre requests (p.ej. 3-7 segundos)
            sleep_s = random.uniform(3, 7)
            time.sleep(sleep_s)

            params = {"saison_id": temporada_transfermarkt, "spieltag": jornada}
            resp = requests.get(BASE_URL, params=params, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                continue

            filas = parse_tabla_jornada_transfermarkt(resp.text, codigo_temporada, jornada)

            # procesar filas de esta jornada, actualizando historial_por_equipo y racha5partidos
            for fila in filas:
                equipo = fila["equipo"]
                pg = fila["pg"] or 0
                pe = fila["pe"] or 0
                pp = fila["pp"] or 0

                if equipo not in historial_por_equipo:
                    historial_por_equipo[equipo] = {
                        "pg_prev": 0,
                        "pe_prev": 0,
                        "pp_prev": 0,
                        "resultados": [],
                    }

                info = historial_por_equipo[equipo]
                pg_prev = info["pg_prev"]
                pe_prev = info["pe_prev"]
                pp_prev = info["pp_prev"]

                # detectar resultado de ESTA jornada comparando acumulados
                if pg > pg_prev:
                    res = "W"
                elif pe > pe_prev:
                    res = "D"
                elif pp > pp_prev:
                    res = "L"
                else:
                    res = ""

                if res:
                    info["resultados"].append(res)

                # actualizar acumulados
                info["pg_prev"] = pg
                info["pe_prev"] = pe
                info["pp_prev"] = pp

                ultimos5 = info["resultados"][-5:]
                racha5 = "".join(ultimos5)
                fila["racha5partidos"] = racha5

                writer.writerow(fila)


def extraer_fecha_hora_desde_html(fecha_str, hora_str):
    """
    Extrae fecha y hora desde strings del HTML de Transfermarkt.
    
    Args:
        fecha_str: Ej. "05/12/2025" (DD/MM/YYYY)
        hora_str: Ej. "21:00" (HH:MM)
    
    Returns:
        datetime objeto o None si no puede parsear
    """
    try:
        if not fecha_str or not hora_str:
            return None
        
        fecha_str = fecha_str.strip()
        hora_str = hora_str.strip()
        
        # Parsear DD/MM/YYYY HH:MM
        datetime_str = f"{fecha_str} {hora_str}"
        return datetime.strptime(datetime_str, "%d/%m/%Y %H:%M")
    except Exception:
        return None


def parse_partidos_jornada_transfermarkt(html_content, jornada_num):
    """
    Parsea los partidos de una jornada desde el HTML de Transfermarkt.
    
    Extrae:
    - Equipo local, equipo visitante
    - Resultado (goles local, goles visitante)
    - Fecha y hora
    
    Returns:
        Lista de dicts con estructura:
        {
            'jornada': int,
            'equipo_local': str,
            'equipo_visitante': str,
            'goles_local': int,
            'goles_visitante': int,
            'fecha': datetime,
            'hora': str (HH:MM)
        }
    """
    partidos = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Buscar tabla de partidos
    tabla_partidos = soup.find('div', class_='responsive-table')
    if not tabla_partidos:
        return partidos
    
    filas = tabla_partidos.find_all('tr')
    
    for fila in filas:
        try:
            # Saltar encabezados
            if fila.find('th'):
                continue
            
            celdas = fila.find_all('td')
            if len(celdas) < 5:
                continue
            
            # Encontrar celda con fecha (clase "show-for-small")
            celda_fecha = fila.find('td', class_='show-for-small')
            if not celda_fecha:
                continue
            
            # Extraer fecha y hora
            fecha_link = celda_fecha.find('a')
            if not fecha_link:
                continue
            
            fecha_str = fecha_link.get_text(strip=True)  # "05/12/2025"
            
            # Hora está después del link
            hora_str = None
            for item in celda_fecha.contents:
                if isinstance(item, str):
                    text = item.strip()
                    if ':' in text and len(text) == 5:  # "21:00"
                        hora_str = text
                        break
            
            if not hora_str:
                # Intentar con la siguiente celda
                continue
            
            # Encontrar equipos y resultado
            # Estructura: [fecha] [equipo_local] [resultado] [equipo_visitante]
            
            # Buscar nombre de equipos (están en celdas con clase especial o en spans)
            equipos = fila.find_all('a', class_='vereinprofil_tooltip')
            if len(equipos) < 2:
                continue
            
            equipo_local = equipos[0].get_text(strip=True)
            equipo_visitante = equipos[1].get_text(strip=True)
            
            # Resultado
            resultado_celda = None
            for celda in celdas:
                if celda.get_text(strip=True) and ':' in celda.get_text(strip=True):
                    # Verificar que sea el formato "X:X" (resultado)
                    texto = celda.get_text(strip=True)
                    if len(texto) <= 5 and texto.count(':') == 1:
                        try:
                            partes = texto.split(':')
                            goles_local = int(partes[0].strip())
                            goles_visitante = int(partes[1].strip())
                            resultado_celda = (goles_local, goles_visitante)
                            break
                        except:
                            continue
            
            if not resultado_celda:
                continue
            
            goles_local, goles_visitante = resultado_celda
            
            # Convertir fecha
            fecha_obj = extraer_fecha_hora_desde_html(fecha_str, hora_str)
            if not fecha_obj:
                continue
            
            # Normalizar nombres de equipos
            equipo_local_norm = normalizar_equipo(equipo_local)
            equipo_visitante_norm = normalizar_equipo(equipo_visitante)
            
            partidos.append({
                'jornada': jornada_num,
                'equipo_local': equipo_local_norm,
                'equipo_visitante': equipo_visitante_norm,
                'goles_local': goles_local,
                'goles_visitante': goles_visitante,
                'fecha': fecha_obj,
                'hora': hora_str
            })
        
        except Exception:
            continue
    
    return partidos


# DEPRECATED: No se usa en el proyecto actual
# def scrapear_partidos_rango_jornadas(
#     codigo_temporada,
#     temporada_transfermarkt,
#     j_ini=1,
#     j_fin=38,
#     carpeta_salida=None,
#     delay_min=1,
#     delay_max=3
# ):
#     """
#     Scrapea los partidos (con fecha/hora) de un rango de jornadas de Transfermarkt.
#     
#     Args:
#         codigo_temporada: Ej. "23_24" o "24_25"
#         temporada_transfermarkt: Ej. 2024, 2025 (saison_id)
#         j_ini, j_fin: Rango de jornadas a scrapear
#         carpeta_salida: Carpeta donde guardar CSVs (si None, no guarda)
#         delay_min, delay_max: Delay entre requests (segundos)
#     """
    
    ruta_csv = None
    if carpeta_salida:
        os.makedirs(carpeta_salida, exist_ok=True)
        ruta_csv = os.path.join(carpeta_salida, f"partidos_{codigo_temporada}.csv")
    
    all_partidos = []
    header_escrito = False
    
    for jornada in range(j_ini, j_fin + 1):
        try:
            # URL de la jornada
            url = f"{MATCHES_BASE_URL}/spieltag/{jornada}/saison_id/{temporada_transfermarkt}"
            
            # Delay aleatorio
            delay = random.uniform(delay_min, delay_max)
            time.sleep(delay)
            
            # Request
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            # Parsear
            partidos = parse_partidos_jornada_transfermarkt(response.text, jornada)
            all_partidos.extend(partidos)
            
            # Guardar a CSV si se proporciona carpeta
            if ruta_csv and partidos:
                with open(ruta_csv, 'a', newline='', encoding='utf-8') as f:
                    if not header_escrito:
                        writer = csv.DictWriter(
                            f,
                            fieldnames=['jornada', 'equipo_local', 'equipo_visitante',
                                       'goles_local', 'goles_visitante', 'fecha', 'hora']
                        )
                        writer.writeheader()
                        header_escrito = True
                    
                    # Convertir datetime a string para CSV
                    for partido in partidos:
                        partido_copia = partido.copy()
                        partido_copia['fecha'] = partido['fecha'].isoformat()
                        writer.writerow(partido_copia)
        
        except Exception:
            continue
    
    return all_partidos


def extraer_nacionalidad_desde_bandera(img_bandera):
    """
    Extrae la nacionalidad desde el atributo 'alt' de la imagen bandera.
    
    Args:
        img_bandera: Tag <img> con la bandera del país
    
    Returns:
        str con el nombre del país o None
    """
    if not img_bandera:
        return None
    
    # El atributo 'alt' generalmente contiene el nombre del país
    nacionalidad = img_bandera.get('alt', '').strip()
    
    if nacionalidad:
        return nacionalidad
    
    # Intentar con title
    nacionalidad = img_bandera.get('title', '').strip()
    return nacionalidad if nacionalidad else None


def obtener_plantilla_equipo(href_equipo, saison_id=2024, delay_min=1, delay_max=3):
    """
    Descarga la página de plantilla de un equipo desde Transfermarkt.
    
    Args:
        href_equipo: URL relativa del equipo (ej: /real-madrid/kader/verein/418)
        saison_id: ID de la temporada en Transfermarkt (2023, 2024, 2025, etc.)
        delay_min, delay_max: Delay entre requests (segundos)
    
    Returns:
        HTML content o None si hay error
    """
    try:
        url_completa = f"https://www.transfermarkt.es{href_equipo}/saison/{saison_id}"
        
        delay = random.uniform(delay_min, delay_max)
        time.sleep(delay)
        
        response = requests.get(
            url_completa,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        response.raise_for_status()
        
        return response.text
    
    except Exception:
        return None


def procesar_plantilla_equipo(html_content, equipo_norm):
    """
    Parsea la HTML de plantilla y extrae jugadores con nacionalidad + estadio del equipo.
    
    Args:
        html_content: Contenido HTML de la página de plantilla
        equipo_norm: Nombre del equipo normalizado
    
    Returns:
        Tupla (lista de dicts jugadores, nombre_estadio)
    """
    jugadores = []
    estadio = None
    
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        # ============ EXTRAER ESTADIO ============
        # Buscar en el header la sección del estadio
        header = soup.find('header', class_='data-header')
        if header:
            # Buscar todos los <li> con class data-header__label
            for li in header.find_all('li', class_='data-header__label'):
                texto = li.get_text(strip=True)
                if 'Estadio:' in texto or 'Stadium:' in texto:
                    # El estadio está en la etiqueta <a> dentro de data-header__content
                    span_content = li.find('span', class_='data-header__content')
                    if span_content:
                        a_tag = span_content.find('a')
                        if a_tag:
                            estadio = a_tag.get_text(strip=True)
                            break
        
        # ============ EXTRAER JUGADORES ============
        # Buscar tabla principal de plantilla
        tabla = soup.find('table', class_='items')
        
        if not tabla or not tabla.tbody:
            return jugadores, estadio
        
        filas = tabla.tbody.find_all('tr')
        
        for fila in filas:
            try:
                celdas = fila.find_all('td')
                
                # Estructura de tabla: dorsal, nombre+pos, foto, nombre, posicion, edad, BANDERA, fecha, mercado
                # Solo procesar filas principales que tengan 9 celdas (las expansiones rowspan tienen menos)
                if len(celdas) < 9:
                    continue
                
                # Dorsal (celda 0)
                try:
                    dorsal = int(celdas[0].get_text(strip=True))
                except (ValueError, IndexError):
                    dorsal = None
                
                # Nombre del jugador (celda 3 generalmente tiene el link al jugador)
                link_jugador = celdas[3].find('a') if len(celdas) > 3 else None
                if not link_jugador:
                    # Fallback: intentar en celda 1
                    link_jugador = celdas[1].find('a')
                
                if not link_jugador:
                    continue
                
                nombre_jugador = link_jugador.get_text(strip=True)
                
                # Posición (celda 4)
                posicion = "Desconocida"
                if len(celdas) > 4:
                    posicion_texto = celdas[4].get_text(strip=True)
                    if posicion_texto:
                        posicion = posicion_texto
                
                # Edad (celda 5)
                edad = None
                if len(celdas) > 5:
                    try:
                        edad_text = celdas[5].get_text(strip=True)
                        edad = int(edad_text)
                    except (ValueError, IndexError):
                        pass
                
                # Nacionalidad (celda 6 - buscar imagen con flag)
                nacionalidad = None
                if len(celdas) > 6:
                    img_bandera = celdas[6].find('img')
                    if img_bandera:
                        nacionalidad = extraer_nacionalidad_desde_bandera(img_bandera)
                
                if nombre_jugador and nacionalidad:
                    jugadores.append({
                        'jugador': nombre_jugador,
                        'nacionalidad': nacionalidad,
                        'posicion': posicion,
                        'dorsal': dorsal,
                        'edad': edad,
                        'equipo': equipo_norm
                    })
            
            except Exception:
                continue
        
        return jugadores, estadio
    
    except Exception:
        return [], None


def scrapear_plantillas_temporada(código_equipos_to_href, temporada_codigo, carpeta_salida, saison_id=2024, delay_min=2, delay_max=5):
    """
    Scrapea plantillas de todos los equipos, extrae datos de jugadores y estadios,
    actualiza estadios en BD.
    
    Args:
        código_equipos_to_href: Dict {nombre_equipo_norm: href_tm}
        temporada_codigo: Ej. "23_24", "24_25"
        carpeta_salida: Carpeta donde guardar CSVs
        saison_id: ID de la temporada en Transfermarkt (2023, 2024, 2025, etc.)
        delay_min, delay_max: Delay entre requests
    """
    
    for equipo_norm, href in código_equipos_to_href.items():
        
        html = obtener_plantilla_equipo(href, saison_id=saison_id, delay_min=delay_min, delay_max=delay_max)
        
        if html:
            # Procesar_plantilla_equipo retorna tupla (jugadores, estadio)
            jugadores, estadio = procesar_plantilla_equipo(html, equipo_norm)
            
            # ========== GUARDAR ESTADIO EN BD ==========
            if estadio:
                try:
                    # Mapear nombre normalizado TM al nombre exacto en BD
                    equipo_bd_nombre = mapear_equipo_tm_a_bd(equipo_norm)
                    equipo_obj = Equipo.objects.filter(nombre=equipo_bd_nombre).first()
                    
                    if equipo_obj:
                        if equipo_obj.estadio != estadio:
                            equipo_obj.estadio = estadio
                            equipo_obj.save()
                except Exception:
                    pass
        pass



def extraer_hrefs_equipos_desde_clasificacion(html_clasificacion):
    """
    Extrae los hrefs de todos los equipos desde la tabla de clasificación.
    
    Args:
        html_clasificacion: HTML de la página de clasificación
    
    Returns:
        Dict {equipo_norm: href_tm}
    """
    equipos_href = {}
    
    try:
        soup = BeautifulSoup(html_clasificacion, 'lxml')
        tabla = soup.find('table', class_='items')
        
        if not tabla or not tabla.tbody:
            return equipos_href
        
        for fila in tabla.tbody.find_all('tr'):
            tds = fila.find_all('td')
            
            if len(tds) < 3:
                continue
            
            # El nombre del equipo suele estar en la celda 2
            celda_equipo = tds[2]
            link = celda_equipo.find('a')
            
            if link:
                href = link.get('href', '')
                equipo_raw = link.get_text(strip=True)
                equipo_norm = normalizar_equipo(equipo_raw)
                
                if href and equipo_norm:
                    # Convertir href de forma /equipo/spielplan/verein/XXX a /equipo/kader/verein/XXX
                    # para acceder a la plantilla
                    href_plantilla = href.replace('/spielplan/', '/kader/')
                    equipos_href[equipo_norm] = href_plantilla
        
        return equipos_href
    
    except Exception:
        return equipos_href


if __name__ == "__main__":
    # ============= OPCIÓN 1: Scrapear partidos =============
    # carpeta_destino = os.path.join("data", "temporada_25_26")
    # scrapear_rango_jornadas_online(
    #     codigo_temporada="25_26",
    #     temporada_transfermarkt=2025,
    #     j_ini=1,
    #     j_fin=18,
    #     carpeta_salida=carpeta_destino,
    # )
    
    # ============= OPCIÓN 2: Scrapear plantillas con nacionalidad =============
    # Paso 1: Primero necesitas descargar la página de clasificación para obtener los hrefs
    # print("📥 Descargando clasificación para obtener hrefs de equipos...")
    # resp = requests.get(
    #     f"{BASE_URL}?saison_id=2024",
    #     headers={"User-Agent": "Mozilla/5.0"},
    #     timeout=15
    # )
    # 
    # if resp.status_code == 200:
    #     # Extraer hrefs de los equipos
    #     equipos_href = extraer_hrefs_equipos_desde_clasificacion(resp.text)
    #     
    #     # Paso 2: Scrapear plantillas
    #     carpeta_plantillas = os.path.join("csv", "csvGenerados", "plantillas")
    #     scrapear_plantillas_temporada(
    #         código_equipos_to_href=equipos_href,
    #         temporada_codigo="24_25",
    #         carpeta_salida=carpeta_plantillas,
    #         delay_min=2,
    #         delay_max=5
    #     )
    # else:
    #     print(f"❌ Error descargando clasificación: {resp.status_code}")
    pass

