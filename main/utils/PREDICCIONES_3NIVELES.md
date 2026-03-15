# Sistema de Predicciones en 3 Niveles

## Descripción
Las predicciones se generan con una estrategia de 3 niveles para optimizar velocidad y utilización de recursos:

### 1. **INIT** (Al arrancar contenedor)
- **Jugadores**: Solo aquellos con **60+ minutos en los primeros 10 partidos de la temporada 25/26**
- **Tiempo**: ~4-5 minutos
- **Cómo funciona**: En `entrypoint.sh` se ejecuta con `--init-active-only`
- **Beneficio**: Rápido, carga lo esencial
- **Comando**: 
  ```bash
  python manage.py generar_predicciones --all-jornadas --init-active-only --workers 32 --batch 300
  ```

### 2. **BACKGROUND** (En segundo plano)
- **Jugadores**: TODOS los demás (que no se generaron en INIT)
- **Cómo funciona**: 
  - El INIT crea `PedidoPrediccion` para todos los jugadores-jornada
  - Un daemon en background ejecuta `generar_predicciones_background` en **LOOP CONTINUO**
  - Genera en lotes de 50 sin parar hasta completar TODAS
  - Se ejecuta en paralelo con Daphne (no bloquea)
- **Comando**:
  ```bash
  # Corre de forma continua hasta terminar (default)
  python manage.py generar_predicciones_background --batch 50 --tempo 25_26
  
  # O modo single para solo 1 lote (testing)
  python manage.py generar_predicciones_background --single --batch 50 --tempo 25_26
  ```
- **Ventaja**: 
  - **Todas las predicciones se generan automáticamente** sin cron job
  - No demora inicio (corre en background en paralelo)
  - App siempre responde
  - Se termina naturalmente cuando no hay más predicciones pendientes

### 3. **ON-DEMAND** (Cuando se accede)
- **Jugadores**: Cualquiera que se busque y NO tenga predicción aún
- **Cuándo**: 
  - Usuario ve perfil del jugador
  - Usuario agrega jugador a su plantilla
  - Búsqueda/filtrado en la app
- **Cómo funciona**:
  - Decorator `@ensure_predictions` en las vistas
  - Marca la predicción como pendiente (background)
  - Si el usuario vuelve en pocos segundos, tiene la predicción
- **Código**:
  ```python
  from main.utils.prediction_decorators import ensure_predictions
  
  @ensure_predictions
  def player_detail(request, jugador_id):
      predicciones = cargar_predicciones_contexto(jugador_id)
      ...
  ```

## Flujo Completo al Arrancar

```
STARTUP
  ├─ 1. [INIT-ACTIVE] 4-5 min (60+ min en primeros 10 juegos)
  │   └─ Crea PedidoPrediccion para TODOS jugadores-jornada
  │
  ├─ 2. [BACKGROUND DAEMON - LOOP CONTINUO] 🔄 En paralelo
  │   └─ generar_predicciones_background corre de forma continua
  │   └─ Genera lotes de 50 predicciones 'pending'
  │   └─ Continúa hasta que no hay más pendientes
  │   └─ Se auto-termina cuando completa
  │
  ├─ 3. [ON-DEMAND] Cuando se accede a jugador
  │   └─ Si falta predicción, marca como pending → background la genera pronto
  │
  └─ ✓ APP READY ~3-5 min + Daphne activo
     Predicciones mejorando en background
```

## Modelos Implicados

### `PedidoPrediccion`
```python
jugador → ForeignKey(Jugador)
jornada → ForeignKey(Jornada)
temporada → ForeignKey(Temporada)
estado → 'pending' | 'generated' | 'failed'
creado_en → timestamp
actualizacion_en → timestamp
intentos → contador (máximo 3)
motivo_error → para debugging
```

### `PrediccionJugador` (existente)
- Almacena la predicción real
- Unique: (jugador, jornada, modelo)

## Cache
- Predicciones se cachean 1 hora en Redis/Memcached
- Clave: `pred_{jugador_id}_{jornada_id}`
- Se limpia automáticamente al generar nueva

## Integración en Vistas

### Vista de Perfil de Jugador
```python
from main.utils.prediction_decorators import ensure_predictions, cargar_predicciones_contexto

@ensure_predictions  # ← Decorator
def player_detail(request, jugador_id):
    jugador = get_object_or_404(Jugador, pk=jugador_id)
    predicciones = cargar_predicciones_contexto(jugador_id)  # ← Cargar predics
    
    context = {
        'jugador': jugador,
        'predicciones': predicciones,  # {1: 45.2, 2: 38.5, ...}
    }
    return render(request, 'jugador_detail.html', context)
```

### Vista de Agregar a Plantilla
```python
from main.utils.prediction_decorators import ensure_predictions_for_plantilla

@ensure_predictions_for_plantilla  # ← Decorator alternativo
def agregar_a_plantilla(request):
    jugador_id = request.POST.get('jugador_id')
    # ... crear PlantillaJugador ...
    return redirect(...)
```

## Monitoreo de Predicciones Pendientes

```python
from main.models import PedidoPrediccion

# Cuántas predicciones falta generar
pendientes = PedidoPrediccion.objects.filter(estado='pending').count()
print(f"Pendientes: {pendientes}")

# Cuántas se han generado en total
generadas = PedidoPrediccion.objects.filter(estado='generated').count()
print(f"Generadas: {generadas}")

# Cuántas erraron (> 3 intentos)
fallidas = PedidoPrediccion.objects.filter(estado='failed').count()
print(f"Fallidas: {fallidas}")

# Histórico de generaciones en última hora
from django.utils import timezone
from datetime import timedelta

recientes = PedidoPrediccion.objects.filter(
    estado='generated',
    actualizado_en__gte=timezone.now() - timedelta(hours=1)
).count()
print(f"Generadas en última hora: {recientes}")

# Ver progreso %
total = PedidoPrediccion.objects.count()
porcentaje = (generadas / total * 100) if total > 0 else 0
print(f"Progreso: {generadas}/{total} ({porcentaje:.1f}%)")
```

### Ver Daemon en Logs
```bash
# Ver logs del background en tiempo real
docker logs -f tfg-backend-1 | grep "\[BACKGROUND\]"

# O si corre local
tail -f app.log | grep "\[BACKGROUND\]"
```

## Performance

| Nivel | Tiempo | Jugadores | Cómo |
|-------|--------|-----------|------|
| **INIT** | 4-5 min | ~100-150 (activos) | Arranque |
| **BACKGROUND** (por lote) | 1-2 min | ~50 | Loop continuo |
| **ON-DEMAND** | <500ms | 1 al momento | Acceso usuario |

**Resultado**: App lista en 5 min + todas las predicciones generadas en background (30-60 min para 5000+)

## Debugging

```bash
# Ver predicciones pendientes
python manage.py shell
>>> from main.models import PedidoPrediccion
>>> PedidoPrediccion.objects.filter(estado='pending').count()
>>> PedidoPrediccion.objects.filter(estado='failed').count()

# Ejecutar background manualmente
python manage.py generar_predicciones_background --batch 50 --verbosity 2

# Ver logs
tail -f /var/log/predicciones.log
```
