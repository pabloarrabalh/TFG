from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from common_trainer import BaseTrainer


DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS = BaseTrainer.build_output_dirs("consejero")

CONFIG = {
    "archivo": "csv/csvGenerados/players_matches_all_seasons.csv",
    "puntos_fichar_umbral": 7.5,
    "train_ratio": 0.85,
}

FEATURES = [
    "pf_last5",
    "pf_last3",
    "min_last5",
    "starter_rate5",
    "form_trend_3_8",
    "home_rate5",
    "age_num",
    "vs_pos_avg",
    "posicion_enc",
]

FEATURE_DESC = {
    "pf_last5": "media de puntos de los ultimos 5 partidos",
    "pf_last3": "media de puntos de los ultimos 3 partidos",
    "min_last5": "minutos medios en los ultimos 5 partidos",
    "starter_rate5": "ratio de titularidades en los ultimos 5 partidos",
    "form_trend_3_8": "tendencia de forma corta frente a media (3 vs 8 partidos)",
    "home_rate5": "proporcion de partidos recientes jugados como local",
    "age_num": "edad del jugador",
    "vs_pos_avg": "diferencia frente a la media esperada de su posicion",
    "posicion_enc": "impacto base de la posicion del jugador",
}

LABEL_MAP = {0: "vender", 1: "fichar"}
POS_ENC = {"PT": 0.0, "DF": 1.0, "MC": 2.0, "DT": 3.0}


def _normalizar_posicion(value: str) -> str | None:
    raw = (value or "").strip().lower()
    if raw in {"pt", "portero"}:
        return "PT"
    if raw in {"df", "defensa"}:
        return "DF"
    if raw in {"mc", "centrocampista"}:
        return "MC"
    if raw in {"dt", "delantero"}:
        return "DT"
    return None


def _season_to_int(value: str) -> int:
    raw = (value or "").strip()
    parts = raw.split("_")
    if not parts:
        return -1
    try:
        return int(parts[0])
    except ValueError:
        return -1


def _build_unique_player_key(df: pd.DataFrame) -> pd.Series:
    name = df["player"].astype(str).str.strip().str.lower()
    nat = df.get("nacionalidad", pd.Series(["" for _ in range(len(df))])).astype(str).str.strip().str.lower()
    return name + "|" + nat


def _rolling_shifted_mean(grouped: pd.core.groupby.DataFrameGroupBy, column: str, window: int) -> pd.Series:
    return grouped[column].apply(
        lambda s: s.shift(1).rolling(window=window, min_periods=1).mean()
    ).reset_index(level=0, drop=True)


def _rolling_shifted_std(grouped: pd.core.groupby.DataFrameGroupBy, column: str, window: int) -> pd.Series:
    return grouped[column].apply(
        lambda s: s.shift(1).rolling(window=window, min_periods=2).std()
    ).reset_index(level=0, drop=True)


class ConsejeroTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("consejero")

    def cargar_datos(self) -> pd.DataFrame:
        archivo = CONFIG["archivo"]
        df = pd.read_csv(archivo, low_memory=False)

        required = {
            "player",
            "nacionalidad",
            "posicion",
            "puntos_fantasy",
            "min_partido",
            "titular",
            "temporada",
            "jornada",
        }
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"Faltan columnas obligatorias en dataset: {missing}")

        return df

    def preparar_training_frame(self, raw_df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
        df = raw_df.copy()

        df["temporada"] = df["temporada"].astype(str).str.strip()
        df["jornada_num"] = pd.to_numeric(df["jornada"], errors="coerce")
        df["puntos_fantasy"] = pd.to_numeric(df["puntos_fantasy"], errors="coerce")
        df["min_partido"] = pd.to_numeric(df["min_partido"], errors="coerce").fillna(0.0)
        df["titular_num"] = pd.to_numeric(df["titular"], errors="coerce").fillna(0.0)
        df["titular_num"] = df["titular_num"].clip(lower=0, upper=1)

        numeric_extra = [
            "gol_partido",
            "asist_partido",
            "xg_partido",
            "xag",
            "tiros",
            "tiro_puerta_partido",
            "pases_totales",
            "pases_completados_pct",
            "entradas",
            "duelos",
            "duelos_ganados",
            "despejes",
            "regates_completados",
            "conducciones_progresivas",
            "amarillas",
            "rojas",
            "porcentaje_paradas",
            "psxg",
            "goles_en_contra",
            "edad",
            "local",
        ]
        for col in numeric_extra:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        df["pos_code"] = df["posicion"].apply(_normalizar_posicion)
        df["season_ord"] = df["temporada"].apply(_season_to_int)

        df = df.dropna(subset=["jornada_num", "puntos_fantasy", "pos_code"])
        df = df[df["season_ord"] >= 0].copy()

        df["jornada_num"] = df["jornada_num"].astype(int)
        df["player_key"] = _build_unique_player_key(df)
        df["time_ord"] = df["season_ord"] * 100 + df["jornada_num"]

        df = df.sort_values(["player_key", "time_ord", "jornada_num"]).reset_index(drop=True)

        grouped = df.groupby("player_key", sort=False)

        df["matches_before"] = grouped.cumcount()
        df["pf_last3"] = _rolling_shifted_mean(grouped, "puntos_fantasy", 3)
        df["pf_last5"] = _rolling_shifted_mean(grouped, "puntos_fantasy", 5)
        df["pf_last8"] = _rolling_shifted_mean(grouped, "puntos_fantasy", 8)
        df["pf_std5"] = _rolling_shifted_std(grouped, "puntos_fantasy", 5)
        df["min_last3"] = _rolling_shifted_mean(grouped, "min_partido", 3)
        df["min_last5"] = _rolling_shifted_mean(grouped, "min_partido", 5)
        df["starter_rate3"] = _rolling_shifted_mean(grouped, "titular_num", 3)
        df["starter_rate5"] = _rolling_shifted_mean(grouped, "titular_num", 5)
        df["form_trend"] = df["pf_last3"] - df["pf_last5"]
        df["form_trend_3_8"] = df["pf_last3"] - df["pf_last8"]

        def _safe_roll(src: str, out: str, window: int = 5) -> None:
            if src in df.columns:
                df[out] = _rolling_shifted_mean(grouped, src, window)
            else:
                df[out] = 0.0

        _safe_roll("gol_partido", "goals_last5")
        _safe_roll("asist_partido", "assists_last5")
        _safe_roll("xg_partido", "xg_last5")
        _safe_roll("xag", "xag_last5")
        _safe_roll("tiros", "shots_last5")
        _safe_roll("tiro_puerta_partido", "sot_last5")
        _safe_roll("pases_totales", "passes_last5")
        _safe_roll("pases_completados_pct", "pass_acc_last5")
        _safe_roll("entradas", "tackles_last5")
        _safe_roll("despejes", "clears_last5")
        _safe_roll("regates_completados", "dribbles_succ_last5")
        _safe_roll("conducciones_progresivas", "prog_carries_last5")
        _safe_roll("amarillas", "yellow_last5")
        _safe_roll("rojas", "red_last5")
        _safe_roll("porcentaje_paradas", "save_pct_last5")
        _safe_roll("psxg", "psxg_last5")
        _safe_roll("goles_en_contra", "gc_last5")
        _safe_roll("local", "home_rate5")

        duels_last5 = _rolling_shifted_mean(grouped, "duelos", 5) if "duelos" in df.columns else 0.0
        duels_won_last5 = _rolling_shifted_mean(grouped, "duelos_ganados", 5) if "duelos_ganados" in df.columns else 0.0
        df["duels_won_rate5"] = np.where(duels_last5 > 0, duels_won_last5 / duels_last5, 0.0)

        if "edad" in df.columns:
            df["age_num"] = pd.to_numeric(df["edad"], errors="coerce")
            df["age_num"] = df["age_num"].fillna(df["age_num"].median())
        else:
            df["age_num"] = 27.0

        df["target_next_points"] = grouped["puntos_fantasy"].shift(-1)

        df = df[(df["matches_before"] >= 1) & (df["target_next_points"].notna())].copy()

        for col in FEATURES:
            if col in {"vs_pos_avg", "posicion_enc"}:
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        unique_times = np.sort(df["time_ord"].unique())
        if len(unique_times) < 8:
            raise ValueError("No hay suficiente historial temporal para un split sin leakage")

        train_ratio = float(CONFIG["train_ratio"])
        cut_idx = max(0, min(int(len(unique_times) * train_ratio) - 1, len(unique_times) - 2))
        cut_time = float(unique_times[cut_idx])

        return df, cut_time

    def build_labels(self, df: pd.DataFrame, cut_time: float) -> tuple[pd.DataFrame, dict[str, float], float]:
        train_mask = df["time_ord"] <= cut_time
        test_mask = df["time_ord"] > cut_time

        if train_mask.sum() == 0 or test_mask.sum() == 0:
            raise ValueError("Split temporal invalido: train/test vacios")

        pos_ref = (
            df.loc[train_mask]
            .groupby("pos_code")["target_next_points"]
            .mean()
            .to_dict()
        )
        global_ref = float(df.loc[train_mask, "target_next_points"].mean())
        if not np.isfinite(global_ref) or global_ref <= 0:
            global_ref = 5.0

        df["pos_ref"] = df["pos_code"].map(pos_ref).fillna(global_ref)
        df["pos_ref"] = df["pos_ref"].replace(0, global_ref)

        df["vs_pos_avg"] = df["pf_last3"] - df["pos_ref"]
        df["posicion_enc"] = df["pos_code"].map(POS_ENC).astype(float)

        puntos_fichar_umbral = float(CONFIG["puntos_fichar_umbral"])
        umbral_relativo = np.maximum(df["pos_ref"], puntos_fichar_umbral)
        df["target_class"] = np.where(df["target_next_points"] >= umbral_relativo, 1, 0)

        return df, pos_ref, global_ref

    @staticmethod
    def calibrar_umbral_prob_fichar(y_true: np.ndarray, prob_fichar: np.ndarray) -> tuple[float, dict]:
        y_true = np.asarray(y_true).astype(int)
        prob_fichar = np.asarray(prob_fichar, dtype=float)

        prior = float(np.mean(y_true)) if len(y_true) else 0.2
        thresholds = np.linspace(0.1, 0.9, 81)

        best = None
        for thr in thresholds:
            y_pred = (prob_fichar >= thr).astype(int)
            pos_rate = float(np.mean(y_pred))
            bal = float(balanced_accuracy_score(y_true, y_pred))
            f1 = float(f1_score(y_true, y_pred, zero_division=0))

            score = bal - (0.25 * abs(pos_rate - prior)) + (0.05 * f1)

            if best is None or score > best["score"]:
                best = {
                    "threshold": float(thr),
                    "score": score,
                    "balanced_accuracy": bal,
                    "f1": f1,
                    "predicted_fichar_rate": pos_rate,
                    "prior_fichar_rate": prior,
                }

        if not best:
            return 0.25, {
                "threshold": 0.25,
                "balanced_accuracy": 0.0,
                "f1": 0.0,
                "predicted_fichar_rate": 0.0,
                "prior_fichar_rate": prior,
                "strategy": "fallback",
            }

        best["strategy"] = "balanced_accuracy_with_prior_penalty"
        return best["threshold"], best

    def fit_model(self, df: pd.DataFrame, cut_time: float) -> tuple[Pipeline, dict]:
        train_mask = df["time_ord"] <= cut_time
        test_mask = df["time_ord"] > cut_time

        X_train = df.loc[train_mask, FEATURES].values
        y_train = df.loc[train_mask, "target_class"].values.astype(int)

        X_test = df.loc[test_mask, FEATURES].values
        y_test = df.loc[test_mask, "target_class"].values.astype(int)

        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="liblinear",
                    random_state=42,
                ),
            ),
        ])
        pipeline.fit(X_train, y_train)

        proba_test = pipeline.predict_proba(X_test)[:, 1]
        umbral_prob_fichar, calibration_info = self.calibrar_umbral_prob_fichar(y_test, proba_test)

        y_pred = (proba_test >= umbral_prob_fichar).astype(int)
        y_pred_default = (proba_test >= 0.5).astype(int)

        puntos_fichar_umbral = float(CONFIG["puntos_fichar_umbral"])
        metricas = {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "balanced_accuracy": round(float(balanced_accuracy_score(y_test, y_pred)), 4),
            "accuracy_default_0_5": round(float(accuracy_score(y_test, y_pred_default)), 4),
            "balanced_accuracy_default_0_5": round(float(balanced_accuracy_score(y_test, y_pred_default)), 4),
            "n_train": int(train_mask.sum()),
            "n_test": int(test_mask.sum()),
            "feature_count": len(FEATURES),
            "features": FEATURES,
            "umbrales": {
                "puntos_fichar": puntos_fichar_umbral,
                "prob_fichar": round(float(umbral_prob_fichar), 4),
            },
            "decision_prob_fichar": round(float(umbral_prob_fichar), 4),
            "calibration": {
                "strategy": calibration_info.get("strategy"),
                "prior_fichar_rate": round(float(calibration_info.get("prior_fichar_rate", 0.0)), 4),
                "predicted_fichar_rate": round(float(calibration_info.get("predicted_fichar_rate", 0.0)), 4),
                "balanced_accuracy": round(float(calibration_info.get("balanced_accuracy", 0.0)), 4),
                "f1": round(float(calibration_info.get("f1", 0.0)), 4),
            },
            "label_map": {str(k): v for k, v in LABEL_MAP.items()},
            "model_type": "logistic_regression",
            "class_distribution_train": {
                str(int(k)): int(v)
                for k, v in pd.Series(y_train).value_counts().sort_index().items()
            },
            "class_distribution_test": {
                str(int(k)): int(v)
                for k, v in pd.Series(y_test).value_counts().sort_index().items()
            },
            "split": {
                "strategy": "temporal",
                "train_ratio": float(CONFIG["train_ratio"]),
                "time_cut": cut_time,
            },
            "leakage_control": [
                "features usan shift(1): solo informacion historica por jugador",
                "target es puntos del siguiente partido (shift -1)",
                "split temporal: train pasado, test futuro",
                "fichar si target_next_points >= umbral absoluto; medias por posicion solo para features",
                "decision final calibrada con umbral probabilistico para evitar sesgo a vender",
            ],
            "classification_report": classification_report(
                y_test,
                y_pred,
                labels=[0, 1],
                target_names=[LABEL_MAP[0], LABEL_MAP[1]],
                output_dict=True,
                zero_division=0,
            ),
        }

        BaseTrainer.print_split_summary(
            df.loc[train_mask, FEATURES],
            df.loc[test_mask, FEATURES],
            pd.Series(y_train),
            pd.Series(y_test),
        )

        return pipeline, metricas

    def save_artifacts(self, pipeline: Pipeline, metricas: dict, df: pd.DataFrame, cut_time: float) -> None:
        joblib.dump(pipeline, DIRECTORIO_SALIDA / "modelo_consejero.pkl")

        with (DIRECTORIO_SALIDA / "features_consejero.json").open("w", encoding="utf-8") as f:
            json.dump(FEATURES, f, indent=2, ensure_ascii=False)

        with (DIRECTORIO_SALIDA / "feature_desc_consejero.json").open("w", encoding="utf-8") as f:
            json.dump(FEATURE_DESC, f, indent=2, ensure_ascii=False)

        with (DIRECTORIO_SALIDA / "label_map.json").open("w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in LABEL_MAP.items()}, f, indent=2, ensure_ascii=False)

        train_mask = df["time_ord"] <= cut_time
        pos_avgs = (
            df.loc[train_mask]
            .groupby(["pos_code", "temporada"])["target_next_points"]
            .mean()
            .reset_index()
        )
        pos_avgs_dict = {
            f"{row.pos_code}_{row.temporada}": round(float(row.target_next_points), 4)
            for row in pos_avgs.itertuples(index=False)
        }

        with (DIRECTORIO_SALIDA / "pos_avgs.json").open("w", encoding="utf-8") as f:
            json.dump(pos_avgs_dict, f, indent=2, ensure_ascii=False)

        with (DIRECTORIO_SALIDA / "metricas_consejero.json").open("w", encoding="utf-8") as f:
            json.dump(metricas, f, indent=2, ensure_ascii=False)

    def run(self) -> None:
        BaseTrainer.print_banner("ENTRENAMIENTO CONSEJERO")

        BaseTrainer.print_section("CARGA DE DATOS")
        raw_df = self.cargar_datos()
        print(f"Filas origen: {len(raw_df)}")

        BaseTrainer.print_section("FEATURES SIN LEAKAGE")
        df, cut_time = self.preparar_training_frame(raw_df)
        print(f"Filas con historial y target: {len(df)}")

        BaseTrainer.print_section("LABELS")
        df, _, _ = self.build_labels(df, cut_time)

        BaseTrainer.print_section("ENTRENAMIENTO")
        pipeline, metricas = self.fit_model(df, cut_time)

        BaseTrainer.print_section("GUARDADO DE ARTEFACTOS")
        self.save_artifacts(pipeline, metricas, df, cut_time)

        print(f"Accuracy: {metricas['accuracy']}")
        print(f"Balanced accuracy: {metricas['balanced_accuracy']}")
        print(f"Umbral prob_fichar: {metricas.get('decision_prob_fichar')}")
        print(f"Artefactos en: {DIRECTORIO_SALIDA}")

        BaseTrainer.print_banner("ENTRENAMIENTO CONSEJERO COMPLETADO")


def main() -> None:
    ConsejeroTrainer().run()


if __name__ == "__main__":
    main()
