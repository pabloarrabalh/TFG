from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from django.db.models import Avg, Max

try:
    import joblib
except ImportError: 
    joblib = None

try:
    import shap as _shap
except ImportError:  
    _shap = None

from ..models import EquipoJugadorTemporada, EstadisticasPartidoJugador, Jornada, Jugador, Temporada


logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parents[2] / "csv" / "csvGenerados" / "entrenamiento" / "consejero"

_pipeline = None
_explainer = None
_pos_avgs = {}
_feature_desc = {}
_thresholds = {"puntos_fichar": 7.5, "prob_fichar": 0.25}

_POSICION_ENC = {"PT": 0, "DF": 1, "MC": 2, "DT": 3}

_FEATURES = [
    "pf_last3",
    "pf_last5",
    "pf_last8",
    "pf_std5",
    "min_last3",
    "min_last5",
    "starter_rate3",
    "starter_rate5",
    "form_trend",
    "form_trend_3_8",
    "goals_last5",
    "assists_last5",
    "xg_last5",
    "xag_last5",
    "shots_last5",
    "sot_last5",
    "passes_last5",
    "pass_acc_last5",
    "tackles_last5",
    "duels_won_rate5",
    "clears_last5",
    "dribbles_succ_last5",
    "prog_carries_last5",
    "yellow_last5",
    "red_last5",
    "save_pct_last5",
    "psxg_last5",
    "gc_last5",
    "home_rate5",
    "age_num",
    "vs_pos_avg",
    "posicion_enc",
]


class ConsejeroValidationError(Exception):
    pass


class ConsejeroNotFoundError(Exception):
    pass


class ConsejeroServiceError(Exception):
    pass


def _fallback_feature_desc(feature_name: str) -> str:
    return str(feature_name).replace("_", " ")


def _desc_feature(feature_name: str) -> str:
    if isinstance(_feature_desc, dict) and feature_name in _feature_desc:
        return str(_feature_desc.get(feature_name))
    return _fallback_feature_desc(feature_name)


def _normalizar_posicion(posicion: str | None) -> str:
    raw = (posicion or "").strip().lower()
    if raw in {"pt", "portero", "goalkeeper", "gk"}:
        return "PT"
    if raw in {"df", "defensa", "defender", "cb", "rb", "lb"}:
        return "DF"
    if raw in {"mc", "centrocampista", "midfielder", "mf", "cm", "dm", "am"}:
        return "MC"
    if raw in {"dt", "delantero", "forward", "fw", "st", "cf"}:
        return "DT"
    return "DT"


def _cargar_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _cargar_modelo() -> bool:
    """Carga el modelo y artefactos una sola vez."""
    global _pipeline, _explainer, _pos_avgs, _feature_desc, _thresholds, _FEATURES

    if _pipeline is not None:
        return True

    if joblib is None:
        logger.error("No se pudo cargar Consejero: falta joblib")
        return False

    try:
        _pipeline = joblib.load(_BASE / "modelo_consejero.pkl")
        _pos_avgs = _cargar_json(_BASE / "pos_avgs.json", {})
        _feature_desc = _cargar_json(_BASE / "feature_desc_consejero.json", {})
        features_file = _cargar_json(_BASE / "features_consejero.json", None)
        if isinstance(features_file, list) and features_file:
            _FEATURES = [str(x) for x in features_file]
        metricas = _cargar_json(_BASE / "metricas_consejero.json", {})
        if isinstance(metricas, dict):
            umbrales = metricas.get("umbrales") or {}
            if isinstance(umbrales, dict):
                current_puntos = float(_thresholds.get("puntos_fichar", 7.5))
                current_prob = float(_thresholds.get("prob_fichar", 0.25))

                if "puntos_fichar" in umbrales:
                    current_puntos = float(umbrales.get("puntos_fichar", current_puntos))
                elif "fichar" in umbrales:
                    current_puntos = float(umbrales.get("fichar", current_puntos))
                elif "alto" in umbrales:
                    current_puntos = float(umbrales.get("alto", current_puntos))

                if "prob_fichar" in umbrales:
                    current_prob = float(umbrales.get("prob_fichar", current_prob))
                elif "decision_prob_fichar" in metricas:
                    current_prob = float(metricas.get("decision_prob_fichar", current_prob))
                elif "decision_threshold" in metricas:
                    current_prob = float(metricas.get("decision_threshold", current_prob))

                current_prob = min(max(current_prob, 0.05), 0.95)
                _thresholds = {"puntos_fichar": current_puntos, "prob_fichar": current_prob}

        if _shap is not None and hasattr(_pipeline, "named_steps"):
            clf = _pipeline.named_steps.get("clf")
            if clf is not None:
                _explainer = _shap.TreeExplainer(clf)
        return True
    except Exception as exc:
        logger.error("No se pudo cargar el modelo Consejero: %s", exc)
        _pipeline = None
        _explainer = None
        _feature_desc = {}
        return False


def _resolver_temporada() -> Temporada | None:
    return (
        Temporada.objects.filter(nombre="25_26").first()
        or Temporada.objects.order_by("-nombre").first()
    )


def _obtener_media_posicion(posicion: str, temporada: Temporada) -> float:
    pos_norm = _normalizar_posicion(posicion)
    pos_db = {
        "PT": "Portero",
        "DF": "Defensa",
        "MC": "Centrocampista",
        "DT": "Delantero",
    }.get(pos_norm, "Delantero")

    value = (
        EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada,
            posicion=pos_db,
        ).aggregate(Avg("puntos_fantasy"))["puntos_fantasy__avg"]
        or 0
    )
    return float(value)


def _obtener_media_posicion_historica(posicion: str, temporada_nombre: str) -> float | None:
    pos_norm = _normalizar_posicion(posicion)
    key_exact = f"{pos_norm}_{temporada_nombre}"
    if key_exact in _pos_avgs:
        try:
            return float(_pos_avgs[key_exact])
        except Exception:
            return None

    values = []
    for key, val in (_pos_avgs or {}).items():
        if not str(key).startswith(f"{pos_norm}_"):
            continue
        try:
            values.append(float(val))
        except Exception:
            continue

    if not values:
        return None
    return float(np.mean(values))


def _mean_attr(items, attr: str, default: float = 0.0) -> float:
    vals = [getattr(it, attr, 0) or 0 for it in items]
    return float(np.mean(vals)) if vals else default


def _std_attr(items, attr: str, default: float = 0.0) -> float:
    vals = [float(getattr(it, attr, 0) or 0) for it in items]
    if len(vals) < 2:
        return default
    return float(np.std(vals, ddof=1))


def _resolver_equipo_jugador(jugador: Jugador, temporada: Temporada) -> int | None:
    row = (
        EquipoJugadorTemporada.objects.filter(jugador=jugador, temporada=temporada)
        .select_related("equipo")
        .first()
    )
    if row and row.equipo_id:
        return int(row.equipo_id)
    return None


def _computar_features(stats_temporada, jugador, posicion, rendimiento_full, media_pos, temporada):
    last3 = stats_temporada[:3]
    last5 = stats_temporada[:5]
    last8 = stats_temporada[:8]

    pf_last3 = _mean_attr(last3, "puntos_fantasy")
    pf_last5 = _mean_attr(last5, "puntos_fantasy")
    pf_last8 = _mean_attr(last8, "puntos_fantasy")
    pf_std5 = _std_attr(last5, "puntos_fantasy")
    min_last3 = _mean_attr(last3, "min_partido")
    min_last5 = _mean_attr(last5, "min_partido")
    starter_rate3 = float(sum(1 for p in last3 if p.titular) / max(len(last3), 1))
    starter_rate5 = float(sum(1 for p in last5 if p.titular) / max(len(last5), 1))
    form_trend = pf_last3 - pf_last5
    form_trend_3_8 = pf_last3 - pf_last8

    temporada_nombre = getattr(temporada, "nombre", "")
    media_hist = _obtener_media_posicion_historica(posicion, temporada_nombre)
    media_ref = media_hist if media_hist is not None and media_hist > 0 else float(media_pos or 0)
    if media_ref <= 0:
        media_ref = float(rendimiento_full or 0)

    vs_pos_avg = pf_last3 - media_ref
    posicion_enc = float(_POSICION_ENC.get(_normalizar_posicion(posicion), 3))

    jugador_equipo_id = _resolver_equipo_jugador(jugador, temporada)
    if jugador_equipo_id:
        home_values = [
            1.0 if getattr(p.partido, "equipo_local_id", None) == jugador_equipo_id else 0.0
            for p in last5
        ]
        home_rate5 = float(np.mean(home_values)) if home_values else 0.0
    else:
        home_rate5 = _mean_attr(last5, "local", default=0.0)

    edad_jugador = getattr(jugador, "edad", None)
    edad_stats = _mean_attr(last5, "edad", default=0.0)
    age_num = float(edad_jugador if edad_jugador is not None else edad_stats or 27.0)

    duels_last5 = _mean_attr(last5, "duelos")
    duels_won_last5 = _mean_attr(last5, "duelos_ganados")
    duels_won_rate5 = float(duels_won_last5 / duels_last5) if duels_last5 > 0 else 0.0

    feature_map = {
        "pf_last3": pf_last3,
        "pf_last5": pf_last5,
        "pf_last8": pf_last8,
        "pf_std5": pf_std5,
        "min_last3": min_last3,
        "min_last5": min_last5,
        "starter_rate3": starter_rate3,
        "starter_rate5": starter_rate5,
        "form_trend": form_trend,
        "form_trend_3_8": form_trend_3_8,
        "goals_last5": _mean_attr(last5, "gol_partido"),
        "assists_last5": _mean_attr(last5, "asist_partido"),
        "xg_last5": _mean_attr(last5, "xg_partido"),
        "xag_last5": _mean_attr(last5, "xag"),
        "shots_last5": _mean_attr(last5, "tiros"),
        "sot_last5": _mean_attr(last5, "tiro_puerta_partido"),
        "passes_last5": _mean_attr(last5, "pases_totales"),
        "pass_acc_last5": _mean_attr(last5, "pases_completados_pct"),
        "tackles_last5": _mean_attr(last5, "entradas"),
        "duels_won_rate5": duels_won_rate5,
        "clears_last5": _mean_attr(last5, "despejes"),
        "dribbles_succ_last5": _mean_attr(last5, "regates_completados"),
        "prog_carries_last5": _mean_attr(last5, "conducciones_progresivas"),
        "yellow_last5": _mean_attr(last5, "amarillas"),
        "red_last5": _mean_attr(last5, "rojas"),
        "save_pct_last5": _mean_attr(last5, "porcentaje_paradas"),
        "psxg_last5": _mean_attr(last5, "psxg"),
        "gc_last5": _mean_attr(last5, "goles_en_contra"),
        "home_rate5": home_rate5,
        "age_num": age_num,
        "vs_pos_avg": vs_pos_avg,
        "posicion_enc": posicion_enc,
    }

    ordered = [float(feature_map.get(name, 0.0) or 0.0) for name in _FEATURES]

    return np.array([ordered], dtype=float)


def _build_factors_with_shap(X_scaled, features_array, pred_idx):
    shap_values = _explainer.shap_values(X_scaled)

    if isinstance(shap_values, list):
        sv_clase = shap_values[pred_idx][0]
    elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        sv_clase = shap_values[0, :, pred_idx]
    else:
        sv_clase = np.zeros(len(_FEATURES))

    abs_shap = np.abs(sv_clase)
    top_idx = np.argsort(abs_shap)[::-1][:3]
    total_abs = float(np.sum(abs_shap))
    if total_abs <= 1e-9:
        total_abs = 1.0

    factores = []
    for i in top_idx:
        if i >= len(_FEATURES) or abs_shap[i] < 1e-8:
            continue
        impacto_abs = float(abs_shap[i])
        impacto_signed = float(sv_clase[i])
        factores.append(
            {
                "nombre": _FEATURES[i],
                "descripcion": _desc_feature(_FEATURES[i]),
                "impacto": round(impacto_abs, 3),
                "impacto_signed": round(impacto_signed, 3),
                "impacto_rel_pct": round((impacto_abs / total_abs) * 100.0, 1),
                "direccion": "positivo" if impacto_signed > 0 else "negativo",
                "valor": round(float(features_array[0, i]), 3),
                "fuente": "shap",
            }
        )
    return factores


def _build_factors_fallback(X_scaled, features_array, clf):
    importances = getattr(clf, "feature_importances_", None)
    if importances is None:
        importances = np.ones(len(_FEATURES), dtype=float)

    importances = np.asarray(importances, dtype=float)
    if importances.shape[0] != len(_FEATURES):
        importances = np.ones(len(_FEATURES), dtype=float)

    contrib = importances * np.abs(X_scaled[0])
    abs_contrib = np.abs(contrib)
    total_abs = float(np.sum(abs_contrib))
    if total_abs <= 1e-9:
        total_abs = 1.0
    top_idx = np.argsort(np.abs(contrib))[::-1][:3]

    factores = []
    for i in top_idx:
        if i >= len(_FEATURES) or abs(float(contrib[i])) < 1e-8:
            continue
        impacto_abs = float(abs_contrib[i])
        impacto_signed = float(contrib[i] if float(X_scaled[0][i]) >= 0 else -contrib[i])
        factores.append(
            {
                "nombre": _FEATURES[i],
                "descripcion": _desc_feature(_FEATURES[i]),
                "impacto": round(impacto_abs, 3),
                "impacto_signed": round(impacto_signed, 3),
                "impacto_rel_pct": round((impacto_abs / total_abs) * 100.0, 1),
                "direccion": "positivo" if float(X_scaled[0][i]) >= 0 else "negativo",
                "valor": round(float(features_array[0, i]), 3),
                "fuente": "fallback",
            }
        )
    return factores


def _predecir(features_array):
    if _pipeline is None:
        return "vender", 0, []

    if hasattr(_pipeline, "named_steps"):
        scaler = _pipeline.named_steps.get("scaler")
        clf = _pipeline.named_steps.get("clf")
    else:
        scaler = None
        clf = _pipeline

    if clf is None:
        return "vender", 0, []

    X_scaled = scaler.transform(features_array) if scaler is not None else features_array

    probs = np.asarray(clf.predict_proba(X_scaled)[0], dtype=float)
    classes = list(getattr(clf, "classes_", []))

    idx_fichar = classes.index(1) if 1 in classes else min(1, len(probs) - 1)
    idx_vender = classes.index(0) if 0 in classes else 0

    prob_fichar = float(probs[idx_fichar]) if len(probs) > idx_fichar else 0.0
    prob_umbral = float(_thresholds.get("prob_fichar", 0.25))

    recomendacion = "fichar" if prob_fichar >= prob_umbral else "vender"
    confianza_prob = prob_fichar if recomendacion == "fichar" else (1.0 - prob_fichar)
    confianza = int(round(max(0.0, min(1.0, confianza_prob)) * 100))

    pred_idx = idx_fichar if recomendacion == "fichar" else idx_vender

    try:
        if _explainer is not None:
            factores = _build_factors_with_shap(X_scaled, features_array, pred_idx)
        else:
            factores = _build_factors_fallback(X_scaled, features_array, clf)
    except Exception:
        factores = _build_factors_fallback(X_scaled, features_array, clf)

    return recomendacion, confianza, factores


def _resumen_factores(factores):
    if not isinstance(factores, (list, tuple)) or not factores:
        return "Sin factores explicativos suficientes."

    frases = []
    for f in factores[:3]:
        desc = f.get("descripcion", f.get("nombre", "factor"))
        valor = f.get("valor", 0)
        frases.append(f"{desc}: {valor}.")
    return "\n• ".join(frases)


def _generar_veredicto_ml(
    jugador,
    recomendacion,
    confianza,
    factores,
    rendimiento,
    media_pos,
    vs_promedio,
    titulares_3,
    minutos_3,
):
    nombre = f"{jugador.nombre} {jugador.apellido}".strip()
    umbral_pts = float(_thresholds.get("puntos_fichar", 7.5))

    try:
        conf_pct = float(confianza)
    except Exception:
        conf_pct = 0.0
    conf_pct = max(0.0, min(100.0, conf_pct))

    prob_fichar_estimada = conf_pct / 100.0 if recomendacion == "fichar" else 1.0 - (conf_pct / 100.0)
    prob_fichar_estimada = max(0.0, min(1.0, prob_fichar_estimada))

    if recomendacion == "fichar":
        veredicto = "Fichalo. Proyecta buen rendimiento para la proxima jornada."
    else:
        veredicto = "Vendelo. Proyecta rendimiento bajo para la proxima jornada."

    criterio_txt = (
        f"La probabilidad estimada de superar {umbral_pts:.1f} puntos "
        f"es del {prob_fichar_estimada * 100:.1f}%."
    )

    if conf_pct > 0:
        veredicto += f" Confianza del modelo: {int(round(conf_pct))}%"

    base = (
        f"{nombre} promedia {rendimiento:.2f} pts esta temporada "
        f"y esta {vs_promedio:+.2f} frente a la media de su posicion, que es {media_pos:.2f}. "
        f"En los ultimos 3 partidos suma {minutos_3} minutos y {titulares_3}/3 titularidades."
    )

    factores_txt = _resumen_factores(factores)
    razon = f"{base} {criterio_txt}\n\nFactores clave:\n• {factores_txt}"
    return veredicto, razon


def _fallback_veredicto(jugador, rendimiento, media_pos, vs_promedio, titulares_3, minutos_3):
    nombre = f"{jugador.nombre} {jugador.apellido}".strip()
    umbral_pts = float(_thresholds.get("puntos_fichar", 7.5))
    recomendacion = "fichar" if rendimiento >= umbral_pts else "vender"

    if recomendacion == "fichar":
        return (
            recomendacion,
            "Fichalo. Proyecta buen rendimiento para la proxima jornada.",
            f"{nombre} supera el umbral de buen rendimiento. "
            f"Tiene {rendimiento:.1f} puntos frente al umbral de {umbral_pts:.1f}. "
            f"Ultimos 3 partidos: {titulares_3}/3 titularidades y {minutos_3} minutos.",
        )

    return (
        recomendacion,
        "Vendelo. Proyecta rendimiento bajo para la proxima jornada.",
        f"No alcanza el umbral de buen rendimiento. "
        f"Tiene {rendimiento:.1f} puntos frente al umbral de {umbral_pts:.1f}. "
        f"Ademas, esta {vs_promedio:+.1f} frente a la media de su posicion, que es {media_pos:.1f}.",
    )


def _proxima_jornada(temporada, stats_temporada) -> int | None:
    max_jornada = (
        Jornada.objects.filter(temporada=temporada).aggregate(max_num=Max("numero_jornada"))["max_num"]
        or None
    )
    ultima_jugada = None
    if stats_temporada:
        try:
            ultima_jugada = int(stats_temporada[0].partido.jornada.numero_jornada)
        except Exception:
            ultima_jugada = None

    if max_jornada is None and ultima_jugada is None:
        return None
    if ultima_jugada is None:
        return int(max_jornada)
    if max_jornada is None:
        return int(ultima_jugada + 1)
    return int(min(ultima_jugada + 1, max_jornada))


def analizar_consejero(jugador_id, accion_solicitada: str = "") -> dict:
    if not jugador_id:
        raise ConsejeroValidationError("Falta parametro obligatorio: jugador_id")

    if accion_solicitada and accion_solicitada not in {"fichar", "vender"}:
        raise ConsejeroValidationError("Accion invalida. Opciones: fichar, vender")

    try:
        jugador = Jugador.objects.get(id=jugador_id)
    except Jugador.DoesNotExist as exc:
        raise ConsejeroNotFoundError("Jugador no encontrado") from exc

    temporada = _resolver_temporada()
    if not temporada:
        raise ConsejeroServiceError("Temporada no disponible")

    stats_temporada = list(
        EstadisticasPartidoJugador.objects.filter(
            jugador=jugador,
            partido__jornada__temporada=temporada,
        )
        .select_related("partido", "partido__jornada")
        .order_by("-partido__jornada__numero_jornada")
    )

    posicion = jugador.get_posicion_mas_frecuente() or "Delantero"
    rendimiento = _mean_attr(stats_temporada, "puntos_fantasy", default=0.0)
    ultimos3 = stats_temporada[:3]
    titulares_3 = sum(1 for p in ultimos3 if p.titular)
    minutos_3 = int(sum((p.min_partido or 0) for p in ultimos3))

    media_pos = _obtener_media_posicion(posicion, temporada)
    vs_promedio = float(rendimiento - media_pos)
    jornada_objetivo = _proxima_jornada(temporada, stats_temporada)

    modelo_ok = _cargar_modelo()
    if modelo_ok:
        features = _computar_features(stats_temporada, jugador, posicion, rendimiento, media_pos, temporada)
        recomendacion, confianza, factores = _predecir(features)
        veredicto, razon = _generar_veredicto_ml(
            jugador,
            recomendacion,
            confianza,
            factores,
            rendimiento,
            media_pos,
            vs_promedio,
            titulares_3,
            minutos_3,
        )
    else:
        confianza = 0
        factores = []
        recomendacion, veredicto, razon = _fallback_veredicto(
            jugador,
            rendimiento,
            media_pos,
            vs_promedio,
            titulares_3,
            minutos_3,
        )

    return {
        "veredicto": veredicto,
        "razon": razon,
        "rendimiento": f"{rendimiento:.2f}",
        "vs_promedio": round(vs_promedio, 2),
        "titulares_3": titulares_3,
        "minutos_3": minutos_3,
        "accion": recomendacion,
        "accion_solicitada": accion_solicitada or None,
        "recomendacion": recomendacion,
        "confianza": confianza,
        "factores": factores,
        "fuente_explicacion": (factores[0].get("fuente") if factores else "heuristica"),
        "criterio_fichaje_puntos": float(_thresholds.get("puntos_fichar", 7.5)),
        "criterio_fichaje_prob": float(_thresholds.get("prob_fichar", 0.25)),
        "temporada": temporada.nombre,
        "proxima_jornada": jornada_objetivo,
    }
