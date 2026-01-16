"""
ANÁLISIS SHAP GLOBAL - PORTEROS
Usa el modelo entrenado para generar gráficos de explicabilidad
"""

import pickle
import shap
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# 1) Cargar modelo, explainer, SHAP values y features
# ============================================================

MODELO_PATH = "modelos/best_mae_win3_rf_win3_rf_ne200_d8_l3_mf5_mae3.2658_rmse3.9936_r20.0206.pkl"
EXPLAINER_PATH = "explainer_shap.pkl"
SHAP_VALUES_PATH = "shap_values_test.pkl"
FEATURES_PATH = "feature_cols_win3.pkl"

print("📂 Cargando modelo y SHAP...")

with open(MODELO_PATH, "rb") as f:
    modelo = pickle.load(f)

with open(EXPLAINER_PATH, "rb") as f:
    explainer = pickle.load(f)

with open(SHAP_VALUES_PATH, "rb") as f:
    shap_values = pickle.load(f)  # shape (n_test, n_features)

with open(FEATURES_PATH, "rb") as f:
    feature_cols = pickle.load(f)

print("✅ Todos los archivos cargados\n")

# ============================================================
# 2) SUMMARY PLOT (importancias globales)
# ============================================================

print("📊 Generando Summary Plot...")
plt.figure(figsize=(12, 8))
shap.summary_plot(shap_values, feature_names=feature_cols, show=False, plot_type="dot")
plt.title("SHAP Summary Plot - Porteros (ventana 3)", fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig("shap_summary_porteros_win3.png", dpi=300, bbox_inches="tight")
print("✅ Guardado: shap_summary_porteros_win3.png\n")

# ============================================================
# 3) BAR PLOT (importancias ordenadas)
# ============================================================

print("📊 Generando Bar Plot...")
plt.figure(figsize=(10, 8))
shap.summary_plot(shap_values, feature_names=feature_cols, show=False, plot_type="bar")
plt.title("SHAP Feature Importance (Bar) - Porteros", fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig("shap_bar_porteros_win3.png", dpi=300, bbox_inches="tight")
print("✅ Guardado: shap_bar_porteros_win3.png\n")

# ============================================================
# 4) DEPENDENCE PLOTS (relación feature - SHAP)
# ============================================================

# Seleccionar features TOP 5 para dependence
top_5_idx = np.argsort(np.abs(shap_values).mean(axis=0))[-5:]
top_5_features = [feature_cols[i] for i in top_5_idx]

print("📊 Generando Dependence Plots para:", top_5_features)

for feature in top_5_features:
    idx = feature_cols.index(feature)
    plt.figure(figsize=(10, 5))
    shap.dependence_plot(idx, shap_values, None, feature_names=feature_cols, show=False)
    plt.title(f"SHAP Dependence: {feature}", fontsize=12, fontweight="bold")
    plt.tight_layout()
    filename = f"shap_dependence_{feature}.png"
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    print(f"  ✅ {filename}")

print("\n" + "="*80)
print("✅ ANÁLISIS SHAP GLOBAL COMPLETADO")
print("="*80)
print("\nArchivos generados:")
print("  1. shap_summary_porteros_win3.png")
print("  2. shap_bar_porteros_win3.png")
print("  3. shap_dependence_*.png (5 archivos)\n")
