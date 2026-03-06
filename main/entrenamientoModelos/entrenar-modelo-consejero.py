"""
Entrena un modelo de clasificación para el Consejero de Fantasy.

Para cada jugador en cada jornada, a partir de sus estadísticas recientes
predice si en los próximos 3 partidos rendirá por encima, en la media o
por debajo de la media de su posición.

Label:
  0 = vender  (rendimiento futuro < 85% media posición)
  1 = mantener (85% – 115%)
  2 = fichar  (> 115% media posición)

Features (todas computables desde la BD en inferencia):
  pf_last3       – media puntos últimos 3 partidos
  pf_last5       – media puntos últimos 5 partidos
  min_last3      – media minutos últimos 3 partidos
  starter_rate3  – ratio de titularidades últimos 3 partidos
  form_trend     – pf_last3 − pf_last5 (momentum)
  vs_pos_avg     – pf_last3 − media posición en la temporada
  posicion_enc   – PT=0, DF=1, MC=2, DT=3

Output:
  csv/csvGenerados/entrenamiento/consejero/
    modelo_consejero.pkl     – Pipeline (scaler + RF)
    features_consejero.json  – nombre de las features en orden
    label_map.json           – mapping int → string
    metricas_consejero.json  – accuracy, matriz de confusión, etc.
    pos_avgs.json            – medias por posición y temporada (para inferencia)
    imagenes/                – confusion matrix + feature importance + SHAP summary
"""
import warnings
warnings.filterwarnings("ignore")

import sys
import json
import joblib
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    balanced_accuracy_score
)
import shap

# ─── Rutas ────────────────────────────────────────────────────────────────────
CSV_PATH = Path("csv/csvGenerados/players_with_features.csv")
DIRECTORIO_SALIDA    = Path("csv/csvGenerados/entrenamiento/consejero")
DIRECTORIO_IMAGENES  = DIRECTORIO_SALIDA / "imagenes"

for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Config ───────────────────────────────────────────────────────────────────
FEATURES     = ["pf_last3", "pf_last5", "min_last3", "starter_rate3",
                "form_trend", "vs_pos_avg", "posicion_enc"]
LABEL_MAP    = {0: "vender", 1: "mantener", 2: "fichar"}
POSICION_ENC = {"PT": 0, "DF": 1, "MC": 2, "DT": 3}

UMBRAL_BAJO  = 0.85   # < 85% media → vender
UMBRAL_ALTO  = 1.15   # > 115% media → fichar
OUTLIER_MAX  = 40     # puntos_fantasy máximos (mismos que los demás modelos)
MIN_MINUTOS  = 10     # descartar partidos con <10 minutos


# ─── 1. Carga y limpieza ──────────────────────────────────────────────────────
def cargar_datos():
    print(f"Cargando {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    print(f"  Shape inicial: {df.shape}")

    # Tipos numéricos
    for col in ["puntos_fantasy", "min_partido", "titular", "jornada"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Filtrar outliers y partidos con pocos minutos
    df = df[df["puntos_fantasy"] <= OUTLIER_MAX].copy()
    df = df[df["min_partido"] >= MIN_MINUTOS].copy()

    # Normalizar posicion
    df["posicion"] = df["posicion"].str.strip().str.upper()
    df = df[df["posicion"].isin(POSICION_ENC)].copy()

    # Ordenar temporalmente
    df = df.sort_values(["player", "temporada", "jornada"]).reset_index(drop=True)

    print(f"  Shape tras limpieza: {df.shape}")
    print(f"  Posiciones: {df['posicion'].value_counts().to_dict()}")
    return df


# ─── 2. Features por rolling window ──────────────────────────────────────────
def crear_features(df):
    print("Creando features de ventana temporal...")
    grp = df.groupby(["player", "temporada"])

    # Medias rodantes (shift(1) para evitar data leakage)
    df["pf_last3"] = grp["puntos_fantasy"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )
    df["pf_last5"] = grp["puntos_fantasy"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=1).mean()
    )
    df["min_last3"] = grp["min_partido"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )
    df["starter_rate3"] = grp["titular"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )

    # Momentum: tendencia positiva si últimos 3 > últimos 5
    df["form_trend"] = df["pf_last3"] - df["pf_last5"]

    # Encoding de posición
    df["posicion_enc"] = df["posicion"].map(POSICION_ENC)

    # Media de posición por temporada (para vs_pos_avg)
    pos_avg = (
        df.groupby(["posicion", "temporada"])["puntos_fantasy"]
        .mean()
        .rename("pos_avg_season")
        .reset_index()
    )
    df = df.merge(pos_avg, on=["posicion", "temporada"], how="left")
    df["vs_pos_avg"] = df["pf_last3"] - df["pos_avg_season"]

    return df, pos_avg


# ─── 3. Label: rendimiento futuro relativo ───────────────────────────────────
def crear_labels(df):
    print("Creando etiquetas de rendimiento futuro...")
    grp = df.groupby(["player", "temporada"])

    # Media de los próximos 3 partidos
    df["pf_future1"] = grp["puntos_fantasy"].transform(lambda x: x.shift(-1))
    df["pf_future2"] = grp["puntos_fantasy"].transform(lambda x: x.shift(-2))
    df["pf_future3"] = grp["puntos_fantasy"].transform(lambda x: x.shift(-3))
    df["pf_next3_avg"] = df[["pf_future1", "pf_future2", "pf_future3"]].mean(axis=1)

    # Score normalizado sobre la media de posición
    df["future_score"] = df["pf_next3_avg"] / df["pos_avg_season"].clip(lower=0.1)

    # Eliminar filas sin datos futuros o sin features
    df = df.dropna(subset=FEATURES + ["future_score"])

    # Label: 0=vender, 1=mantener, 2=fichar  (np.select evita problemas con NaN)
    df["label"] = np.select(
        [df["future_score"] < UMBRAL_BAJO, df["future_score"] >= UMBRAL_ALTO],
        [0, 2],
        default=1,
    ).astype(int)
    df["label"] = df["label"].astype(int)

    dist = df["label"].value_counts().sort_index()
    for lbl, cnt in dist.items():
        print(f"  {LABEL_MAP[lbl]:10s}: {cnt:6d} ({100*cnt/len(df):.1f}%)")

    return df


# ─── 4. Entrenamiento ─────────────────────────────────────────────────────────
def entrenar(df):
    print("\nEntrenando modelo...")
    X = df[FEATURES].values.astype(float)
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(random_state=42, n_jobs=-1, class_weight="balanced")),
    ])

    param_grid = {
        "clf__n_estimators":    [200, 400],
        "clf__max_depth":       [10, 20, None],
        "clf__min_samples_leaf":[2, 4],
        "clf__max_features":    ["sqrt"],
    }
    total_fits = 2 * 3 * 2 * 1 * 5   # GridSearchCV con cv=5
    print(f"  GridSearchCV: {total_fits} fits (~2×3×2×1 config × 5 folds)")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    gs = GridSearchCV(
        pipeline, param_grid, cv=cv,
        scoring="balanced_accuracy",
        n_jobs=-1, verbose=1
    )
    gs.fit(X_train, y_train)

    best = gs.best_estimator_
    print(f"\n  Mejores hiperparámetros: {gs.best_params_}")

    y_pred = best.predict(X_test)
    acc  = accuracy_score(y_test, y_pred)
    bacc = balanced_accuracy_score(y_test, y_pred)
    print(f"\n  Accuracy          : {acc:.4f}")
    print(f"  Balanced Accuracy : {bacc:.4f}")
    print("\n" + classification_report(y_test, y_pred,
          target_names=["vender", "mantener", "fichar"]))

    return best, X_train, X_test, y_train, y_test, y_pred, acc, bacc


# ─── 5. Visualizaciones ───────────────────────────────────────────────────────
def guardar_confusion_matrix(y_test, y_pred):
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["vender", "mantener", "fichar"],
                yticklabels=["vender", "mantener", "fichar"], ax=ax)
    ax.set_xlabel("Predicción")
    ax.set_ylabel("Real")
    ax.set_title("Matriz de Confusión – Consejero", fontweight="bold")
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / "confusion_matrix.png", dpi=150)
    plt.close()
    print("  Saved: confusion_matrix.png")


def guardar_feature_importance(pipeline, feature_names):
    rf = pipeline.named_steps["clf"]
    importances = rf.feature_importances_
    idx = np.argsort(importances)[::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(feature_names)))
    ax.barh(range(len(feature_names)),
            importances[idx][::-1], color=colors)
    ax.set_yticks(range(len(feature_names)))
    ax.set_yticklabels([feature_names[i] for i in idx][::-1], fontsize=10)
    ax.set_xlabel("Importancia")
    ax.set_title("Feature Importance – Consejero", fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / "feature_importance.png", dpi=150)
    plt.close()
    print("  Saved: feature_importance.png")


def guardar_shap(pipeline, X_train, feature_names):
    print("  Calculando SHAP values (muestra de 500 filas)...")
    scaler = pipeline.named_steps["scaler"]
    clf    = pipeline.named_steps["clf"]

    # Muestra representativa para el summary plot
    idx    = np.random.choice(len(X_train), min(500, len(X_train)), replace=False)
    X_samp = scaler.transform(X_train[idx])

    explainer   = shap.TreeExplainer(clf)
    shap_values = explainer.shap_values(X_samp)   # shape: (n_classes, n_samples, n_features) o lista

    # Normalizar formato: en SHAP ≥0.42 puede ser array 3D (n_samples, n_features, n_classes)
    if isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        shap_fichar = shap_values[:, :, 2]   # clase 2 = fichar
    elif isinstance(shap_values, list):
        shap_fichar = shap_values[2]
    else:
        print("  SHAP: formato inesperado, plot omitido")
        return

    shap.summary_plot(
        shap_fichar, X_samp,
        feature_names=feature_names,
        show=False, plot_size=(10, 5)
    )
    plt.title("SHAP – Factores que influyen en FICHAR", fontweight="bold")
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / "shap_fichar.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved: shap_fichar.png")


# ─── 6. Guardado ──────────────────────────────────────────────────────────────
def guardar_artefactos(pipeline, pos_avg, acc, bacc):
    joblib.dump(pipeline, DIRECTORIO_SALIDA / "modelo_consejero.pkl")
    print("  Saved: modelo_consejero.pkl")

    with open(DIRECTORIO_SALIDA / "features_consejero.json", "w") as f:
        json.dump(FEATURES, f, ensure_ascii=False, indent=2)
    print("  Saved: features_consejero.json")

    with open(DIRECTORIO_SALIDA / "label_map.json", "w") as f:
        json.dump(LABEL_MAP, f, ensure_ascii=False, indent=2)
    print("  Saved: label_map.json")

    metricas = {
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(bacc, 4),
        "umbrales": {"bajo": UMBRAL_BAJO, "alto": UMBRAL_ALTO},
        "features": FEATURES,
        "n_classes": 3,
    }
    with open(DIRECTORIO_SALIDA / "metricas_consejero.json", "w") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    print("  Saved: metricas_consejero.json")

    # Medias por posición+temporada para inferencia
    pos_avg_dict = {}
    for _, row in pos_avg.iterrows():
        key = f"{row['posicion']}_{row['temporada']}"
        pos_avg_dict[key] = round(float(row["pos_avg_season"]), 4)
    with open(DIRECTORIO_SALIDA / "pos_avgs.json", "w") as f:
        json.dump(pos_avg_dict, f, ensure_ascii=False, indent=2)
    print("  Saved: pos_avgs.json")


# ─── main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("ENTRENAMIENTO MODELO CONSEJERO – FANTASY FOOTBALL")
    print("=" * 70 + "\n")

    df                    = cargar_datos()
    df, pos_avg           = crear_features(df)
    df                    = crear_labels(df)

    pipeline, X_train, X_test, y_train, y_test, y_pred, acc, bacc = entrenar(df)

    print("\nGenerando visualizaciones...")
    guardar_confusion_matrix(y_test, y_pred)
    guardar_feature_importance(pipeline, FEATURES)
    guardar_shap(pipeline, X_train, FEATURES)

    print("\nGuardando artefactos...")
    guardar_artefactos(pipeline, pos_avg, acc, bacc)

    print(f"\n{'='*70}")
    print(f"ENTRENAMIENTO COMPLETADO")
    print(f"  Accuracy          : {acc:.4f}")
    print(f"  Balanced Accuracy : {bacc:.4f}")
    print(f"  Artefactos en     : {DIRECTORIO_SALIDA.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
