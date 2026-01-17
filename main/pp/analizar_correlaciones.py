import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

warnings.filterwarnings("ignore")

# ===========================
# CONFIGURACIÓN
# ===========================
DIRECTORIO_SALIDA = Path("csv/csvGenerados/analisis_correlaciones")
DIRECTORIO_SALIDA.mkdir(parents=True, exist_ok=True)

RUTAS_BUSQUEDA = [
    Path.cwd(),
    Path.cwd() / "main" / "pp",
    Path.cwd() / "main",
    Path.cwd() / "data" / "temporada_25_26",
    Path.cwd() / "data",
    Path.cwd().parent,
    Path.cwd().parent / "main" / "pp",
]

ARCHIVO_CSV = "csv/csvGenerados/players_with_features_MINIMO.csv"


def buscar_csv(rutas, nombre_csv):
    """Busca archivo CSV en rutas configuradas."""
    for ruta in rutas:
        ruta_completa = ruta / nombre_csv
        if ruta_completa.exists():
            return str(ruta_completa)
    return None


# ===========================
# 1. CARGAR DATOS
# ===========================
print("="*80)
print("📊 ANÁLISIS DE CORRELACIONES - INVESTIGACIÓN R² BAJO")
print("="*80 + "\n")

ruta_csv = buscar_csv(RUTAS_BUSQUEDA, ARCHIVO_CSV)
if not ruta_csv:
    raise FileNotFoundError(f"No se encontró: {ARCHIVO_CSV}")

print(f"📂 Cargando: {ruta_csv}")
df = pd.read_csv(ruta_csv)
df_porteros = df[df["posicion"] == "PT"].copy()

print(f"✅ {df_porteros.shape[0]} porteros, {df_porteros.shape[1]} columnas\n")


# ===========================
# 2. ANÁLISIS DEL TARGET
# ===========================
print("="*80)
print("1️⃣  ANÁLISIS DEL TARGET")
print("="*80 + "\n")

# Identificar columna target
target_cols = ["target_pf_next", "puntosFantasy", "puntos_fantasy"]
target_col = None
for col in target_cols:
    if col in df_porteros.columns:
        target_col = col
        break

if not target_col:
    print(f"❌ No se encontró columna target. Disponibles: {df_porteros.columns.tolist()}")
    target_col = df_porteros.columns[-1]
    print(f"Usando última columna por defecto: {target_col}\n")
else:
    print(f"✅ Columna target identificada: '{target_col}'\n")

# Estadísticas del target
print("ESTADÍSTICAS DEL TARGET:")
print("-" * 80)
print(f"Mean:       {df_porteros[target_col].mean():.4f} puntos")
print(f"Std:        {df_porteros[target_col].std():.4f} puntos")
print(f"Min:        {df_porteros[target_col].min():.4f} puntos")
print(f"Max:        {df_porteros[target_col].max():.4f} puntos")
print(f"Median:     {df_porteros[target_col].median():.4f} puntos")
print(f"Skewness:   {df_porteros[target_col].skew():.4f}")
print(f"Kurtosis:   {df_porteros[target_col].kurtosis():.4f}")
print(f"Nulos:      {df_porteros[target_col].isnull().sum()} ({df_porteros[target_col].isnull().sum()/len(df_porteros)*100:.2f}%)")

# Percentiles
print(f"\nPERCENTILES:")
for p in [10, 25, 50, 75, 90, 95]:
    val = np.percentile(df_porteros[target_col].dropna(), p)
    print(f"  P{p:2d}: {val:.2f}")

print()


# ===========================
# 3. CORRELACIÓN CON TODAS LAS FEATURES
# ===========================
print("="*80)
print("2️⃣  CORRELACIÓN FEATURES vs TARGET")
print("="*80 + "\n")

# Seleccionar solo columnas numéricas
numeric_cols = df_porteros.select_dtypes(include=[np.number]).columns.tolist()

# Excluir columna target si está en las features
if target_col in numeric_cols:
    numeric_cols.remove(target_col)

print(f"📊 Evaluando {len(numeric_cols)} features numéricas\n")

# Calcular correlaciones
correlaciones = []
for col in numeric_cols:
    # Eliminar NaNs para el cálculo
    mask = df_porteros[[col, target_col]].notna().all(axis=1)
    if mask.sum() > 0:
        corr = df_porteros.loc[mask, col].corr(df_porteros.loc[mask, target_col])
        correlaciones.append({
            "Feature": col,
            "Correlación": corr,
            "Abs_Corr": abs(corr),
            "N_Valid": mask.sum()
        })

df_corr = pd.DataFrame(correlaciones).sort_values("Abs_Corr", ascending=False)

# ===========================
# 4. ANÁLISIS DE CORRELACIÓN
# ===========================
print("TOP 25 FEATURES - CORRELACIÓN CON TARGET:")
print("-" * 80)
print(f"{'#':<3} {'Feature':<45} {'Correlación':<12} {'Abs':<8} {'N':<6}")
print("-" * 80)

for idx, (i, row) in enumerate(df_corr.head(25).iterrows(), 1):
    color_indicator = ""
    if abs(row["Correlación"]) > 0.3:
        color_indicator = "🟢"
    elif abs(row["Correlación"]) > 0.15:
        color_indicator = "🟡"
    else:
        color_indicator = "🔴"
    
    print(f"{idx:<3} {row['Feature']:<45} {row['Correlación']:+.6f}    "
          f"{row['Abs_Corr']:>7.6f} {row['N_Valid']:>6d} {color_indicator}")

print("\n")

# ===========================
# 5. DIAGNÓSTICO
# ===========================
print("="*80)
print("3️⃣  DIAGNÓSTICO - ¿POR QUÉ R² ES BAJO?")
print("="*80 + "\n")

max_corr = df_corr["Abs_Corr"].max()
max_corr_feature = df_corr[df_corr["Abs_Corr"] == max_corr]["Feature"].values[0]
max_corr_value = df_corr[df_corr["Abs_Corr"] == max_corr]["Correlación"].values[0]

# Correlación máxima teórica
r2_max_theoretical = max_corr ** 2

print(f"MÉTRICA CLAVE:")
print("-" * 80)
print(f"Máxima correlación encontrada:")
print(f"  Feature: {max_corr_feature}")
print(f"  Correlación: {max_corr_value:+.6f}")
print(f"  R² máximo teórico (simple): {r2_max_theoretical:.6f}")
print(f"  Tu R² actual (modelo): -0.0165")
print(f"\n⚠️  BRECHA: {r2_max_theoretical - (-0.0165):.6f}")
print(f"   Espacio de mejora: {r2_max_theoretical*100:.2f}%")

print(f"\n")

# Clasificación
print("CLASIFICACIÓN:")
print("-" * 80)
if max_corr < 0.25:
    print(f"🔴 DATASET EXTREMADAMENTE RUIDOSO")
    print(f"   max_corr = {max_corr:.4f} < 0.25")
    print(f"   → Features capturan <6% de varianza individual")
    print(f"   → Considera agregar variables completamente nuevas")
elif max_corr < 0.4:
    print(f"🟡 DATASET MUY RUIDOSO")
    print(f"   max_corr = {max_corr:.4f} < 0.4")
    print(f"   → Componente estocástica alta (fantasy football)")
    print(f"   → Espacio mejora: agregar features contextuales")
elif max_corr < 0.5:
    print(f"🟠 DATASET RUIDOSO (NORMAL)")
    print(f"   max_corr = {max_corr:.4f} < 0.5")
    print(f"   → Típico en deportes. Considera ensemble o features no-lineales")
elif max_corr < 0.6:
    print(f"🟡 DATASET MODERADAMENTE RUIDOSO")
    print(f"   max_corr = {max_corr:.4f}")
    print(f"   → Buena correlación. Hay features sin explotar")
elif max_corr < 0.7:
    print(f"🟢 DATASET LIMPIO")
    print(f"   max_corr = {max_corr:.4f}")
    print(f"   → Features predicen bien. Posible colinealidad")
else:
    print(f"🟢 DATASET MUY LIMPIO")
    print(f"   max_corr = {max_corr:.4f}")
    print(f"   → Excelente predictibilidad")

print("\n")


# ===========================
# 6. FEATURES CATEGORIZADAS
# ===========================
print("="*80)
print("4️⃣  FEATURES CATEGORIZADAS POR FUERZA DE CORRELACIÓN")
print("="*80 + "\n")

print("FUERTE (|corr| >= 0.3):")
print("-" * 80)
strong = df_corr[df_corr["Abs_Corr"] >= 0.3]
if len(strong) > 0:
    for idx, (i, row) in enumerate(strong.iterrows(), 1):
        print(f"  {idx}. {row['Feature']:<45} {row['Correlación']:+.6f}")
else:
    print("  (Ninguna)")

print(f"\nMODERADA (0.15 <= |corr| < 0.3):")
print("-" * 80)
moderate = df_corr[(df_corr["Abs_Corr"] >= 0.15) & (df_corr["Abs_Corr"] < 0.3)]
if len(moderate) > 0:
    print(f"  Total: {len(moderate)} features")
    for idx, (i, row) in enumerate(moderate.head(10).iterrows(), 1):
        print(f"  {idx}. {row['Feature']:<45} {row['Correlación']:+.6f}")
    if len(moderate) > 10:
        print(f"  ... y {len(moderate)-10} más")
else:
    print("  (Ninguna)")

print(f"\nDÉBIL (|corr| < 0.15):")
print("-" * 80)
weak = df_corr[df_corr["Abs_Corr"] < 0.15]
print(f"  Total: {len(weak)} features (probablemente ruido)")
print(f"  Estos NO aportan predictibilidad → Pueden eliminarse")

print("\n")


# ===========================
# 7. ANÁLISIS DE VARIANCE INFLATION FACTOR (COLINEALIDAD)
# ===========================
print("="*80)
print("5️⃣  COLINEALIDAD - ¿FEATURES REDUNDANTES?")
print("="*80 + "\n")

# Seleccionar features principales del modelo
main_features = [
    "def_actions_ema", "clearance_activity_ema", "save_pct_roll5_mean",
    "rol_save_pct_posicion", "score_roles", "racha_derrotas",
    "psxg_plus_minus_roll5", "pf_lag1"
]

main_features_exist = [f for f in main_features if f in df_porteros.columns]

print(f"Analizando {len(main_features_exist)} features principales...")
print("-" * 80)

# Calcular matriz de correlación
df_main = df_porteros[main_features_exist].dropna()

if len(df_main) > 0:
    corr_matrix = df_main.corr()
    
    # Buscar correlaciones altas entre features
    print("\nCORRELACIONES ENTRE FEATURES (riesgo colinealidad si >0.7):")
    print("-" * 80)
    
    colinealidades = []
    for i in range(len(main_features_exist)):
        for j in range(i+1, len(main_features_exist)):
            corr_val = corr_matrix.iloc[i, j]
            if abs(corr_val) > 0.5:  # Threshold para reportar
                colinealidades.append({
                    "Feature1": main_features_exist[i],
                    "Feature2": main_features_exist[j],
                    "Correlación": corr_val,
                    "Abs": abs(corr_val)
                })
    
    if colinealidades:
        df_colin = pd.DataFrame(colinealidades).sort_values("Abs", ascending=False)
        for idx, (i, row) in enumerate(df_colin.iterrows(), 1):
            risk = "🔴 ALTO" if row["Abs"] > 0.7 else "🟡 MODERADO"
            print(f"  {idx}. {row['Feature1']:<35} ↔ {row['Feature2']:<35}")
            print(f"     Correlación: {row['Correlación']:+.4f} {risk}")
    else:
        print("  ✅ Sin colinealidad significativa (todas |corr| < 0.5)")
else:
    print("  ⚠️ No hay datos válidos para análisis")

print("\n")


# ===========================
# 8. RUIDO vs ERROR
# ===========================
print("="*80)
print("6️⃣  ANÁLISIS RUIDO - CONTEXTO DEL ERROR")
print("="*80 + "\n")

target_std = df_porteros[target_col].std()
mae_model = 3.321  # De entrenamiento anterior

print(f"Desviación estándar target (ruido): {target_std:.4f} puntos")
print(f"MAE del modelo: {mae_model:.4f} puntos")
print(f"Ratio MAE/Ruido: {mae_model/target_std:.4f}x")

print(f"\nINTERPRETACIÓN:")
if mae_model/target_std > 0.8:
    print(f"  🔴 Error es SIMILAR al ruido → Dataset muy ruidoso")
    print(f"     Conclusión: No hay margen significativo de mejora")
elif mae_model/target_std > 0.5:
    print(f"  🟡 Error es MODERADO vs ruido → Normal para deportes")
    print(f"     Conclusión: Hay margen de mejora (~10-15%)")
else:
    print(f"  🟢 Error es BAJO vs ruido → Buen rendimiento")
    print(f"     Conclusión: Hay margen de mejora significativo")

print("\n")


# ===========================
# 9. RECOMENDACIONES ESPECÍFICAS
# ===========================
print("="*80)
print("7️⃣  RECOMENDACIONES ESPECÍFICAS")
print("="*80 + "\n")

recomendaciones = []

# Recom 1: Ruido del dataset
if max_corr < 0.3:
    recomendaciones.append(("CRÍTICO", "Dataset muy ruidoso (max_corr < 0.3)",
        "Agregar variables completamente nuevas: clima, árbitro, lesiones, contexto rival"))
elif max_corr < 0.4:
    recomendaciones.append(("IMPORTANTE", "Dataset ruidoso (max_corr < 0.4)",
        "Agregar 4-5 variables contextuales + considerar ensemble"))
elif max_corr < 0.5:
    recomendaciones.append(("NORMAL", "Dataset típico para deportes (max_corr < 0.5)",
        "Considerar features no-lineales o ensemble model"))

# Recom 2: Features débiles
weak_count = len(df_corr[df_corr["Abs_Corr"] < 0.10])
if weak_count > 10:
    recomendaciones.append(("IMPORTANTE", f"Muchas features débiles ({weak_count} features < 0.10 corr)",
        "Eliminar features sin aporte → Reduce overfitting"))

# Recom 3: Colinealidad
if colinealidades and any(row["Abs"] > 0.7 for _, row in df_colin.iterrows()):
    recomendaciones.append(("IMPORTANTE", "Colinealidad alta detectada",
        "Usar una de cada par correlacionado O agregar regularización L1"))

# Recom 4: Target properties
if abs(df_porteros[target_col].skew()) > 1.0:
    recomendaciones.append(("INFORMACIÓN", "Target con skew alto (distribución sesgada)",
        "Considerar transformación log o Box-Cox antes de modelar"))

# Imprimir recomendaciones
for severity, title, action in recomendaciones:
    icon = {"CRÍTICO": "🔴", "IMPORTANTE": "🟡", "NORMAL": "🟠", "INFORMACIÓN": "🔵"}[severity]
    print(f"{icon} {severity}: {title}")
    print(f"   Acción: {action}\n")

if not recomendaciones:
    print("✅ Sin recomendaciones críticas. Dataset en estado normal.")

print("\n")


# ===========================
# 10. GUARDAR RESULTADOS
# ===========================
print("="*80)
print("8️⃣  GUARDAR RESULTADOS")
print("="*80 + "\n")

# CSV de correlaciones
csv_corr_path = DIRECTORIO_SALIDA / "correlaciones_all_features.csv"
df_corr.to_csv(csv_corr_path, index=False)
print(f"✅ Correlaciones guardadas: {csv_corr_path}")

# CSV de diagnóstico
df_diagnostico = pd.DataFrame([
    {"Métrica": "Máxima correlación", "Valor": f"{max_corr:.6f}"},
    {"Métrica": "Feature más correlacionada", "Valor": max_corr_feature},
    {"Métrica": "R² máximo teórico", "Valor": f"{r2_max_theoretical:.6f}"},
    {"Métrica": "Tu R² actual", "Valor": "-0.0165"},
    {"Métrica": "Espacio de mejora", "Valor": f"{r2_max_theoretical*100:.2f}%"},
    {"Métrica": "Ruido (target std)", "Valor": f"{target_std:.4f}"},
    {"Métrica": "MAE modelo", "Valor": f"{mae_model:.4f}"},
    {"Métrica": "Ratio MAE/Ruido", "Valor": f"{mae_model/target_std:.4f}x"},
    {"Métrica": "Features fuertes (|corr|>=0.3)", "Valor": str(len(strong))},
    {"Métrica": "Features débiles (|corr|<0.15)", "Valor": str(len(weak))},
])

csv_diag_path = DIRECTORIO_SALIDA / "diagnostico_summary.csv"
df_diagnostico.to_csv(csv_diag_path, index=False)
print(f"✅ Diagnóstico guardado: {csv_diag_path}")

print(f"\n✅ Directorio salida: {DIRECTORIO_SALIDA}")

print("\n")


# ===========================
# 11. GRÁFICOS
# ===========================
print("="*80)
print("9️⃣  GENERANDO GRÁFICOS")
print("="*80 + "\n")

# Gráfico 1: Top 20 correlaciones
fig, ax = plt.subplots(figsize=(12, 8))
top_20 = df_corr.head(20).sort_values("Abs_Corr")
colors = ["green" if x >= 0.3 else "orange" if x >= 0.15 else "red" for x in top_20["Abs_Corr"]]
ax.barh(range(len(top_20)), top_20["Abs_Corr"], color=colors)
ax.set_yticks(range(len(top_20)))
ax.set_yticklabels(top_20["Feature"], fontsize=9)
ax.set_xlabel("Correlación Absoluta", fontsize=11)
ax.set_title("Top 20 Features - Correlación con Target\n(Verde: |corr|>=0.3, Naranja: 0.15-0.3, Rojo: <0.15)", fontsize=12)
ax.axvline(0.3, color="green", linestyle="--", alpha=0.5, label="|corr|=0.3")
ax.axvline(0.15, color="orange", linestyle="--", alpha=0.5, label="|corr|=0.15")
ax.legend()
ax.grid(alpha=0.3, axis="x")
plt.tight_layout()
plt.savefig(DIRECTORIO_SALIDA / "01_top20_correlaciones.png", dpi=150, bbox_inches="tight")
plt.close()
print("✅ Gráfico 1: top20_correlaciones.png")

# Gráfico 2: Distribución de correlaciones
fig, ax = plt.subplots(figsize=(12, 6))
ax.hist(df_corr["Abs_Corr"], bins=50, color="skyblue", edgecolor="black", alpha=0.7)
ax.axvline(0.3, color="green", linestyle="--", linewidth=2, label="Fuerte (>=0.3)")
ax.axvline(0.15, color="orange", linestyle="--", linewidth=2, label="Moderada (>=0.15)")
ax.axvline(max_corr, color="red", linestyle="-", linewidth=3, label=f"Max={max_corr:.3f}")
ax.set_xlabel("Correlación Absoluta", fontsize=11)
ax.set_ylabel("Frecuencia", fontsize=11)
ax.set_title("Distribución de Correlaciones - Todas las Features", fontsize=12)
ax.legend(fontsize=10)
ax.grid(alpha=0.3, axis="y")
plt.tight_layout()
plt.savefig(DIRECTORIO_SALIDA / "02_distribucion_correlaciones.png", dpi=150, bbox_inches="tight")
plt.close()
print("✅ Gráfico 2: distribucion_correlaciones.png")

# Gráfico 3: Target distribution
fig, ax = plt.subplots(figsize=(12, 6))
ax.hist(df_porteros[target_col].dropna(), bins=50, color="lightblue", edgecolor="black", alpha=0.7)
ax.axvline(df_porteros[target_col].mean(), color="red", linestyle="--", linewidth=2, label=f"Mean: {df_porteros[target_col].mean():.2f}")
ax.axvline(df_porteros[target_col].median(), color="green", linestyle="--", linewidth=2, label=f"Median: {df_porteros[target_col].median():.2f}")
ax.set_xlabel("Puntos Fantasy", fontsize=11)
ax.set_ylabel("Frecuencia", fontsize=11)
ax.set_title("Distribución del Target (Puntos Fantasy Porteros)", fontsize=12)
ax.legend(fontsize=10)
ax.grid(alpha=0.3, axis="y")
plt.tight_layout()
plt.savefig(DIRECTORIO_SALIDA / "03_target_distribution.png", dpi=150, bbox_inches="tight")
plt.close()
print("✅ Gráfico 3: target_distribution.png")

# Gráfico 4: Scatter top predictor vs target
if len(strong) > 0:
    top_feature = strong.iloc[0]["Feature"]
    fig, ax = plt.subplots(figsize=(12, 8))
    
    mask = df_porteros[[top_feature, target_col]].notna().all(axis=1)
    sample = df_porteros[mask].sample(min(500, mask.sum()), random_state=42)
    
    ax.scatter(sample[top_feature], sample[target_col], alpha=0.5, s=50)
    
    # Línea de tendencia
    z = np.polyfit(sample[top_feature], sample[target_col], 1)
    p = np.poly1d(z)
    x_line = np.linspace(sample[top_feature].min(), sample[top_feature].max(), 100)
    ax.plot(x_line, p(x_line), "r--", linewidth=2, label=f"Tendencia (r={max_corr:.3f})")
    
    ax.set_xlabel(f"{top_feature}", fontsize=11)
    ax.set_ylabel("Puntos Fantasy", fontsize=11)
    ax.set_title(f"Relación: {top_feature} vs Target\n(Top predictor, r={max_corr:.4f})", fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(DIRECTORIO_SALIDA / "04_top_feature_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("✅ Gráfico 4: top_feature_scatter.png")

print("\n✅ Todos los gráficos guardados en:", DIRECTORIO_SALIDA)

print("\n")


# ===========================
# 12. RESUMEN FINAL
# ===========================
print("="*80)
print("🎯 RESUMEN EJECUTIVO")
print("="*80 + "\n")

print(f"""
HALLAZGO PRINCIPAL:
  Máxima correlación: {max_corr:.6f} ({max_corr_feature})
  
CLASIFICACIÓN:
  Dataset {"muy ruidoso" if max_corr < 0.3 else "ruidoso" if max_corr < 0.4 else "típico para deportes" if max_corr < 0.5 else "limpio"}
  
ESPACIO DE MEJORA:
  R² máximo posible: {r2_max_theoretical:.6f} (vs actual: -0.0165)
  Margen de mejora: {r2_max_theoretical*100:.2f}%
  
FEATURES ÚTILES:
  Fuertes (|corr|>=0.3): {len(strong)} features
  Débiles (|corr|<0.15): {len(weak)} features (eliminar)
  
RECOMENDACIÓN INMEDIATA:
  {"Agregar variables contextuales (clima, árbitro, lesiones)" if max_corr < 0.4 else "Considerar ensemble o features no-lineales"}
  
PRÓXIMO PASO:
  Ejecutar: python correlaciones_profundas.py
  Revisar: {csv_corr_path}
  Analizar: {DIRECTORIO_SALIDA}/04_top_feature_scatter.png
""")

print("="*80)
print("✅ ANÁLISIS COMPLETADO")
print("="*80)
