import importlib
import logging
import os
import sys
import threading
import time
from pathlib import Path

from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_save

logger = logging.getLogger(__name__)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        """Se ejecuta al iniciar Django"""
        logger.info("[apps.ready()] Inicializando MainConfig...")
        
        # Detectar si es un script de data loading (no cargar signals costosos)
        is_data_script = any(
            'popularDB' in arg or 'manage.py' not in sys.argv[0]
            for arg in sys.argv
        )
        
        if not is_data_script:
            # Importar signals para autoindexacion SOLO si no es un script de datos
            logger.info("[apps.ready()] Cargando signals...")
            try:
                import main.signals  # noqa: F401
                logger.info("[apps.ready()] Signals cargadas")
            except Exception as e:
                logger.warning('[apps.ready()] Error cargando signals: %s', e)
        else:
            logger.info("[apps.ready()] Script de datos detectado, signals omitidos")

        # Pre-importar predecir para que el auto-reloader lo rastree desde el arranque.
        # Sin esto, la primera peticion que lo importa hace que el reloader lo vea como
        # "modulo nuevo recien modificado" y reinicia el servidor a mitad de request.
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            try:
                _p = Path(__file__).parent / 'entrenamientoModelos'
                if str(_p) not in sys.path:
                    sys.path.insert(0, str(_p))
                logger.info("[apps.ready()] Pre-importando predecir...")
                importlib.import_module('predecir')
                logger.info("[apps.ready()] Predecir pre-importado")
            except Exception as _e:
                logger.warning('Could not pre-load predecir: %s', _e)

        # Solo ejecutar durante runserver (desarrollo local).
        # En Docker, entrypoint.sh llama a los comandos explícitamente.
        if 'runserver' in sys.argv:
            logger.info("[apps.ready()] runserver detectado, iniciando thread de datos...")
            init_thread = threading.Thread(target=self._initialize_data, daemon=True)
            init_thread.start()
        
        logger.info("[apps.ready()] Inicialización completada")

    @staticmethod
    def _mostrar_banner():
        """Muestra el banner ASCII de LigaMaster y el puerto."""
        # Leer banner desde archivo externo
        try:
            banner_path = Path(__file__).parent / 'banner.txt'
            with open(banner_path, 'r', encoding='utf-8') as f:
                banner = f.read()
        except Exception as e:
            logger.warning(f'Could not read banner.txt: {e}')
            banner = ''
        
        print(banner)
        
        # Obtener puerto desde sys.argv o usar default
        puerto = 8000
        for i, arg in enumerate(sys.argv):
            if arg == 'runserver' and i + 1 < len(sys.argv):
                try:
                    puerto = int(sys.argv[i + 1].split(':')[-1])
                except (ValueError, IndexError):
                    pass
        
        print(f"\n  Backend corriendo en http://localhost:{puerto}\n")
        print("  " + "="*70)
        print()

    def _initialize_data(self):
        """Inicializa datos en background con mensajes de progreso."""
        time.sleep(1)

        paso = 0
        total_pasos = 5

        try:
            from main.models import Partido, EstadisticasPartidoJugador
            from main import signals as main_signals
            from main.scrapping.popularDB import main as populardb_main, fase_2_cargar_roles
            from main.meilisearch_docs import reindexar_todo, MEILISEARCH_AVAILABLE

            # ── Paso 1: Comprobar si la BD ya tiene datos ──
            paso = 1
            logger.info(f"Paso {paso}/{total_pasos} - Comprobando base de datos...")
            partidos_count = Partido.objects.count()
            stats_count = EstadisticasPartidoJugador.objects.count()
            bd_completa = partidos_count > 100 and stats_count > 1000
            if bd_completa:
                logger.info(f"[OK] Paso {paso}/{total_pasos} - BD completa ({partidos_count} partidos, {stats_count} stats)")
            else:
                logger.info(f"[WARN] Paso {paso}/{total_pasos} - BD incompleta o vacía")

            # ── Paso 2: Cargar datos iniciales si BD vacía ──
            paso = 2
            if not bd_completa:
                logger.info(f"Paso {paso}/{total_pasos} - Cargando datos iniciales...")
                try:
                    # Desconectar la señal AutoPredicción para evitar miles de hilos
                    signal_desconectado = False
                    if hasattr(main_signals, 'auto_generar_prediccion'):
                        post_save.disconnect(main_signals.auto_generar_prediccion, sender=EstadisticasPartidoJugador)
                        signal_desconectado = True

                    populardb_main()
                    logger.info(f"[OK] Paso {paso}/{total_pasos} - Datos iniciales cargados correctamente")
                except Exception as e:
                    logger.error(f"[ERROR] Paso {paso}/{total_pasos} - Error cargando datos: {e}")
                finally:
                    # Reconectar señal
                    if signal_desconectado:
                        try:
                            post_save.connect(main_signals.auto_generar_prediccion, sender=EstadisticasPartidoJugador)
                        except Exception:
                            pass
            else:
                logger.info(f"[SKIP] Paso {paso}/{total_pasos} - Saltando (BD ya completa)")

            # ── Paso 3: Cargar roles si faltan ──
            paso = 3
            logger.info(f"Paso {paso}/{total_pasos} - Verificando roles...")
            total = EstadisticasPartidoJugador.objects.count()
            sin_roles = EstadisticasPartidoJugador.objects.filter(roles=[]).count()
            if total > 0 and sin_roles / total > 0.5:
                logger.info(f"Paso {paso}/{total_pasos} - Cargando roles faltantes ({sin_roles}/{total})...")
                try:
                    fase_2_cargar_roles()
                    logger.info(f"[OK] Paso {paso}/{total_pasos} - Roles cargados correctamente")
                except Exception as e:
                    logger.error(f"[ERROR] Paso {paso}/{total_pasos} - Error cargando roles: {e}")
            else:
                logger.info(f"[OK] Paso {paso}/{total_pasos} - Roles OK ({sin_roles}/{total} sin roles)")

            # ── Paso 4: Indexar en Meilisearch ──
            paso = 4
            logger.info(f"Paso {paso}/{total_pasos} - Indexando en Meilisearch...")
            try:
                if not MEILISEARCH_AVAILABLE:
                    raise RuntimeError("Meilisearch no disponible")
                reindexar_todo()
                logger.info(f"[OK] Paso {paso}/{total_pasos} - Meilisearch indexado correctamente")
            except Exception as e:
                logger.warning(f"[WARN] Paso {paso}/{total_pasos} - Meilisearch desactivado: {e}")

            # ── Paso 5: Generar predicciones para jornadas pendientes ──
            paso = 5
            logger.info(f"Paso {paso}/{total_pasos} - Generando predicciones pendientes...")
            try:
                self._generar_predicciones_pendientes()
                logger.info(f"[OK] Paso {paso}/{total_pasos} - Predicciones generadas/verificadas")
            except Exception as e:
                logger.error(f"[ERROR] Paso {paso}/{total_pasos} - Error generando predicciones: {e}")

            logger.info("[SUCCESS] Inicializacion completada correctamente")
            
            # Mostrar banner después de inicialización completada
            if 'runserver' in sys.argv:
                print()
                self._mostrar_banner()

        except Exception as e:
            logger.error(f"[CRITICAL] Error en Paso {paso}/{total_pasos}: {e}")



    @staticmethod
    def _generar_predicciones_pendientes():
        """Genera predicciones solo para jornadas de 25/26 que no tengan ninguna."""
        from main.models import Temporada, Jornada, PrediccionJugador

        temporada = Temporada.objects.filter(nombre='25_26').first()
        if not temporada:
            return

        jornadas_sin = (
            Jornada.objects.filter(temporada=temporada)
            .exclude(predicciones_jugadores__isnull=False)
            .order_by('numero_jornada')
        )

        # Optimización: si ya hay predicciones para todas, salir rápido
        if not jornadas_sin.exists():
            return

        total = jornadas_sin.count()
        logger.info(f"Generando predicciones para {total} jornadas...")

        for jornada in jornadas_sin:
            if PrediccionJugador.objects.filter(jornada=jornada).exists():
                continue
            try:
                call_command(
                    'generar_predicciones',
                    temporada='25_26',
                    jornada=jornada.numero_jornada,
                    workers=4,
                    verbosity=0,
                )
            except Exception:
                pass
        
        logger.info("Predicciones cargadas")
