import sys
import logging
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand
from django.db.models import Max

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Genera predicciones de puntos fantasy para todos los jugadores'

    def add_arguments(self, parser):
        parser.add_argument('--jornada',   type=int,  default=None,  help='Número de jornada objetivo')
        parser.add_argument('--temporada', type=str,  default=None,  help='Nombre de temporada BD: 25_26')
        parser.add_argument('--jugador',   type=int,  default=None,  help='Solo predecir para este jugador_id')
        parser.add_argument('--modelo',    type=str,  default='RF',  help='RF | XGB | ElasticNet (default: RF)')
        parser.add_argument('--all-modelos', action='store_true',    help='Genera baseline + rf + ridge + xgb + elasticnet para cada jugador/jornada')
        parser.add_argument('--workers',   type=int,  default=32,    help='Hilos paralelos (default: 32 - máximo recomendado)')
        parser.add_argument('--force',     action='store_true',       help='Sobreescribe predicciones existentes')
        parser.add_argument('--batch',     type=int,  default=300,   help='Tamaño de batch para guardar (default: 300 - más rápido)')
        parser.add_argument('--next-only', action='store_true',       help='Solo generar para próxima jornada (última+1)')
        parser.add_argument('--all-jornadas', action='store_true',    help='Generar para TODAS las jornadas de la temporada')
        parser.add_argument('--active-only', action='store_true',     help='Solo genera para jugadores con 60+ minutos en últimas 10 jornadas (reduce tiempo ~70%)')
        parser.add_argument('--init-active-only', action='store_true', help='[INIT] Solo primeros 10 partidos de 25/26 con 60+ minutos')
        parser.add_argument('--min-minutes', type=int, default=60,    help='Minutos mínimos para considerar jugador activo (default: 60)')
        parser.add_argument('--sin-filtro-minutos', action='store_true', help='Desactiva el filtro de minutos y considera a todos los jugadores')
        parser.add_argument('--mark-incomplete', action='store_true', help='Marca predicciones no generadas como pendientes para background')

    # ─────────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        from main.models import Temporada, Jornada, EquipoJugadorTemporada, PrediccionJugador

        verbosity = int(options.get('verbosity', 1))

        # ── Resolver temporada ──────────────────────────────────────────────
        if options['temporada']:
            try:
                temporada = Temporada.objects.get(nombre=options['temporada'])
            except Temporada.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Temporada '{options['temporada']}' no encontrada"))
                return
        else:
            temporada = Temporada.objects.order_by('-nombre').first()
            if not temporada:
                self.stderr.write(self.style.ERROR("No hay temporadas en la BD"))
                return

        if verbosity >= 2:
            self.stdout.write(f"Temporada: {temporada.nombre}")

        # ── Resolver jornada ────────────────────────────────────────────────
        if options['next_only'] or options['all_jornadas']:
            # Modo prioritario: solo próxima jornada, o todas
            from main.models import EstadisticasPartidoJugador
            ultima_j_pk = (EstadisticasPartidoJugador.objects
                .filter(partido__jornada__temporada=temporada)
                .order_by('-partido__jornada__numero_jornada')
                .values_list('partido__jornada', flat=True)
                .first())
            if not ultima_j_pk:
                self.stderr.write(self.style.ERROR("No hay estadísticas registradas para esta temporada"))
                return
            ultima_jornada = Jornada.objects.get(pk=ultima_j_pk)
            ultima_numero = ultima_jornada.numero_jornada

            if options['next_only']:
                # Solo próxima jornada
                jornadas_target = [ultima_numero + 1]
            else:  # all_jornadas
                # TODAS las jornadas de la temporada (1 a max), no solo las después de la última con stats
                jornadas_target = list(
                    Jornada.objects.filter(temporada=temporada)
                    .order_by('numero_jornada')
                    .values_list('numero_jornada', flat=True)
                )
            
            if not jornadas_target:
                self.stderr.write(self.style.ERROR(f"No hay jornadas para procesar (última con stats: {ultima_numero})"))
                return

        elif options['jornada']:
            # Jornada específica (opción original)
            try:
                jornada = Jornada.objects.get(temporada=temporada, numero_jornada=options['jornada'])
                jornadas_target = [options['jornada']]
            except Jornada.DoesNotExist:
                self.stderr.write(self.style.ERROR(
                    f"Jornada {options['jornada']} no encontrada en {temporada.nombre}"
                ))
                return
        else:
            # Default: última jornada con estadísticas
            from main.models import EstadisticasPartidoJugador
            ultima_j_pk = (EstadisticasPartidoJugador.objects
                .filter(partido__jornada__temporada=temporada)
                .order_by('-partido__jornada__numero_jornada')
                .values_list('partido__jornada', flat=True)
                .first())
            if not ultima_j_pk:
                self.stderr.write(self.style.ERROR("No hay estadísticas registradas para esta temporada"))
                return
            jornada = Jornada.objects.get(pk=ultima_j_pk)
            jornadas_target = [jornada.numero_jornada]

        if verbosity >= 2:
            if len(jornadas_target) == 1:
                self.stdout.write(f"Jornada objetivo: J{jornadas_target[0]}")
            else:
                self.stdout.write(f"Jornadas objetivo: J{jornadas_target[0]} a J{jornadas_target[-1]} ({len(jornadas_target)} jornadas)")

        # ── Construir lista de jugadores ────────────────────────────────────
        if options['jugador']:
            from main.models import Jugador
            try:
                jug = Jugador.objects.get(pk=options['jugador'])
                ejt = EquipoJugadorTemporada.objects.filter(
                    jugador=jug, temporada=temporada
                ).first()
                posicion = ejt.posicion if ejt else jug.get_posicion_mas_frecuente() or 'Delantero'
                jugadores_lista = [(jug.pk, posicion)]
            except Jugador.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Jugador {options['jugador']} no encontrado"))
                return
        else:
            jugadores_lista = list(
                EquipoJugadorTemporada.objects
                .filter(temporada=temporada)
                .select_related('jugador')
                .values_list('jugador_id', 'posicion')
                .distinct()
            )
            # Deduplica: si el mismo jugador aparece en varios equipos (traspaso), coge última
            seen = {}
            for jid, pos in jugadores_lista:
                seen[jid] = pos
            jugadores_lista = list(seen.items())
            
            # ── Filtrar jugadores activos ──────────────────────────────────────
            if options['init_active_only']:
                # INIT: Primeros 10 partidos de 25/26 con 60+ minutos
                from main.models import EstadisticasPartidoJugador
                min_minutes = options['min_minutes']
                
                # Solo primeros 10 partidos
                jornadas_init = list(
                    Jornada.objects.filter(temporada=temporada)
                    .order_by('numero_jornada')[:10]
                    .values_list('pk', flat=True)
                )
                
                jugadores_activos = set(
                    EstadisticasPartidoJugador.objects
                    .filter(partido__jornada_id__in=jornadas_init, min_partido__gte=min_minutes)
                    .values_list('jugador_id', flat=True)
                    .distinct()
                )
                
                jugadores_lista = [(jid, pos) for jid, pos in jugadores_lista if jid in jugadores_activos]
                
                if verbosity >= 1:
                    self.stdout.write(
                        f"  [INIT-ACTIVE-ONLY] Primeros 10 partidos 25/26, {min_minutes}+ minutos: "
                        f"{len(jugadores_lista)} de {len(seen)} jugadores"
                    )
            
            elif options['active_only']:
                # NORMAL: Últimas 10 jornadas con 60+ minutos
                from main.models import EstadisticasPartidoJugador
                min_minutes = options['min_minutes']
                jornada_min = max(1, jornadas_target[0] - 10)  # Últimas 10 jornadas
                
                jugadores_activos = set()
                for jornada_num in range(jornada_min, jornadas_target[0]):
                    try:
                        jornada = Jornada.objects.get(temporada=temporada, numero_jornada=jornada_num)
                    except Jornada.DoesNotExist:
                        continue
                    
                    jugadores_con_minutos = set(
                        EstadisticasPartidoJugador.objects
                        .filter(partido__jornada=jornada, min_partido__gte=min_minutes)
                        .values_list('jugador_id', flat=True)
                        .distinct()
                    )
                    jugadores_activos.update(jugadores_con_minutos)
                
                jugadores_lista = [(jid, pos) for jid, pos in jugadores_lista if jid in jugadores_activos]
                
                if verbosity >= 1:
                    self.stdout.write(
                        f"  [ACTIVE-ONLY] Últimas 10 jornadas, {min_minutes}+ minutos: "
                        f"{len(jugadores_lista)} de {len(seen)} jugadores"
                    )

        num_jugadores = len(jugadores_lista)
        num_jornadas = len(jornadas_target)
        modelos_por_tarea = 5 if options.get('all_modelos') else 1
        total_predicciones = num_jugadores * num_jornadas * modelos_por_tarea
        modelos_label = 'baseline+rf+ridge+xgb+elasticnet' if options.get('all_modelos') else options['modelo']
        
        if verbosity >= 2:
            self.stdout.write(
                f"Jugadores: {num_jugadores}  |  Jornadas: {num_jornadas}  "
                f"|  Total predicciones: {total_predicciones}  |  Modelo(s): {modelos_label}  "
                f"|  Workers: {options['workers']}"
            )

        # ── Cargar módulos de predicción una sola vez ───────────────────────
        entrenamientos_path = Path(__file__).resolve().parents[3] / 'main' / 'entrenamientoModelos'
        if str(entrenamientos_path) not in sys.path:
            sys.path.insert(0, str(entrenamientos_path))

        import importlib
        try:
            _predecir_mod = importlib.import_module('predecir')
            _predecir_puntos = getattr(_predecir_mod, 'predecir_puntos')
            if verbosity >= 2:
                self.stdout.write("  [OK] Módulo unificado 'predecir' cargado")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"No se pudo cargar el módulo de predicción: {e}"))
            return

        # ── Obtener objetos Jornada para las jornadas objetivo ─────────────
        jornadas_objs = {}
        for numero_jornada in jornadas_target:
            try:
                j = Jornada.objects.get(temporada=temporada, numero_jornada=numero_jornada)
                jornadas_objs[numero_jornada] = j
            except Jornada.DoesNotExist:
                if verbosity >= 1:
                    self.stdout.write(f"  [SKIP] Jornada {numero_jornada} no existe en {temporada.nombre}")

        if not jornadas_objs:
            self.stderr.write(self.style.ERROR("No hay jornadas válidas para procesar"))
            return

        jornadas_target = list(jornadas_objs.keys())

        # Reglas de negocio:
        # - J1..J5: predicción baseline (media)
        # - Desde J6: solo jugadores con >= min_minutes en CADA una de las 5 jornadas previas
        min_minutes_required = int(options.get('min_minutes') or 60)
        ventana_jornadas = 5
        inicio_filtro_jornada = 6
        baseline_hasta_jornada = inicio_filtro_jornada - 1

        from main.models import EstadisticasPartidoJugador

        jugadores_ids_set = {jid for jid, _ in jugadores_lista}
        minutos_por_jugador_jornada = defaultdict(dict)

        if jugadores_ids_set:
            max_jornada_hist = max(jornadas_target) - 1
            if max_jornada_hist >= 1:
                minutos_qs = (
                    EstadisticasPartidoJugador.objects
                    .filter(
                        partido__jornada__temporada=temporada,
                        jugador_id__in=jugadores_ids_set,
                        partido__jornada__numero_jornada__lte=max_jornada_hist,
                    )
                    .values('jugador_id', 'partido__jornada__numero_jornada')
                    .annotate(min_partido_max=Max('min_partido'))
                )
                for row in minutos_qs:
                    minutos_por_jugador_jornada[row['jugador_id']][row['partido__jornada__numero_jornada']] = int(row['min_partido_max'] or 0)

        elegibles_por_jornada = {}
        for jornada_num in jornadas_target:
            if jornada_num < inicio_filtro_jornada:
                elegibles_por_jornada[jornada_num] = jugadores_ids_set
                continue

            jornadas_previas = range(jornada_num - ventana_jornadas, jornada_num)
            elegibles = set()
            for jugador_id in jugadores_ids_set:
                mins = minutos_por_jugador_jornada.get(jugador_id, {})
                if all(mins.get(prev_jornada, 0) >= min_minutes_required for prev_jornada in jornadas_previas):
                    elegibles.add(jugador_id)
            elegibles_por_jornada[jornada_num] = elegibles

        if verbosity >= 2:
            total_candidatos = len(jugadores_ids_set)
            for jornada_num in jornadas_target:
                if jornada_num >= inicio_filtro_jornada:
                    elegibles = len(elegibles_por_jornada.get(jornada_num, set()))
                    self.stdout.write(
                        f"  [FILTRO MINUTOS] J{jornada_num}: {elegibles}/{total_candidatos} elegibles "
                        f"({min_minutes_required}+ min en J{jornada_num - ventana_jornadas}-J{jornada_num - 1})"
                    )

        _POS_CODE = {
            'Portero': 'PT', 'Defensa': 'DF',
            'Centrocampista': 'MC', 'Delantero': 'DT',
        }
        _MODELO_A_DB = {
            'rf': 'rf',
            'random forest': 'rf',
            'ridge': 'ridge',
            'ridge regression': 'ridge',
            'elasticnet': 'elasticnet',
            'elastic net': 'elasticnet',
            'xgb': 'xgb',
            'xgboost': 'xgb',
            'baseline': 'baseline',
        }
        _DB_A_MODELO_TIPO = {
            'baseline': 'Baseline',
            'rf': 'RF',
            'ridge': 'Ridge',
            'xgb': 'XGB',
            'elasticnet': 'ElasticNet',
        }

        if options.get('all_modelos'):
            modelos_objetivo = ['baseline', 'rf', 'ridge', 'xgb', 'elasticnet']
        else:
            modelo_norm = _MODELO_A_DB.get(str(options['modelo']).lower(), str(options['modelo']).lower())
            if modelo_norm not in _DB_A_MODELO_TIPO:
                self.stderr.write(self.style.ERROR(
                    f"Modelo '{options['modelo']}' no soportado. Usa: baseline, rf, ridge, xgb, elasticnet o --all-modelos"
                ))
                return
            modelos_objetivo = [modelo_norm]

        # Si se piden todos los modelos, el objetivo es cubrir todos los jugadores.
        aplicar_filtro_minutos = not options.get('sin_filtro_minutos', False)
        if options.get('all_modelos'):
            aplicar_filtro_minutos = False

        # ── Predecir ────────────────────────────────────────────────────────
        ok = error = skip = 0
        predicciones_buffer = []  # Buffer global para batch saving
        batch_size = options.get('batch', 100)

        def predecir_uno(jugador_id, posicion, numero_jornada, modelo_db):
            """Wrapper que llama al predictor correcto (sin guardar)."""
            from main.models import PrediccionJugador
            pos_code = _POS_CODE.get(posicion, 'DT')
            jornada_obj = jornadas_objs[numero_jornada]

            # Regla principal: desde J6 solo si jugó >= 60 min en las 5 jornadas previas
            if aplicar_filtro_minutos and numero_jornada >= inicio_filtro_jornada:
                elegibles = elegibles_por_jornada.get(numero_jornada, set())
                if jugador_id not in elegibles:
                    return 'skip', None

            # Compatibilidad de negocio histórica: J1..J5 baseline en modo simple.
            modelo_db_final = modelo_db
            if (not options.get('all_modelos')) and numero_jornada <= baseline_hasta_jornada:
                modelo_db_final = 'baseline'

            modelo_tipo_prediccion = _DB_A_MODELO_TIPO[modelo_db_final]

            # Saltar si ya existe y no --force
            if not options['force']:
                existe = PrediccionJugador.objects.filter(
                    jugador_id=jugador_id,
                    jornada=jornada_obj,
                    modelo=modelo_db_final,
                ).exists()
                if existe:
                    return 'skip', None

            try:
                def _extraer_puntos(res):
                    if not isinstance(res, dict):
                        return None, True
                    if res.get('error'):
                        return None, True
                    pts_local = res.get('prediccion', res.get('puntos_predichos'))
                    return pts_local, False

                resultado = _predecir_puntos(
                    jugador_id,
                    pos_code,
                    numero_jornada,
                    verbose=False,
                    modelo_tipo=modelo_tipo_prediccion,
                )
                pts, fallo = _extraer_puntos(resultado)

                # En modo all-modelos, si falla un modelo no-baseline, usar baseline de respaldo
                if options.get('all_modelos') and modelo_db_final != 'baseline' and (fallo or pts is None):
                    resultado_base = _predecir_puntos(
                        jugador_id,
                        pos_code,
                        numero_jornada,
                        verbose=False,
                        modelo_tipo='Baseline',
                    )
                    pts_base, _ = _extraer_puntos(resultado_base)
                    pts = pts_base
                    fallo = False if pts is not None else True

                if pts is None:
                    # Sin nulos en modo all-modelos: fallback final conservador.
                    if options.get('all_modelos'):
                        pts = 0.0
                    elif fallo:
                        return 'error', None
                    else:
                        return 'skip', None

                if fallo and not options.get('all_modelos'):
                    return 'error', None

                # Devolver objeto sin guardar (lo haremos en batch después)
                from main.models import PrediccionJugador as PJ
                pred_obj = PJ(
                    jugador_id=jugador_id,
                    jornada=jornada_obj,
                    prediccion=float(pts),
                    modelo=modelo_db_final,
                )
                return 'ok', pred_obj
            except Exception as exc:
                logger.exception(f"Error predicción {jugador_id} J{numero_jornada}: {exc}")
                return 'error', None

        # ── Construir lista de tareas (jugador, jornada) ────────────────────
        tareas = []
        for jid, pos in jugadores_lista:
            for num_jornada in jornadas_target:
                for modelo_db in modelos_objetivo:
                    tareas.append((jid, pos, num_jornada, modelo_db))

        total_tareas = len(tareas)

        with ThreadPoolExecutor(max_workers=options['workers']) as pool:
            futures = {
                pool.submit(predecir_uno, jid, pos, num_j, modelo_db): (jid, num_j, modelo_db)
                for jid, pos, num_j, modelo_db in tareas
            }
            for i, future in enumerate(as_completed(futures), 1):
                status, pred_obj = future.result()
                if status == 'ok':
                    ok += 1
                    if verbosity >= 1 and ok % 100 == 0:
                        self.stdout.write(
                            f"[PROGRESO] {ok} predicciones generadas "
                            f"(procesadas: {i}/{total_tareas}, errores: {error}, omitidas: {skip})"
                        )
                    if pred_obj:
                        predicciones_buffer.append(pred_obj)
                        # Guardar batch cuando alcance el tamaño
                        if len(predicciones_buffer) >= batch_size:
                            from main.models import PrediccionJugador
                            PrediccionJugador.objects.bulk_create(
                                predicciones_buffer,
                                ignore_conflicts=True,  # Ignora duplicados por unique_together
                                batch_size=batch_size
                            )
                            predicciones_buffer = []
                elif status == 'error':
                    error += 1
                else:
                    skip += 1
                if verbosity >= 2:
                    if i % 50 == 0 or i == total_tareas:
                        self.stdout.write(
                            f"  {i}/{total_tareas} — [+]{ok}  [!]{error}  [>]{skip} omitidos  (buffer: {len(predicciones_buffer)})",
                            ending='\r'
                        )
                        self.stdout.flush()

        # Guardar predicciones restantes del buffer
        if predicciones_buffer:
            from main.models import PrediccionJugador
            PrediccionJugador.objects.bulk_create(
                predicciones_buffer,
                ignore_conflicts=True,
                batch_size=batch_size
            )

        if verbosity >= 2:
            self.stdout.write('')
        
        jornada_str = f"J{jornadas_target[0]}" if len(jornadas_target) == 1 else f"J{jornadas_target[0]}-{jornadas_target[-1]}"
        self.stdout.write(self.style.SUCCESS(
            f"Completado {jornada_str} | {temporada.nombre}: "
            f"{ok} guardadas  {error} errores  {skip} omitidas"
        ))
