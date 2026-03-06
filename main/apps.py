import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        """Se ejecuta al iniciar Django"""
        import os
        import threading

        # Importar signals para autoindexacion
        try:
            import main.signals  # noqa: F401
        except ImportError:
            pass

        # Pre-importar predecir para que el auto-reloader lo rastree desde el arranque.
        # Sin esto, la primera peticion que lo importa hace que el reloader lo vea como
        # "modulo nuevo recien modificado" y reinicia el servidor a mitad de request.
        if 'migrate' not in os.sys.argv and 'makemigrations' not in os.sys.argv:
            try:
                import sys
                from pathlib import Path
                _p = Path(__file__).parent / 'entrenamientoModelos'
                if str(_p) not in sys.path:
                    sys.path.insert(0, str(_p))
                import importlib
                importlib.import_module('predecir')
                logger.info('predecir module pre-loaded OK')
            except Exception as _e:
                logger.warning('Could not pre-load predecir: %s', _e)

        # Solo ejecutar si no es en migraciones
        if 'migrate' not in os.sys.argv and 'makemigrations' not in os.sys.argv:
            # Ejecutar popularDB en background (daemon=True)
            # Con PostgreSQL no hay problemas de locks
            init_thread = threading.Thread(target=self._initialize_data, daemon=True)
            init_thread.start()

    def _initialize_data(self):
        """Inicializa datos en background. Solo ejecuta popularDB si la BD está vacía."""
        import time
        time.sleep(1)

        try:
            from main.models import Partido, EstadisticasPartidoJugador

            # ── Comprobar si la BD ya tiene datos ──
            partidos_count = Partido.objects.count()
            stats_count = EstadisticasPartidoJugador.objects.count()
            bd_completa = partidos_count > 100 and stats_count > 1000

            if bd_completa:
                logger.info("✓ BD ya tiene datos (%d partidos, %d stats) — omitiendo popularDB", partidos_count, stats_count)
            else:
                logger.info("🔄 BD vacía o incompleta — ejecutando popularDB...")
                try:
                    # Desconectar la señal AutoPredicción para evitar miles de hilos durante la carga masiva
                    from django.db.models.signals import post_save
                    from main import signals as main_signals
                    signal_desconectado = False
                    if hasattr(main_signals, 'auto_generar_prediccion'):
                        post_save.disconnect(main_signals.auto_generar_prediccion, sender=EstadisticasPartidoJugador)
                        signal_desconectado = True

                    from main.scrapping.popularDB import main as populardb_main
                    populardb_main()
                    logger.info("✓ popularDB completado")
                except Exception as e:
                    logger.error("❌ Error en popularDB: %s", e)
                finally:
                    # Reconectar señal
                    if signal_desconectado:
                        try:
                            post_save.connect(main_signals.auto_generar_prediccion, sender=EstadisticasPartidoJugador)
                        except Exception:
                            pass

            # ── Roles: solo cargar si faltan ──
            total = EstadisticasPartidoJugador.objects.count()
            sin_roles = EstadisticasPartidoJugador.objects.filter(roles=[]).count()
            if total > 0 and sin_roles / total > 0.5:
                from main.scrapping.popularDB import fase_2_cargar_roles
                logger.info("🔄 Cargando roles faltantes...")
                fase_2_cargar_roles()
                logger.info("✓ Roles cargados")

            # ── OpenSearch: OBLIGATORIO ──
            try:
                from main.opensearch_docs import reindexar_todo, OPENSEARCH_AVAILABLE
                if not OPENSEARCH_AVAILABLE:
                    logger.error("❌ CRÍTICO: OpenSearch NO está disponible")
                    logger.error("   Asegurate de que:")
                    logger.error("   1. OpenSearch está corriendo en localhost:9200")
                    logger.error("   2. Tienes los permisos correctos")
                    logger.error("   3. Has reiniciado el servidor")
                    raise RuntimeError("OpenSearch es obligatorio para que la búsqueda funcione")
                logger.info("🔍 Indexando documentos en OpenSearch...")
                reindexar_todo()
                logger.info("✓ OpenSearch indexado correctamente")
            except Exception as e:
                logger.error(f"❌ Error crítico en OpenSearch: {e}")
                raise

            # ── Predicciones: generar solo jornadas sin predicciones ──
            self._generar_predicciones_pendientes()

        except Exception as e:
            logger.error("Error durante inicialización: %s", e)

    @staticmethod
    def _generar_predicciones_pendientes():
        """Genera predicciones solo para jornadas de 25/26 que no tengan ninguna."""
        from main.models import Temporada, Jornada, PrediccionJugador
        from django.core.management import call_command

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
