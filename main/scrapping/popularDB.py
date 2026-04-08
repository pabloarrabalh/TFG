import logging
import os
import sys
import time

# Configurar logging ANTES de django setup
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
    force=True
)
_log = logging.getLogger(__name__)
_log.info("Iniciando popularDB script...")
sys.stdout.flush()

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

_log.info("Ejecutando django.setup()...")
sys.stdout.flush()
django.setup()
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
    force=True,
)
_log.info("Django setup completado correctamente")
sys.stdout.flush()


def main():
    """Función principal: ejecuta todas las fases."""
    _log.info("ENTRANDO EN main()...")
    sys.stdout.flush()
    _log.info("Importando modelos Django...")
    sys.stdout.flush()
    from main.models import Calendario, Equipo, EstadisticasPartidoJugador, Jugador, Partido, Temporada
    _log.info("Modelos importados OK")
    sys.stdout.flush()

    _log.info("Importando fbref...")
    sys.stdout.flush()
    from main.scrapping.fbref import scrappear_calendario_para_bd
    _log.info("fbref importado OK")
    sys.stdout.flush()

    _log.info("Importando fases_calendario...")
    sys.stdout.flush()
    from main.scrapping.populardb.fases_calendario import (
        fase_2g_cargar_goles_desde_calendario,
        fase_3_cargar_calendario,
    )
    _log.info("fases_calendario importado OK")
    sys.stdout.flush()

    _log.info("Importando fases_complementarias...")
    sys.stdout.flush()
    from main.scrapping.populardb.fases_complementarias import (
        fase_2_cargar_roles,
        fase_2b_cargar_goles,
        fase_2c_cargar_clasificacion,
        fase_2d_cargar_rendimiento,
        fase_2e_poblar_equipo_jugador_temporada,
        fase_2f_completar_estadios,
    )
    _log.info("fases_complementarias importado OK")
    sys.stdout.flush()

    _log.info("Importando fases_partidos...")
    sys.stdout.flush()
    from main.scrapping.populardb.fases_partidos import (
        actualizar_fechas_jornadas,
        fase_0_scrapear_plantillas_y_estadios,
        fase_0a_crear_todas_las_jornadas,
        fase_1_cargar_partidos_y_estadisticas,
        procesar_csv_partido,
    )
    _log.info("fases_partidos importado OK")
    sys.stdout.flush()

    _log.info("Importando fases_percentiles...")
    sys.stdout.flush()
    from main.scrapping.populardb.fases_percentiles import fase_4_precalcular_percentiles
    _log.info("fases_percentiles importado OK")
    sys.stdout.flush()

    _log.info("Importando helpers...")
    sys.stdout.flush()
    from main.scrapping.populardb.helpers import (
        _puntos_fantasy_sin_outlier,
        obtener_o_crear_equipo,
        obtener_o_crear_equipo_jugador_temporada,
        obtener_o_crear_equipo_temporada,
        obtener_o_crear_jornada,
        obtener_o_crear_jugador,
        obtener_o_crear_partido,
        obtener_o_crear_temporada,
    )
    _log.info("Todos los módulos importados correctamente")
    sys.stdout.flush()
    
    start_time = time.time()
    
    _log.info("=" * 60)
    _log.info("INICIANDO CARGA COMPLETA DE DATOS - popularDB")
    _log.info("=" * 60)
    sys.stdout.flush()
    
    # FASE 0a: Crear todas las jornadas PRIMERO (CRÍTICO)
    _log.info("FASE 0a: Creando todas las jornadas...")
    sys.stdout.flush()
    fase_0a_crear_todas_las_jornadas()
    _log.info("FASE 0a completada. Temporadas: %d", Temporada.objects.count())
    sys.stdout.flush()
    
    # FASE 0: Scrapear plantillas y actualizar estadios
    _log.info("FASE 0: Scrapeando plantillas y datos de estadios...")
    sys.stdout.flush()
    fase_0_scrapear_plantillas_y_estadios()
    _log.info("FASE 0 completada. Equipos: %d", Equipo.objects.count())
    sys.stdout.flush()
    
    # FASE 1: Partidos y Estadísticas
    _log.info("FASE 1: Cargando partidos y estadísticas desde CSV...")
    sys.stdout.flush()
    fase_1_cargar_partidos_y_estadisticas()
    _log.info("FASE 1 completada. Partidos: %d, Estadísticas: %d", 
              Partido.objects.count(), EstadisticasPartidoJugador.objects.count())
    sys.stdout.flush()
    
    # FASE 2: Datos complementarios
    _log.info("FASE 2a: Cargando roles...")
    fase_2_cargar_roles()
    _log.info("FASE 2a completada.")
    
    _log.info("FASE 2b: Cargando goles...")
    fase_2b_cargar_goles()
    _log.info("FASE 2b completada.")
    
    _log.info("FASE 2c: Cargando clasificación...")
    fase_2c_cargar_clasificacion()
    _log.info("FASE 2c completada.")
    
    _log.info("FASE 2d: Calculando rendimiento histórico...")
    fase_2d_cargar_rendimiento()
    _log.info("FASE 2d completada.")
    
    _log.info("FASE 2e: Poblando EquipoJugadorTemporada...")
    fase_2e_poblar_equipo_jugador_temporada()
    _log.info("FASE 2e completada.")
    
    _log.info("FASE 2f: Completando datos de estadios...")
    fase_2f_completar_estadios()
    _log.info("FASE 2f completada.")
    
    # FASE FBREF: Scrappear calendario desde FBREF con resultados
    _log.info("FASE FBREF: Scrapeando calendario desde FBREF...")
    scrappear_calendario_para_bd()
    _log.info("FASE FBREF completada.")
    
    # FASE 3: Cargar Calendario base y Goles desde JSON
    _log.info("FASE 3: Cargando calendario base desde JSON...")
    fase_3_cargar_calendario()
    _log.info("FASE 3 completada. Calendarios: %d", Calendario.objects.count())
    
    _log.info("FASE 2g: Cargando goles desde calendario JSON...")
    fase_2g_cargar_goles_desde_calendario()
    _log.info("FASE 2g completada.")
    
    # FASE 4: Precalcular percentiles y guardarlos en EquipoJugadorTemporada
    _log.info("FASE 4: Precalculando percentiles...")
    fase_4_precalcular_percentiles()
    _log.info("FASE 4 completada.")
    
    elapsed = time.time() - start_time
    _log.info("=" * 60)
    _log.info("CARGA COMPLETADA EXITOSAMENTE")
    _log.info("=" * 60)
    _log.info("Resumen final:")
    _log.info("  Temporadas: %d", Temporada.objects.count())
    _log.info("  Equipos: %d", Equipo.objects.count())
    _log.info("  Jugadores: %d", Jugador.objects.count())
    _log.info("  Partidos: %d", Partido.objects.count())
    _log.info("  Estadísticas: %d", EstadisticasPartidoJugador.objects.count())
    _log.info("  Calendarios: %d", Calendario.objects.count())
    _log.info("Tiempo total: %.2f segundos", elapsed)
    _log.info("=" * 60)


if __name__ == "__main__":
    main()
