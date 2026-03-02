"""
API REST para funcionalidades específicas
Base URL: /api/v1/
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from main.models import Jugador, Temporada, EstadisticasPartidoJugador
from django.db.models import Sum, Q, Count, F
from scipy import stats as scipy_stats
import logging
import json

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def api_radar_jugador(request, jugador_id, temporada):
    """
    GET /api/v1/radar/{jugador_id}/{temporada}/
    
    Génera datos de perfil táctico (radar chart) para un jugador en una temporada específica.
    
    Parámetros (URL):
        - jugador_id (int): ID del jugador
        - temporada (str): Nombre de la temporada (ej: "2023-2024")
    
    Respuesta exitosa (200):
    {
        "status": "success",
        "data": {
            "jugador_id": 123,
            "jugador_nombre": "Juan Pérez",
            "temporada": "2023-2024",
            "posicion": "Delantero",
            "radar_values": [85, 65, 75, 80, 90, 88, 82],
            "media_general": 81.57,
            "labels": ["Ataque", "Defensa", "Regate", "Pases", "Comportamiento", "Minutos", "Fantasy"]
        }
    }
    
    Respuesta de error (400):
    {
        "status": "error",
        "message": "Descripción del error"
    }
    """
    try:
        # Obtener jugador
        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except Jugador.DoesNotExist:
            logger.error(f"Jugador {jugador_id} no encontrado")
            return JsonResponse({'error': 'Jugador no encontrado'}, status=400)
        
        # Obtener temporada
        try:
            temp_obj = Temporada.objects.get(nombre=temporada)
        except Temporada.DoesNotExist:
            logger.error(f"Temporada {temporada} no encontrada")
            return JsonResponse({'error': 'Temporada no encontrada'}, status=400)
        
        # Obtener posición del jugador
        posicion = jugador.get_posicion_mas_frecuente()
        if not posicion:
            logger.warning(f"Jugador {jugador_id} sin posición detectada")
            return JsonResponse({'radar_values': [50]*7, 'media_general': 50}, status=200)
        
        # Función para calcular percentil - OPTIMIZADA
        def calcular_pct(stat_field):
            """Calcula el percentil para un stat en esta temporada y posición"""
            try:
                # Obtener ALL stats de jugadores de la misma posición en una sola query
                stats_todos = EstadisticasPartidoJugador.objects.filter(
                    posicion=posicion,
                    partido__jornada__temporada=temp_obj
                ).values('jugador').annotate(
                    total_stat=Sum(stat_field)
                )
                
                if not stats_todos.exists():
                    return 50
                
                # Crear lista de valores
                valores = []
                jugador_valor = None
                
                for stat in stats_todos:
                    val = stat['total_stat'] or 0
                    valores.append(float(val))
                    if stat['jugador'] == jugador.id:
                        jugador_valor = float(val)
                
                # Si el jugador no tiene datos, retornar 50
                if jugador_valor is None:
                    return 50
                
                # Calcular percentil
                pct = int(scipy_stats.percentileofscore(valores, jugador_valor))
                return max(0, min(100, pct))  # Asegurarse que está entre 0-100
            
            except Exception as e:
                logger.error(f"Error al calcular percentil {stat_field}: {str(e)}")
                return 50
        
        # Minutos y puntos normalizados (comunes a todos)
        stats_jugador = EstadisticasPartidoJugador.objects.filter(
            jugador=jugador,
            partido__jornada__temporada=temp_obj
        ).aggregate(
            total_minutos=Sum('min_partido'),
            total_puntos=Sum('puntos_fantasy'),
            partidos=Count('id', filter=Q(min_partido__gt=0))
        )

        minutos_totales = stats_jugador['total_minutos'] or 0
        minutos_percentil = min(100, (minutos_totales / 2700) * 100) if minutos_totales > 0 else 0

        puntos_totales = stats_jugador['total_puntos'] or 0
        partidos = stats_jugador['partidos'] or 1
        puntos_promedio = puntos_totales / partidos if partidos > 0 else 0
        puntos_percentil = min(100, (puntos_promedio / 10) * 100) if puntos_promedio > 0 else 0

        if posicion == 'Portero':
            # ── PERFIL PORTERO: Pases · Minutos · Puntos · Comportamiento · Paradas · GEC · PSxG ──
            pases_pct = calcular_pct('pases_totales')
            comportamiento_pct = 100 - calcular_pct('amarillas')
            paradas_pct = calcular_pct('porcentaje_paradas')
            gec_pct = 100 - calcular_pct('goles_en_contra')  # Menos goles encajados = mejor
            psxg_pct = calcular_pct('psxg')  # Post-shot xG: calidad de las paradas

            radar_values = [
                round(pases_pct, 1),
                round(minutos_percentil, 1),
                round(puntos_percentil, 1),
                round(comportamiento_pct, 1),
                round(paradas_pct, 1),
                round(gec_pct, 1),
                round(psxg_pct, 1),
            ]
            labels = ['Pases', 'Minutos', 'Puntos', 'Comportamiento', 'Paradas %', 'GEC', 'PSxG']
        else:
            # ── PERFIL JUGADOR DE CAMPO ──
            ataque_avg = (
                calcular_pct('gol_partido') +
                calcular_pct('tiro_puerta_partido') +
                calcular_pct('xg_partido')
            ) / 3

            defensa_avg = (
                calcular_pct('despejes') +
                calcular_pct('entradas') +
                calcular_pct('duelos')
            ) / 3

            regates_avg = (
                calcular_pct('regates_completados') +
                calcular_pct('conducciones')
            ) / 2

            pases_avg = (
                calcular_pct('pases_totales') +
                calcular_pct('asist_partido')
            ) / 2

            comportamiento_avg = 100 - calcular_pct('amarillas')

            radar_values = [
                round(ataque_avg, 1),
                round(defensa_avg, 1),
                round(regates_avg, 1),
                round(pases_avg, 1),
                round(comportamiento_avg, 1),
                round(minutos_percentil, 1),
                round(puntos_percentil, 1),
            ]
            labels = ['Ataque', 'Defensa', 'Regate', 'Pases', 'Comportamiento', 'Minutos', 'Fantasy']

        media_general = sum(radar_values) / len(radar_values) if radar_values else 0

        logger.info(f"Radar generado para jugador {jugador_id} ({posicion}) en {temporada}: {radar_values}")

        return JsonResponse({
            'status': 'success',
            'data': {
                'jugador_id': jugador.id,
                'jugador_nombre': f"{jugador.nombre} {jugador.apellido}",
                'temporada': temporada,
                'posicion': posicion,
                'radar_values': radar_values,
                'media_general': round(media_general, 2),
                'labels': labels,
            }
        }, status=200)
    
    except Exception as e:
        logger.error(f"Error general en API radar: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@require_http_methods(["GET"])
@csrf_exempt
def api_buscar(request):
    """
    GET /api/buscar/?q=QUERY
    Busca jugadores y equipos usando Elasticsearch
    Requiere al menos 3 caracteres
    Retorna máximo 5 resultados
    """
    try:
        query = request.GET.get('q', '').strip()
        
        if len(query) < 3:
            return JsonResponse({
                'status': 'error',
                'message': 'Mínimo 3 caracteres requeridos',
                'results': []
            }, status=400)
        
        try:
            from main.elasticsearch_docs import ELASTICSEARCH_AVAILABLE
            
            if not ELASTICSEARCH_AVAILABLE:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Elasticsearch no está disponible',
                    'results': []
                }, status=503)
            
            from elasticsearch_dsl import connections, Q, Search
        except ImportError as e:
            logger.error(f"Error importando elasticsearch: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Elasticsearch no está configurado',
                'results': []
            }, status=503)
        
        resultados = []
        
        try:
            client = connections.get_connection()
            from elasticsearch_dsl import Q
            
            # Búsqueda de jugadores - Usar prefix query para encontrar desde primeras letras
            try:
                search_jugador = Search(using=client, index='jugadores')
                
                # Query con prefix: busca coincidencias desde el inicio
                q = Q('bool', should=[
                    # Búsqueda por prefijo (lo más importante)
                    Q('prefix', nombre_completo={'value': query.lower(), 'boost': 5}),
                    Q('prefix', nombre={'value': query.lower(), 'boost': 4}),
                    Q('prefix', apellido={'value': query.lower(), 'boost': 4}),
                    # Búsqueda exacta como respaldo
                    Q('match', nombre_completo={'query': query, 'boost': 3}),
                    Q('match', nombre={'query': query, 'boost': 2}),
                    Q('match', apellido={'query': query, 'boost': 2}),
                    # Fuzzy como último recurso
                    Q('match', nombre_completo={'query': query, 'fuzziness': 1, 'boost': 1}),
                ], minimum_should_match=1)
                
                search_jugador = search_jugador.query(q)[:5]
                response = search_jugador.execute()
                
                for hit in response:
                    # hit.meta.id may be a name slug from old ES index — always
                    # resolve to a reliable numeric DB id using nombre/apellido.
                    try:
                        hit_nombre = getattr(hit, 'nombre', '')
                        hit_apellido = getattr(hit, 'apellido', '')
                        # Try _source numeric id first
                        source_id = getattr(hit, 'id', None)
                        if source_id and str(source_id).lstrip('-').isdigit():
                            jugador_pk = int(source_id)
                        else:
                            # Fall back: look up in DB by name
                            jobj = Jugador.objects.filter(
                                nombre=hit_nombre, apellido=hit_apellido
                            ).values_list('id', flat=True).first()
                            jugador_pk = jobj
                    except Exception:
                        jugador_pk = None

                    if jugador_pk:
                        resultados.append({
                            'type': 'jugador',
                            'id': jugador_pk,
                            'nombre': f"{hit_nombre} {hit_apellido}",
                            'posicion': getattr(hit, 'posicion', 'Desconocida'),
                            'url': f'/jugador/{jugador_pk}/'
                        })
            except Exception as e:
                logger.warning(f"Error en búsqueda de jugadores: {str(e)}")
            
            # Búsqueda de equipos
            try:
                # Obtener la temporada actual (últimaDisponible)
                temporadas = Temporada.objects.all().order_by('-nombre')
                temporada_actual = temporadas.first().nombre if temporadas.exists() else '25_26'
                
                search_equipo = Search(using=client, index='equipos')
                
                q_equipo = Q('bool', should=[
                    # Búsqueda por prefijo
                    Q('prefix', nombre={'value': query.lower(), 'boost': 5}),
                    Q('prefix', estadio={'value': query.lower(), 'boost': 2}),
                    # Búsqueda exacta
                    Q('match', nombre={'query': query, 'boost': 3}),
                    Q('match', estadio={'query': query, 'boost': 1}),
                ], minimum_should_match=1)
                
                search_equipo = search_equipo.query(q_equipo)[:5]
                response = search_equipo.execute()
                
                for hit in response:
                    resultados.append({
                        'type': 'equipo',
                        'id': hit.id,
                        'nombre': hit.nombre,
                        'url': f'/equipo/{hit.nombre}/{temporada_actual}/'
                    })
            except Exception as e:
                logger.warning(f"Error en búsqueda de equipos: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error obteniendo conexión: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Error conectando a Elasticsearch',
                'results': []
            }, status=503)
        
        # Limitar a 5 resultados totales
        resultados = resultados[:5]
        
        return JsonResponse({
            'status': 'success',
            'results': resultados
        }, status=200)
    
    except Exception as e:
        logger.error(f"Error en API búsqueda: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'results': []
        }, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def api_toggle_favorito(request):
    """
    POST /api/favoritos/toggle/
    Marca/deserca un equipo como favorito
    body: {equipo_id: int}
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'message': 'Debes iniciar sesión',
                'error_code': 'not_authenticated'
            }, status=401)
        
        import json
        body = json.loads(request.body)
        equipo_id = body.get('equipo_id')
        
        if not equipo_id:
            return JsonResponse({
                'status': 'error',
                'message': 'equipo_id es requerido'
            }, status=400)
        
        from main.models import Equipo, EquipoFavorito
        
        try:
            equipo = Equipo.objects.get(id=equipo_id)
        except Equipo.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Equipo no encontrado'
            }, status=404)
        
        # Toggler: si existe, eliminar; si no existe, crear
        favorito, created = EquipoFavorito.objects.get_or_create(
            usuario=request.user,
            equipo=equipo
        )
        
        if not created:
            # Ya existía, así que lo eliminamos (toggle off)
            favorito.delete()
            return JsonResponse({
                'status': 'success',
                'is_favorite': False,
                'message': 'Equipo removido de favoritos'
            }, status=200)
        else:
            # Se creó nuevo, así que está activado (toggle on)
            return JsonResponse({
                'status': 'success',
                'is_favorite': True,
                'message': 'Equipo agregado a favoritos'
            }, status=200)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Error en toggle de favoritos: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)