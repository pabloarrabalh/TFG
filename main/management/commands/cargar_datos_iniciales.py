from django.core.management.base import BaseCommand
from django.db.models import Count
import os


class Command(BaseCommand):
    help = 'Carga datos iniciales de la BD (equipos, jugadores, partidos, estadísticas)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-if-exists',
            action='store_true',
            help='Salta la carga si ya existen datos en la BD',
        )

    def handle(self, *args, **options):
        from main.models import Equipo, Jugador, Partido, Jornada

        verbosity = int(options.get('verbosity', 1))

        # Verify database is empty after flush
        if verbosity >= 1:
            self.stdout.write('[INFO] Paso 1/5 - Verificando base de datos vacía...')
        
        jornada_count = Jornada.objects.count()
        equipo_count = Equipo.objects.count()
        
        if jornada_count > 0 or equipo_count > 0:
            self.stdout.write(
                self.style.WARNING(f'[WARN] BD no está vacía ({jornada_count} jornadas, {equipo_count} equipos)')
            )
        else:
            self.stdout.write('[OK] BD vacía, lista para cargar datos')
        
        if verbosity >= 1:
            self.stdout.write('[INFO] Paso 2/5 - Cargando datos iniciales...')

        # Disconnect the auto-prediction signal to avoid spawning thousands of
        # background threads (one per stat row) that exhaust DB connections.
        from django.db.models.signals import post_save
        from main.models import EstadisticasPartidoJugador
        from main import signals as main_signals
        signal_disconnected = False
        if hasattr(main_signals, 'auto_generar_prediccion'):
            post_save.disconnect(main_signals.auto_generar_prediccion, sender=EstadisticasPartidoJugador)
            signal_disconnected = True

        try:
            from main.scrapping.popularDB import (
                fase_0a_crear_todas_las_jornadas,
                fase_1_cargar_partidos_y_estadisticas,
                fase_2_cargar_roles,
                fase_2b_cargar_goles,
                fase_2c_cargar_clasificacion,
                fase_2d_cargar_rendimiento,
                fase_2e_poblar_equipo_jugador_temporada,
                fase_2f_completar_estadios,
                fase_2g_cargar_goles_desde_calendario,
                fase_3_cargar_calendario,
                fase_4_precalcular_percentiles,
            )

            if verbosity >= 2:
                self.stdout.write('[INFO] Paso 1 - Creando jornadas y cargando partidos...')
            
            fase_0a_crear_todas_las_jornadas()
            fase_1_cargar_partidos_y_estadisticas()
            fase_2_cargar_roles()
            fase_2b_cargar_goles()
            fase_2c_cargar_clasificacion()
            fase_2d_cargar_rendimiento()
            fase_2e_poblar_equipo_jugador_temporada()
            fase_2f_completar_estadios()
            fase_2g_cargar_goles_desde_calendario()
            fase_3_cargar_calendario()
            
            if verbosity >= 2:
                self.stdout.write('[INFO] Paso 2 - Calculando percentiles...')
            
            fase_4_precalcular_percentiles()

            if verbosity >= 1:
                self.stdout.write(self.style.SUCCESS('[SUCCESS] Datos cargados exitosamente'))

        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(f'[ERROR] Error de importación: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'[ERROR] Error durante carga de datos: {str(e)}')
            )
        finally:
            if signal_disconnected:
                try:
                    post_save.connect(main_signals.auto_generar_prediccion, sender=EstadisticasPartidoJugador)
                except Exception:
                    pass
