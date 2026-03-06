"""
DRF API views – Consejero (Advisor)
Endpoints:
  POST /api/consejero/

El análisis utiliza un RandomForestClassifier entrenado sobre datos históricos
de La Liga para predecir si un jugador rendirá bien en los próximos 3 partidos
(fichar → seguir) o mal (vender → prescindir).  Los motivos se generan con
valores SHAP sobre las features del jugador en tiempo real.
"""
import json
import logging
import numpy as np
from pathlib import Path

try:
    import joblib
    import shap as _shap
except ImportError:
    joblib = None
    _shap = None

from django.db.models import Avg
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models import (
    Jugador, EstadisticasPartidoJugador, EquipoJugadorTemporada,
    Temporada,
)

logger = logging.getLogger(__name__)

# ─── Rutas a los artefactos del modelo ────────────────────────────────────────
_BASE = Path(__file__).resolve().parents[2] / "csv" / "csvGenerados" / "entrenamiento" / "consejero"

_pipeline        = None   # cargado con lazy-loading
_pos_avgs        = None
_explainer       = None

_POSICION_ENC = {"PT": 0, "DF": 1, "MC": 2, "DT": 3}
_LABEL_MAP    = {0: "vender", 1: "mantener", 2: "fichar"}
_FEATURES     = ["pf_last3", "pf_last5", "min_last3", "starter_rate3",
                 "form_trend", "vs_pos_avg", "posicion_enc"]

_FEATURE_DESC = {
    "pf_last3":      "media de puntos (últ. 3 partidos)",
    "pf_last5":      "media de puntos (últ. 5 partidos)",
    "min_last3":     "minutos por partido (últ. 3 jornadas)",
    "starter_rate3": "ratio de titularidades (últ. 3 jornadas)",
    "form_trend":    "tendencia de forma (momentum)",
    "vs_pos_avg":    "diferencia con la media de su posición",
    "posicion_enc":  "posición en el campo",
}


def _cargar_modelo():
    """Carga el pipeline y el explainer SHAP una sola vez."""
    global _pipeline, _pos_avgs, _explainer
    if _pipeline is not None:
        return True
    try:
        if joblib is None or _shap is None:
            raise ImportError("joblib or shap not available")
        _pipeline = joblib.load(_BASE / "modelo_consejero.pkl")
        with open(_BASE / "pos_avgs.json") as f:
            _pos_avgs = json.load(f)
        _explainer = _shap.TreeExplainer(_pipeline.named_steps["clf"])
        return True
    except Exception as e:
        logger.error(f"No se pudo cargar el modelo Consejero: {e}")
        return False


class ConsejeroView(APIView):
    """POST /api/consejero/ – Analizar jugador para fichar/vender/mantener usando ML"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            jugador_id = request.data.get('jugador_id')
            accion = request.data.get('accion')  # 'fichar', 'vender', 'mantener'

            if not jugador_id or not accion:
                return Response(
                    {'error': 'Faltan parámetros: jugador_id, accion'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                jugador = Jugador.objects.get(id=jugador_id)
            except Jugador.DoesNotExist:
                return Response({'error': 'Jugador no encontrado'}, status=status.HTTP_404_NOT_FOUND)

            temporada = (
                Temporada.objects.filter(nombre='25_26').first()
                or Temporada.objects.order_by('-nombre').first()
            )
            if not temporada:
                return Response({'error': 'Temporada no disponible'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Todas las estadísticas de la temporada, ordenadas de más reciente a más antigua
            stats_temporada = list(
                EstadisticasPartidoJugador.objects.filter(
                    jugador=jugador,
                    partido__jornada__temporada=temporada,
                ).order_by('-partido__jornada__numero_jornada')
            )

            # Métricas básicas para el frontend
            posicion = jugador.get_posicion_mas_frecuente() or 'DT'
            rendimiento = (
                sum(p.puntos_fantasy or 0 for p in stats_temporada) / len(stats_temporada)
                if stats_temporada else 0
            )
            ultimos3 = stats_temporada[:3]
            titulares_3 = sum(1 for p in ultimos3 if p.titular)
            minutos_3   = sum(p.min_partido or 0 for p in ultimos3)

            media_pos   = _obtener_media_posicion(posicion, temporada)
            vs_promedio = rendimiento - media_pos

            # ── Inferencia con el modelo ML ──────────────────────────────────
            modelo_ok = _cargar_modelo()
            if modelo_ok:
                features   = _computar_features(stats_temporada, posicion, rendimiento, media_pos, temporada)
                recomendacion, confianza, factores = _predecir(features)
                veredicto, razon = _generar_veredicto_ml(
                    jugador, accion, recomendacion, confianza, factores,
                    rendimiento, media_pos, vs_promedio, titulares_3, minutos_3,
                )
            else:
                # Fallback si el modelo no carga
                recomendacion = 'mantener'
                confianza     = 0
                factores      = []
                veredicto, razon = _fallback_veredicto(
                    jugador, accion, rendimiento, media_pos, vs_promedio, titulares_3, minutos_3
                )

            return Response({
                'veredicto':     veredicto,
                'razon':         razon,
                'rendimiento':   f'{rendimiento:.2f}',
                'vs_promedio':   round(vs_promedio, 2),
                'titulares_3':   titulares_3,
                'minutos_3':     minutos_3,
                'accion':        accion,
                'recomendacion': recomendacion,
                'confianza':     confianza,
                'factores':      factores,
            })

        except Exception as e:
            logger.exception(f'ConsejeroView error: {e}')
            return Response(
                {'error': f'Error al analizar jugador: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ─── helpers ─────────────────────────────────────────────────────────────────

def _obtener_media_posicion(posicion, temporada):
    return (
        EstadisticasPartidoJugador.objects.filter(
            partido__jornada__temporada=temporada,
            posicion=posicion,
        ).aggregate(Avg('puntos_fantasy'))['puntos_fantasy__avg'] or 0
    )


def _computar_features(stats_temporada, posicion, rendimiento_full, media_pos, temporada):
    """
    Construye el vector de features compatible con el modelo entrenado.
    Features: pf_last3, pf_last5, min_last3, starter_rate3, form_trend, vs_pos_avg, posicion_enc
    stats_temporada está ordenado de más reciente a más antiguo.
    """
    def _mean(objs, attr, default=0.0):
        vals = [getattr(o, attr) or 0 for o in objs]
        return float(np.mean(vals)) if vals else default

    last3 = stats_temporada[:3]
    last5 = stats_temporada[:5]

    pf_last3      = _mean(last3, 'puntos_fantasy')
    pf_last5      = _mean(last5, 'puntos_fantasy')
    min_last3     = _mean(last3, 'min_partido')
    starter_rate3 = float(sum(1 for p in last3 if p.titular) / max(len(last3), 1))
    form_trend    = pf_last3 - pf_last5

    # vs_pos_avg: pf_last3 comparado con la media de posición de toda la temporada
    # Intentamos usar pos_avgs.json si el modelo está cargado; si no, usamos media_pos de la BD
    vs_pos_avg = pf_last3 - media_pos

    posicion_enc = float(_POSICION_ENC.get(posicion.upper(), 3))

    return np.array([[pf_last3, pf_last5, min_last3, starter_rate3,
                      form_trend, vs_pos_avg, posicion_enc]], dtype=float)


def _predecir(features_array):
    """
    Aplica el pipeline (scaler + RF) y calcula SHAP para un único jugador.
    Devuelve (recomendacion: str, confianza: int, factores: list[dict]).
    """
    scaler    = _pipeline.named_steps["scaler"]
    clf       = _pipeline.named_steps["clf"]
    X_scaled  = scaler.transform(features_array)

    probs         = clf.predict_proba(X_scaled)[0]   # [p_vender, p_mantener, p_fichar]
    pred_idx      = int(np.argmax(probs))
    recomendacion = _LABEL_MAP[pred_idx]
    confianza     = int(round(probs[pred_idx] * 100))

    # SHAP values para esta instancia
    shap_values = _explainer.shap_values(X_scaled)   # lista o array 3D

    # Extraer array (n_features,) para la clase predicha
    if isinstance(shap_values, list):
        sv_clase = shap_values[pred_idx][0]            # (n_features,)
    elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        sv_clase = shap_values[0, :, pred_idx]
    else:
        sv_clase = np.zeros(len(_FEATURES))

    # Top 3 features por magnitud de impacto
    abs_shap = np.abs(sv_clase)
    top_idx  = np.argsort(abs_shap)[::-1][:3]
    factores = []
    for i in top_idx:
        if abs_shap[i] < 1e-6:
            continue
        factores.append({
            "nombre":      _FEATURES[i],
            "descripcion": _FEATURE_DESC[_FEATURES[i]],
            "impacto":     round(float(abs_shap[i]), 3),
            "direccion":   "positivo" if sv_clase[i] > 0 else "negativo",
            "valor":       round(float(features_array[0, i]), 2),
        })

    return recomendacion, confianza, factores


_ACCION_LABEL = {"fichar": "fichar", "vender": "vender", "mantener": "mantener"}


def _generar_veredicto_ml(jugador, accion, recomendacion, confianza, factores,
                           rendimiento, media_pos, vs_promedio, titulares_3, minutos_3):
    """
    Genera el texto del veredicto y la razón, integrando la recomendación del modelo
    y los factores SHAP con el contexto de la acción elegida por el usuario.
    """
    nombre     = f"{jugador.nombre} {jugador.apellido}"
    coincide   = (accion == recomendacion)

    # ── FICHAR ────────────────────────────────────────────────────────────────
    if accion == 'fichar':
        if recomendacion == 'fichar':
            veredicto = f"Sí, fíchalo. El modelo lo recomienda con un {confianza}% de confianza."
            razon     = (
                f"El análisis sobre datos históricos de La Liga indica que {nombre} tiene buenas "
                f"perspectivas. Su media esta temporada es {rendimiento:.1f} pts "
                f"({vs_promedio:+.1f} vs media de su posición, {media_pos:.1f} pts), "
                f"con {titulares_3}/3 titularidades recientes."
            )
        elif recomendacion == 'mantener':
            veredicto = f"Con matices. El modelo lo situaría en «mantener» ({confianza}% confianza)."
            razon     = (
                f"No es un fichaje evidente pero tampoco es mala opción. Su media es {rendimiento:.1f} pts "
                f"({vs_promedio:+.1f} vs su posición). Ha sido titular {titulares_3}/3 partidos recientes."
            )
        else:  # recomendacion == 'vender'
            veredicto = f"El modelo no lo recomienda ahora ({confianza}% confianza en «no fichar»)."
            razon     = (
                f"Los datos apuntan a poca continuidad o bajo rendimiento. Media: {rendimiento:.1f} pts "
                f"({vs_promedio:+.1f} vs posición), {titulares_3}/3 titularidades recientes y "
                f"{minutos_3} minutos en los últimos 3 partidos."
            )

    # ── VENDER ────────────────────────────────────────────────────────────────
    elif accion == 'vender':
        if recomendacion == 'vender':
            veredicto = f"Sí, véndelo. El modelo confirma que la situación no mejora ({confianza}% confianza)."
            razon     = (
                f"El análisis respalda la venta: {nombre} lleva {minutos_3} minutos en los últimos 3 partidos, "
                f"ha sido titular solo {titulares_3}/3 veces y su media ({rendimiento:.1f} pts) está "
                f"{abs(vs_promedio):.1f} pts por debajo de la media de su posición."
            )
        elif recomendacion == 'mantener':
            veredicto = f"El modelo no lo vendería ahora. Rendimiento en la media ({confianza}% confianza)."
            razon     = (
                f"Aunque no es una estrella, {nombre} rinde dentro de la media de su posición "
                f"({rendimiento:.1f} pts, {vs_promedio:+.1f}), con {titulares_3}/3 titularidades recientes. "
                f"El modelo ve más valor en mantenerlo que en venderlo ahora."
            )
        else:  # recomendacion == 'fichar'
            veredicto = f"El modelo recomienda lo contrario: está en buena forma ({confianza}% confianza)."
            razon     = (
                f"Los datos apuntan a que {nombre} está rindiendo bien. Media: {rendimiento:.1f} pts "
                f"({vs_promedio:+.1f} vs posición), {titulares_3}/3 titularidades recientes y "
                f"{minutos_3} minutos en los últimos 3 partidos. Venderlo ahora podría ser un error."
            )

    # ── MANTENER ──────────────────────────────────────────────────────────────
    elif accion == 'mantener':
        if recomendacion == 'mantener':
            veredicto = f"Sí, mantenlo. El modelo también lo recomienda ({confianza}% confianza)."
            razon     = (
                f"{nombre} rinde de forma consistente: media {rendimiento:.1f} pts "
                f"({vs_promedio:+.1f} vs posición), {titulares_3}/3 titularidades recientes. "
                f"Es una pieza funcional en la plantilla."
            )
        elif recomendacion == 'fichar':
            veredicto = f"Mantenlo, está en buena forma. El modelo incluso lo recomendaría para fichar ({confianza}% confianza)."
            razon     = (
                f"El análisis ve tendencia positiva: media {rendimiento:.1f} pts "
                f"({vs_promedio:+.1f} vs posición), {titulares_3}/3 titularidades recientes. "
                f"Si lo tienes, no lo sueltes."
            )
        else:  # recomendacion == 'vender'
            veredicto = f"El modelo sugiere que no es la mejor opción a largo plazo ({confianza}% confianza en «vender»)."
            razon     = (
                f"El rendimiento de {nombre} está por debajo de lo esperado para su posición: "
                f"media {rendimiento:.1f} pts ({vs_promedio:+.1f}), {titulares_3}/3 titularidades y "
                f"{minutos_3} minutos en los últimos 3 partidos. Si tienes alternativas, merece la pena valorarlas."
            )

    else:
        veredicto = "Análisis no disponible."
        razon     = "Acción no reconocida."

    return veredicto, razon


def _fallback_veredicto(jugador, accion, rendimiento, media_pos, vs_promedio, titulares_3, minutos_3):
    """Veredicto simple por reglas cuando el modelo no está disponible."""
    nombre = f"{jugador.nombre} {jugador.apellido}"
    por_encima = rendimiento > media_pos
    titular_ok = titulares_3 >= 2

    if accion == 'fichar':
        if por_encima and titular_ok:
            return (f"Sí, fíchalo. Rinde por encima de la media de su posición.",
                    f"Media {rendimiento:.1f} pts vs {media_pos:.1f} pts de su posición, {titulares_3}/3 titularidades.")
        else:
            return (f"No lo recomendaría ahora.",
                    f"Media {rendimiento:.1f} pts vs {media_pos:.1f} pts, solo {titulares_3}/3 titularidades.")
    elif accion == 'vender':
        if not por_encima and minutos_3 < 150:
            return (f"Sí, véndelo.",
                    f"{minutos_3} minutos en los últimos 3 partidos y rinde {abs(vs_promedio):.1f} pts por debajo de la media.")
        else:
            return (f"No lo vendería ahora.",
                    f"Rinde en la media ({rendimiento:.1f} pts) con {titulares_3}/3 titularidades.")
    else:
        if por_encima:
            return (f"Sí, mantenlo. Rinde por encima de la media.",
                    f"Media {rendimiento:.1f} pts ({vs_promedio:+.1f} vs posición).")
        else:
            return (f"Te recomendaría buscar alternativas.",
                    f"Media {rendimiento:.1f} pts ({vs_promedio:+.1f} vs posición), {titulares_3}/3 titularidades.")

