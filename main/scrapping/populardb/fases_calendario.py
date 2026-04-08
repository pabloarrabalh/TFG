import json
import logging
import os
from datetime import datetime

from django.conf import settings

from main.models import Calendario, Equipo, EstadoPartido, Jornada, Partido, Temporada
from main.scrapping.commons import normalizar_equipo_bd, parsear_fecha


def fase_3_cargar_calendario():
    """FASE 3: Carga el calendario desde JSON a la tabla Calendario en BD."""
    _log = logging.getLogger(__name__)

    temporadas_map = {
        "temporada_23_24": "23_24",
        "temporada_24_25": "24_25",
        "temporada_25_26": "25_26",
    }

    csv_dir = os.path.join(settings.BASE_DIR, "csv", "csvGenerados")
    total_cargados = 0
    equipos_no_encontrados = set()

    for temp_dir, temp_codigo in temporadas_map.items():
        json_path = os.path.join(csv_dir, f"calendario_{temp_codigo}.json")
        if not os.path.exists(json_path):
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                calendario_dict = json.load(f)

            temporada = Temporada.objects.get(nombre=temp_codigo)

            for jornada_num_str, matches in calendario_dict.items():
                try:
                    jornada_num = int(jornada_num_str)
                    jornada = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)

                    for match_info in matches:
                        try:
                            match_str = match_info.get("match", "")
                            fecha_str = match_info.get("fecha", "")
                            hora_str = match_info.get("hora", "")

                            if not match_str:
                                continue

                            if " vs " not in match_str.lower():
                                continue

                            partes = match_str.lower().split(" vs ")
                            if len(partes) != 2:
                                continue

                            equipo_local_nombre = normalizar_equipo_bd(partes[0].strip())
                            equipo_visitante_nombre = normalizar_equipo_bd(partes[1].strip())

                            try:
                                equipo_local = Equipo.objects.get(nombre=equipo_local_nombre)
                            except Equipo.DoesNotExist:
                                equipos_no_encontrados.add(f"{equipo_local_nombre} (local)")
                                continue

                            try:
                                equipo_visitante = Equipo.objects.get(nombre=equipo_visitante_nombre)
                            except Equipo.DoesNotExist:
                                equipos_no_encontrados.add(f"{equipo_visitante_nombre} (visitante)")
                                continue

                            fecha = parsear_fecha(fecha_str).date()

                            hora = None
                            if hora_str and hora_str.strip():
                                try:
                                    hora = datetime.strptime(hora_str, "%H:%M").time()
                                except Exception:
                                    hora = None

                            _, created = Calendario.objects.update_or_create(
                                jornada=jornada,
                                equipo_local=equipo_local,
                                equipo_visitante=equipo_visitante,
                                defaults={
                                    "fecha": fecha,
                                    "hora": hora,
                                    "match_str": match_str,
                                },
                            )

                            if created:
                                total_cargados += 1
                        except Exception:
                            continue

                except Exception:
                    continue
        except Exception as e:
            _log.warning("[FASE 3] Error procesando %s: %s", json_path, e)
            continue

    if equipos_no_encontrados:
        muestra = ", ".join(sorted(equipos_no_encontrados)[:10])
        _log.warning(
            "[FASE 3] Equipos no encontrados (%d). Muestra: %s",
            len(equipos_no_encontrados),
            muestra,
        )

    total_calendario = Calendario.objects.count()
    _log.info("[FASE 3] Calendario: %d partidos en BD (%d nuevos)", total_calendario, total_cargados)
    return total_calendario


def fase_2g_cargar_goles_desde_calendario():
    """Carga goles desde los calendarios JSON de FBREF."""
    _log = logging.getLogger(__name__)

    temporadas = ["23_24", "24_25", "25_26"]
    total_actualizado = 0
    total_procesados = 0

    for cod_temporada in temporadas:
        try:
            temporada = Temporada.objects.get(nombre=cod_temporada)
        except Temporada.DoesNotExist:
            continue

        json_path = os.path.join(settings.BASE_DIR, "csv", "csvGenerados", f"calendario_{cod_temporada}.json")
        if not os.path.exists(json_path):
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                calendario = json.load(f)

            for jornada_str, partidos in calendario.items():
                jornada_num = int(jornada_str)

                try:
                    jornada = Jornada.objects.get(numero_jornada=jornada_num, temporada=temporada)
                except Jornada.DoesNotExist:
                    continue

                for match in partidos:
                    if "resultado" not in match:
                        continue

                    total_procesados += 1

                    try:
                        match_str = match.get("match", "")
                        resultado = match.get("resultado", "")

                        partes = resultado.split("-")
                        if len(partes) != 2:
                            continue

                        try:
                            goles_local = int(partes[0].strip())
                            goles_visitante = int(partes[1].strip())
                        except ValueError:
                            continue

                        equipos = match_str.lower().split(" vs ")
                        if len(equipos) != 2:
                            continue

                        equipo_local_nombre = normalizar_equipo_bd(equipos[0].strip())
                        equipo_visitante_nombre = normalizar_equipo_bd(equipos[1].strip())

                        try:
                            equipo_local = Equipo.objects.get(nombre=equipo_local_nombre)
                        except Equipo.DoesNotExist:
                            continue

                        try:
                            equipo_visitante = Equipo.objects.get(nombre=equipo_visitante_nombre)
                        except Equipo.DoesNotExist:
                            continue

                        partido = Partido.objects.filter(
                            jornada=jornada,
                            equipo_local=equipo_local,
                            equipo_visitante=equipo_visitante,
                        ).first()

                        if partido:
                            partido.goles_local = goles_local
                            partido.goles_visitante = goles_visitante
                            partido.estado = EstadoPartido.JUGADO
                            partido.save(update_fields=["goles_local", "goles_visitante", "estado"])
                            total_actualizado += 1

                    except Exception:
                        continue

        except Exception as e:
            _log.warning("[Goles] Error procesando %s: %s", json_path, e)
            continue

    _log.info(
        "[Goles] %d actualizados (de %d), total con goles: %d",
        total_actualizado,
        total_procesados,
        Partido.objects.exclude(goles_local__isnull=True).count(),
    )
