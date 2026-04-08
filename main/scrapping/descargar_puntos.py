import os
import time
import random
import cloudscraper


def crear_scraper_ff():
    scraper = cloudscraper.create_scraper(
        browser={
            "browser": "chrome",
            "platform": "windows",
            "desktop": True,
        }
    )
    scraper.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
    )
    return scraper


def descargar_html_con_reintentos(url: str,ruta_salida: str,max_intentos: int = 5,backoff_inicial: float = 3.0,backoff_max: float = 30.0,timeout: int = 30,verbose: bool = True,):
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)

    if os.path.exists(ruta_salida):
        if verbose:
            print(f"[SKIP] Ya existe: {ruta_salida}")
        return ruta_salida

    scraper = crear_scraper_ff()

    intento = 0
    ultimo_error = None

    while intento < max_intentos:
        intento += 1
        try:
            if verbose:
                print(f"[GET] ({intento}/{max_intentos}) {url}")

            resp = scraper.get(url, timeout=timeout)

            if resp.status_code == 200 and resp.text.strip():
                with open(ruta_salida, "w", encoding="utf-8") as f:
                    f.write(resp.text)
                if verbose:
                    print(f"[OK] Guardado en {ruta_salida}")
                return ruta_salida

            ultimo_error = f"Status {resp.status_code}"
            if verbose:
                print(f"[WARN] Respuesta no OK ({resp.status_code})")

        except Exception as e:
            ultimo_error = repr(e)
            if verbose:
                print(f"[ERROR] Intento {intento} fallido: {e!r}")

        if intento < max_intentos:
            delay_base = min(backoff_inicial * (2 ** (intento - 1)), backoff_max)
            delay = delay_base + random.uniform(0, 1.5)
            if verbose:
                print(f"[SLEEP] Esperando {delay:.1f}s antes de reintentar...")
            time.sleep(delay)

    raise RuntimeError(
        f"No se pudo descargar {url} tras {max_intentos} intentos. "
        f"Último error: {ultimo_error}"
    )



def descargar_puntos_temporada(temporada: str, j_ini: int, j_fin: int):
    # El año de la URL es el segundo número de la temporada
    try:
        anio_url = int(temporada.split('_')[1])
        if anio_url < 100:
            anio_url += 2000
    except Exception:
        raise ValueError("El formato de temporada debe ser 'xx_yy', por ejemplo '22_23'")
    base_url = f"https://www.futbolfantasy.com/laliga/puntos/{anio_url}/{{jornada}}/laliga-fantasy"
    carpeta_base = os.path.join("main", "html", f"temporada_{temporada}")
    os.makedirs(carpeta_base, exist_ok=True)

    for j in range(j_ini, j_fin + 1):
        url = base_url.format(jornada=j)
        carpeta_j = os.path.join(carpeta_base, f"j{j}")
        os.makedirs(carpeta_j, exist_ok=True)

        ruta_salida = os.path.join(carpeta_j, "puntos.html")

        try:
            descargar_html_con_reintentos(
                url=url,
                ruta_salida=ruta_salida,
                max_intentos=5,
                backoff_inicial=3.0,
                backoff_max=30.0,
                timeout=30,
                verbose=False,  
            )
        except Exception as e:
            print(f"[FALLO] Jornada {j}: {e!r}")


if __name__ == "__main__":
    descargar_puntos_temporada("22_23", 1, 38)
