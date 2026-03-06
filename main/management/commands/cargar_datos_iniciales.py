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
        from main.models import Equipo, Jugador, Partido

        # Checar si ya hay datos
        if options['skip_if_exists']:
            equipo_count = Equipo.objects.count()
            jugador_count = Jugador.objects.count()
            partido_count = Partido.objects.count()

            if equipo_count >= 15 and jugador_count >= 200 and partido_count >= 500:
                self.stdout.write(
                    self.style.WARNING(
                        f'⏭️  BD ya tiene datos suficientes ({equipo_count} equipos, {jugador_count} jugadores, {partido_count} partidos). Saltando carga.'
                    )
                )
                return

        self.stdout.write('⏳ Cargando datos iniciales...')

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
            )

            self.stdout.write('📅 Fase 0a: Creando todas las jornadas...')
            fase_0a_crear_todas_las_jornadas()

            self.stdout.write('📊 Fase 1: Cargando partidos y estadísticas desde CSVs...')
            fase_1_cargar_partidos_y_estadisticas()

            self.stdout.write('👥 Fase 2: Cargando roles...')
            fase_2_cargar_roles()

            self.stdout.write('⚽ Fase 2b: Cargando goles en partidos...')
            fase_2b_cargar_goles()

            self.stdout.write('🏆 Fase 2c: Cargando clasificación por jornada...')
            fase_2c_cargar_clasificacion()

            self.stdout.write('📈 Fase 2d: Cargando rendimiento histórico...')
            fase_2d_cargar_rendimiento()

            self.stdout.write('🔗 Fase 2e: Poblando equipo-jugador-temporada...')
            fase_2e_poblar_equipo_jugador_temporada()

            self.stdout.write('🏟️  Fase 2f: Completando estadios...')
            fase_2f_completar_estadios()

            self.stdout.write('⚽ Fase 2g: Cargando goles desde calendario...')
            fase_2g_cargar_goles_desde_calendario()

            self.stdout.write(self.style.SUCCESS('✅ Datos cargados exitosamente'))

        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error de importación: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error durante carga de datos: {str(e)}')
            )
