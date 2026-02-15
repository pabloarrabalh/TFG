from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db.models import Sum
from scipy import stats as scipy_stats
from main.models import Temporada, Jugador, EstadisticasPartidoJugador, Posicion


class Command(BaseCommand):
    help = 'Precalcula los percentiles de todos los jugadores para cachearlos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--temporada',
            type=str,
            help='Precalcular solo para una temporada específica (ej: 25_26)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpiar el caché antes de precalcular',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Limpiando caché...")
            cache.clear()
            self.stdout.write(self.style.SUCCESS("✓ Caché limpiado"))

        # Obtener temporadas a procesar
        if options['temporada']:
            temporadas = Temporada.objects.filter(nombre=options['temporada'])
            if not temporadas.exists():
                self.stdout.write(
                    self.style.ERROR(f"Temporada {options['temporada']} no encontrada")
                )
                return
        else:
            temporadas = Temporada.objects.all()

        # Posiciones e stats a cachear
        posiciones = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']
        stats_por_posicion = {
            'Portero': ['goles_en_contra', 'porcentaje_paradas', 'psxg'],
            'Defensa': ['despejes', 'entradas', 'duelos', 'amarillas', 'rojas'],
            'Centrocampista': [
                'pases_totales', 'asist_partido', 'regates_completados', 'duelos'
            ],
            'Delantero': [
                'gol_partido', 'tiro_puerta_partido', 'tiros', 'xg_partido',
                'pases_totales', 'asist_partido', 'xag', 'regates_completados',
                'regates_fallidos', 'conducciones', 'conducciones_progresivas',
                'distancia_conduccion', 'despejes', 'entradas', 'duelos',
                'amarillas', 'rojas'
            ],
        }

        total_jugadores = Jugador.objects.count()
        contador = 0

        for temporada in temporadas:
            self.stdout.write(f"\n📅 Procesando {temporada.nombre}...")

            for posicion in posiciones:
                # Obtener stats para esta posición
                stats_list = stats_por_posicion.get(posicion, [])
                
                # Obtener jugadores de esta posición en esta temporada
                jugadores_posicion = EstadisticasPartidoJugador.objects.filter(
                    posicion=posicion,
                    partido__jornada__temporada=temporada
                ).values('jugador').distinct()

                jugador_ids = [j['jugador'] for j in jugadores_posicion]
                
                if not jugador_ids:
                    continue

                self.stdout.write(
                    f"  {posicion}: {len(jugador_ids)} jugadores, "
                    f"{len(stats_list)} stats"
                )

                # Precalcular cada stat
                for stat_field in stats_list:
                    # Calcular valores para todos los jugadores
                    valores_por_jugador = {}
                    
                    for jug_id in jugador_ids:
                        query = EstadisticasPartidoJugador.objects.filter(
                            jugador_id=jug_id,
                            partido__jornada__temporada=temporada
                        )
                        agg = query.aggregate(stat_value=Sum(stat_field))
                        valor = agg['stat_value'] or 0
                        valores_por_jugador[jug_id] = float(valor)

                    # Lista de valores para percentileofscore
                    valores = list(valores_por_jugador.values())

                    if not valores:
                        continue

                    # Cachear percentiles
                    for jug_id, jugador_value in valores_por_jugador.items():
                        try:
                            jugador_obj = Jugador.objects.get(id=jug_id)
                            percentil = int(
                                scipy_stats.percentileofscore(valores, jugador_value)
                            )

                            cache_key = f"percentil_{jug_id}_{temporada.nombre}_{posicion}_{stat_field}"
                            cache.set(cache_key, percentil, 86400)  # 24 horas
                            contador += 1

                        except Jugador.DoesNotExist:
                            pass

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Precálculo completado: {contador} percentiles cacheados"
            )
        )
