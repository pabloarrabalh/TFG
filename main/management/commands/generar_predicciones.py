"""
Genera predicciones de puntos fantasy para todos los jugadores de una jornada
y las almacena en PrediccionJugador.

Uso básico (predice próxima jornada de la temporada más reciente):
    python manage.py generar_predicciones

Opciones:
    --jornada 15          Número de jornada objetivo
    --temporada 25_26     Temporada (formato BD: 25_26)
    --jugador 123         Solo para un jugador específico
    --modelo RF           Tipo de modelo: RF | XGB | ElasticNet
    --workers 4           Hilos paralelos (default: 4)
    --force               Sobreescribe predicciones existentes
"""

import sys
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Genera predicciones de puntos fantasy para todos los jugadores'

    def add_arguments(self, parser):
        parser.add_argument('--jornada',   type=int,  default=None,  help='Número de jornada objetivo')
        parser.add_argument('--temporada', type=str,  default=None,  help='Nombre de temporada BD: 25_26')
        parser.add_argument('--jugador',   type=int,  default=None,  help='Solo predecir para este jugador_id')
        parser.add_argument('--modelo',    type=str,  default='RF',  help='RF | XGB | ElasticNet (default: RF)')
        parser.add_argument('--workers',   type=int,  default=8,     help='Hilos paralelos (default: 8)')
        parser.add_argument('--force',     action='store_true',       help='Sobreescribe predicciones existentes')
        parser.add_argument('--batch',     type=int,  default=100,   help='Tamaño de batch para guardar (default: 100)')

    # ─────────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        from main.models import Temporada, Jornada, EquipoJugadorTemporada, PrediccionJugador

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

        self.stdout.write(f"Temporada: {temporada.nombre}")

        # ── Resolver jornada ────────────────────────────────────────────────
        if options['jornada']:
            try:
                jornada = Jornada.objects.get(temporada=temporada, numero_jornada=options['jornada'])
            except Jornada.DoesNotExist:
                self.stderr.write(self.style.ERROR(
                    f"Jornada {options['jornada']} no encontrada en {temporada.nombre}"
                ))
                return
        else:
            # Última jornada que tenga estadísticas registradas
            from main.models import EstadisticasPartidoJugador
            ultima_j = (EstadisticasPartidoJugador.objects
                .filter(partido__jornada__temporada=temporada)
                .order_by('-partido__jornada__numero_jornada')
                .values_list('partido__jornada', flat=True)
                .first())
            if not ultima_j:
                self.stderr.write(self.style.ERROR("No hay estadísticas registradas para esta temporada"))
                return
            jornada = Jornada.objects.get(pk=ultima_j)

        self.stdout.write(f"Jornada objetivo: J{jornada.numero_jornada}")

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

        total = len(jugadores_lista)
        self.stdout.write(f"Jugadores a predecir: {total}  |  modelo: {options['modelo']}  |  workers: {options['workers']}")

        # ── Cargar módulos de predicción una sola vez ───────────────────────
        entrenamientos_path = Path(__file__).resolve().parents[3] / 'main' / 'entrenamientoModelos'
        if str(entrenamientos_path) not in sys.path:
            sys.path.insert(0, str(entrenamientos_path))

        predictores = {}
        for pos, mod_nombre, func_nombre in [
            ('Portero',        'predecir_portero',       'predecir_puntos_portero'),
            ('Defensa',        'predecir_defensa',        'predecir_puntos_defensa'),
            ('Centrocampista', 'predecir_mediocampista',  'predecir_puntos_mediocampista'),
            ('Delantero',      'predecir_delantero',      'predecir_puntos_delantero'),
        ]:
            try:
                import importlib
                mod = importlib.import_module(mod_nombre)
                predictores[pos] = getattr(mod, func_nombre)
                self.stdout.write(f"  ✓ {pos}: módulo cargado")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ✗ {pos}: no disponible ({e})"))

        if not predictores:
            self.stderr.write(self.style.ERROR("Ningún módulo de predicción disponible"))
            return

        # ── Predecir ────────────────────────────────────────────────────────
        ok = error = skip = 0
        predicciones_buffer = []  # Buffer para batch saving
        batch_size = options.get('batch', 100)

        def predecir_uno(jugador_id, posicion):
            """Wrapper que llama al predictor correcto (sin guardar)."""
            from main.models import PrediccionJugador
            pos = posicion if posicion in predictores else 'Delantero'
            func = predictores.get(pos)
            if not func:
                return 'skip', None

            # Saltar si ya existe y no --force
            if not options['force']:
                existe = PrediccionJugador.objects.filter(
                    jugador_id=jugador_id,
                    jornada=jornada,
                    modelo=options['modelo'].lower(),
                ).exists()
                if existe:
                    return 'skip', None

            try:
                resultado = func(jugador_id, jornada.numero_jornada, verbose=False)
                if not isinstance(resultado, dict) or resultado.get('error'):
                    return 'error', None

                pts = resultado.get('prediccion', resultado.get('puntos_predichos'))
                if pts is None:
                    return 'error', None

                # Devolver objeto sin guardar (lo haremos en batch después)
                from main.models import PrediccionJugador as PJ
                pred_obj = PJ(
                    jugador_id=jugador_id,
                    jornada=jornada,
                    prediccion=float(pts),
                    modelo=options['modelo'].lower()
                )
                return 'ok', pred_obj
            except Exception as exc:
                logger.debug(f"Error predicción {jugador_id}: {exc}")
                return 'error', None

        with ThreadPoolExecutor(max_workers=options['workers']) as pool:
            futures = {
                pool.submit(predecir_uno, jid, pos): jid
                for jid, pos in jugadores_lista
            }
            for i, future in enumerate(as_completed(futures), 1):
                status, pred_obj = future.result()
                if status == 'ok':
                    ok += 1
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
                if i % 20 == 0 or i == total:
                    self.stdout.write(
                        f"  {i}/{total} — ✓{ok}  ✗{error}  →{skip} omitidos  (buffer: {len(predicciones_buffer)})",
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

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"\nCompletado J{jornada.numero_jornada} | {temporada.nombre}: "
            f"{ok} guardadas  {error} errores  {skip} omitidas"
        ))
