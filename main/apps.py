from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'
    
    def ready(self):
        """Se ejecuta al iniciar Django"""
        import os
        import threading
        from django.core.management import call_command
        
        # Importar signals para autoindexación
        try:
            import main.signals
        except ImportError:
            pass
        
        # Solo ejecutar si no es en migraciones
        if 'migrate' not in os.sys.argv and 'makemigrations' not in os.sys.argv:
            # Ejecutar en background thread para no bloquear el servidor
            init_thread = threading.Thread(target=self._initialize_data, daemon=True)
            init_thread.start()
    
    def _initialize_data(self):
        """Inicializa datos en background"""
        import time
        time.sleep(2)  # Esperar a que Django termine de inicializar
        
        try:
            print("\n" + "="*60)
            print("Inicializando datos en background...")
            print("="*60)
            
            # Ejecutar populateDB
            print("\nCargando roles...")
            from main.scrapping.popularDB import fase_2_cargar_roles
            fase_2_cargar_roles()
            print("Roles cargados")
            
            # Indexar en Elasticsearch
            print("\nIndexando en Elasticsearch...")
            try:
                from main.elasticsearch_docs import reindexar_todo, ELASTICSEARCH_AVAILABLE
                if ELASTICSEARCH_AVAILABLE:
                    reindexar_todo()
                    print("Elasticsearch indexado correctamente")
                else:
                    print("Elasticsearch no disponible (busqueda deshabilitada)")
            except Exception as e:
                print(f"Error indexando Elasticsearch: {str(e)}")
            
            print("\n" + "="*60)
            print("Inicialización completada")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"Error durante inicialización: {e}")
            import traceback
            traceback.print_exc()


