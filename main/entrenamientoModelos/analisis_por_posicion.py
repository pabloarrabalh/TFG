"""
Análisis de MAE por posición.
Umbrales calculados desde baseline naive (MAE de predecir la media por jugador).

Posiciones: PT (Portero), DF (Defensa), MC (Mediocampista), DT (Delantero)

Criterio de clasificación (ajustado a contexto TFG / predicción deportiva):
  🟢 BUENO      = modelo iguala o supera al baseline naive
  🟡 ACEPTABLE  = modelo hasta un 10% peor que el baseline (competitivo)
  🔴 MALO       = modelo más de un 10% peor que el baseline (no aporta valor)
"""

import numpy as np
import pandas as pd
from pathlib import Path


# =============================================================================
# CONFIGURACIÓN
# =============================================================================
RANGO_TARGET = 30  # abs(-10) + 20

# En predicción deportiva, igualar al baseline ya es un resultado válido.
# BUENO     = MAE <= baseline naive        (el modelo aporta valor real)
# ACEPTABLE = MAE <= baseline naive + 10%  (modelo competitivo)
# MALO      = MAE >  baseline naive + 10%  (el modelo no mejora al naive)
PORCENTAJE_BUENO     = 1.00
PORCENTAJE_ACEPTABLE = 1.10

CARPETAS = {
    'PT': 'portero',
    'DF': 'defensa',
    'MC': 'mediocampista',
    'DT': 'delantero',
}

DIR_BASE      = Path("csv/csvGenerados/entrenamiento")
CSV_JUGADORES = Path("csv/csvGenerados/players_with_features.csv")

NOMBRES_CSV_GRIDSEARCH = [
    "resultados_gridsearch_mejorado.csv",
    "resultados_gridsearch_portero.csv",
    "resultados_gridsearch_defensa.csv",
    "resultados_gridsearch_mediocampista.csv",
    "resultados_gridsearch_delantero.csv",
]


# =============================================================================
# CARGA DE DATOS
# =============================================================================

def cargar_mae_gridsearch(posicion: str) -> np.ndarray | None:
    """Carga los MAEs del CSV de GridSearch para una posición."""
    carpeta = DIR_BASE / CARPETAS[posicion] / "csvs"
    for nombre in NOMBRES_CSV_GRIDSEARCH:
        ruta = carpeta / nombre
        if ruta.exists():
            df   = pd.read_csv(ruta)
            maes = pd.to_numeric(df.get('MAE', pd.Series([])), errors='coerce').dropna().values
            if len(maes) > 0:
                print(f"  ✅ {posicion}: {ruta.name} ({len(maes)} modelos)")
                return maes
    print(f"  ❌ {posicion}: no se encontró CSV de GridSearch")
    return None


def cargar_puntos_y_baseline(posicion: str) -> tuple[np.ndarray, float] | tuple[None, None]:
    """
    Carga los puntos reales (target_pf_next) de los jugadores para una posición
    y calcula el MAE del baseline naive: predecir siempre la media histórica
    de cada jugador.

    Este MAE es la referencia mínima que debería superar cualquier modelo ML.
    """
    if not CSV_JUGADORES.exists():
        print(f"  ❌ No se encontró {CSV_JUGADORES}")
        return None, None

    df = pd.read_csv(CSV_JUGADORES)

    cols = {'posicion', 'player', 'target_pf_next'}
    if not cols.issubset(df.columns):
        print(f"  ❌ Columnas necesarias no encontradas: {cols - set(df.columns)}")
        return None, None

    df_pos = df[df['posicion'] == posicion].copy()
    df_pos['target_pf_next'] = pd.to_numeric(df_pos['target_pf_next'], errors='coerce')
    df_pos = df_pos.dropna(subset=['player', 'target_pf_next'])
    df_pos = df_pos[df_pos['target_pf_next'] <= 30]  # filtrar outliers extremos

    if len(df_pos) == 0:
        print(f"  ❌ Sin datos para posición {posicion}")
        return None, None

    puntos = df_pos['target_pf_next'].values

    # Baseline naive: para cada partido, predecir la media histórica del jugador
    media_por_jugador = df_pos.groupby('player')['target_pf_next'].transform('mean')
    mae_baseline = float((df_pos['target_pf_next'] - media_por_jugador).abs().mean())

    print(f"  📦 {posicion}: {len(puntos)} partidos | "
          f"μ={np.mean(puntos):.2f} σ={np.std(puntos):.2f} | "
          f"baseline naive MAE={mae_baseline:.4f}")

    return puntos, mae_baseline


# =============================================================================
# UMBRALES Y CLASIFICACIÓN
# =============================================================================

def calcular_umbrales(mae_baseline: float | None, posicion: str) -> dict:
    """
    Umbrales derivados del baseline naive.
    Fallback a porcentaje del rango del target si no hay baseline.
    """
    if mae_baseline is not None:
        return {
            'bueno':      mae_baseline * PORCENTAJE_BUENO,
            'aceptable':  mae_baseline * PORCENTAJE_ACEPTABLE,
            'baseline':   mae_baseline,
            'origen':     f"Baseline naive (MAE={mae_baseline:.4f})",
        }

    fallback = {
        'PT': (0.13, 0.22), 'DF': (0.14, 0.23),
        'MC': (0.15, 0.25), 'DT': (0.15, 0.25),
    }
    pb, pa = fallback[posicion]
    return {
        'bueno':     RANGO_TARGET * pb,
        'aceptable': RANGO_TARGET * pa,
        'baseline':  None,
        'origen':    f"Fallback rango target ({RANGO_TARGET} pts)",
    }


def clasificar(mae: float, umbrales: dict) -> str:
    if mae <= umbrales['bueno']:
        return "🟢 BUENO"
    if mae <= umbrales['aceptable']:
        return "🟡 ACEPTABLE"
    return "🔴 MALO"


# =============================================================================
# ANÁLISIS
# =============================================================================

def analizar_posicion(posicion: str, maes: np.ndarray,
                      puntos: np.ndarray, umbrales: dict) -> dict:
    # IQR solo si hay suficientes modelos evaluados
    if len(maes) >= 10:
        q1, q3 = np.percentile(maes, [25, 75])
        iqr    = q3 - q1
        maes   = maes[(maes >= q1 - 1.5 * iqr) & (maes <= q3 + 1.5 * iqr)]

    mae_medio = float(np.mean(maes))

    mejora_str = "N/A"
    if umbrales['baseline'] is not None and umbrales['baseline'] > 0:
        mejora     = (umbrales['baseline'] - mae_medio) / umbrales['baseline'] * 100
        mejora_str = f"{mejora:+.1f}%"

    return {
        'posicion':         posicion,
        'mae':              mae_medio,
        'n_modelos':        len(maes),
        'clasificacion':    clasificar(mae_medio, umbrales),
        'umbral_bueno':     umbrales['bueno'],
        'umbral_aceptable': umbrales['aceptable'],
        'baseline':         umbrales['baseline'],
        'mejora':           mejora_str,
        'origen_umbral':    umbrales['origen'],
        'puntos_mean':      float(np.mean(puntos)),
        'puntos_std':       float(np.std(puntos)),
        'puntos_median':    float(np.median(puntos)),
        'puntos_min':       float(np.min(puntos)),
        'puntos_max':       float(np.max(puntos)),
        'n_puntos':         len(puntos),
    }


# =============================================================================
# SALIDA
# =============================================================================

def imprimir_resultado(r: dict) -> None:
    nombres      = {'PT': 'Portero', 'DF': 'Defensa', 'MC': 'Mediocampista', 'DT': 'Delantero'}
    nombre       = nombres.get(r['posicion'], r['posicion'])
    baseline_str = f"{r['baseline']:.4f}" if r['baseline'] is not None else "N/A"

    print(f"""
┌──────────────────────────────────────────────────────────┐
│ {nombre:<56} │
├──────────────────────────────────────────────────────────┤
│ MAE modelos   : {r['mae']:.4f}  →  {r['clasificacion']:<26} │
│ Mejora naive  : {r['mejora']:<42} │
│ Modelos eval. : {r['n_modelos']:<42} │
├──────────────────────────────────────────────────────────┤
│ DISTRIBUCIÓN PUNTOS REALES ({r['n_puntos']} partidos)              │
│ Media   : {r['puntos_mean']:>6.2f}  │  Std    : {r['puntos_std']:>6.2f}              │
│ Mediana : {r['puntos_median']:>6.2f}  │  Rango  : [{r['puntos_min']:.1f}, {r['puntos_max']:.1f}]          │
├──────────────────────────────────────────────────────────┤
│ UMBRALES — {r['origen_umbral'][:45]:<45} │
│ 🟢 BUENO      MAE ≤ {r['umbral_bueno']:.4f}  (≤ baseline naive)              │
│ 🟡 ACEPTABLE  MAE ≤ {r['umbral_aceptable']:.4f}  (≤ baseline + 10%)            │
│ 🔴 MALO       MAE > {r['umbral_aceptable']:.4f}  (peor que naive + 10%)        │
│ 📊 Baseline naive MAE : {baseline_str:<32} │
└──────────────────────────────────────────────────────────┘""")


def generar_reporte(resultados: list[dict]) -> str:
    lineas = [
        "=" * 65,
        "ANÁLISIS DE RENDIMIENTO POR POSICIÓN",
        "Criterio: BUENO = supera baseline naive | ACEPTABLE = hasta 10% peor",
        "=" * 65,
    ]

    for r in sorted(resultados, key=lambda x: x['mae']):
        nombres      = {'PT': 'Portero', 'DF': 'Defensa', 'MC': 'Mediocampista', 'DT': 'Delantero'}
        baseline_str = f"{r['baseline']:.4f}" if r['baseline'] else "fallback"
        lineas.append(
            f"{nombres.get(r['posicion'], r['posicion']):<15} "
            f"MAE={r['mae']:.4f}  mejora={r['mejora']:<8}  "
            f"{r['clasificacion']:<20}  baseline={baseline_str}"
        )

    maes = [r['mae'] for r in resultados]
    lineas += [
        "-" * 65,
        f"MAE global promedio : {np.mean(maes):.4f}",
        f"MAE mín / máx       : {min(maes):.4f} / {max(maes):.4f}",
        "=" * 65,
    ]

    sin_baseline = [r['posicion'] for r in resultados if r['baseline'] is None]
    if sin_baseline:
        lineas.append(f"⚠️  Usando fallback en: {sin_baseline} (baseline no disponible)")

    return "\n".join(lineas)


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("ANÁLISIS DE POSICIONES — UMBRALES DESDE BASELINE NAIVE")
    print("=" * 65)

    resultados = []

    for pos in ['PT', 'DF', 'MC', 'DT']:
        print(f"\n[{pos}]")
        maes = cargar_mae_gridsearch(pos)
        if maes is None:
            continue

        puntos, mae_baseline = cargar_puntos_y_baseline(pos)
        if puntos is None:
            continue

        umbrales  = calcular_umbrales(mae_baseline, pos)
        resultado = analizar_posicion(pos, maes, puntos, umbrales)
        imprimir_resultado(resultado)
        resultados.append(resultado)

    if not resultados:
        print("\n[!] No se encontró ningún CSV. Revisa CARPETAS y DIR_BASE.")
    else:
        reporte = generar_reporte(resultados)
        print("\n" + reporte)

        ruta_out = DIR_BASE / "analisis_posiciones_reporte.txt"
        ruta_out.write_text(reporte, encoding='utf-8')
        print(f"\n[*] Reporte guardado en: {ruta_out}")
