"""
AI Insight endpoint: genera frases dinámicas sobre un jugador
basadas en sus estadísticas reales.

GET /api/jugador-insight/?jugador_id=123&temporada=25/26
"""
from dataclasses import dataclass, field
from typing import Callable

from django.db.models import Sum, Avg, Count, Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Jugador, Temporada, EquipoJugadorTemporada,
    EstadisticasPartidoJugador,
)


# ── Sistema de frases ─────────────────────────────────────────────────────────

@dataclass
class Frase:
    plantilla: str
    condicion: Callable[[dict], float]
    tipo: str  # e.g., 'xg_ataque', 'asistencias', 'motor', 'forma', 'tarjetas', 'minutos', etc.
    prioridad: int = 1  # 1 = más importante del tipo (se ordena descendente)
    pesos: dict = field(default_factory=lambda: {
        "Delantero": 1.0, "Centrocampista": 1.0,
        "Defensa": 1.0, "Portero": 1.0,
    })
    es_comun: bool = False  # Frases que aparecen en todas posiciones (forma, tarjetas, minutos)

    def render(self, stats: dict) -> str:
        try:
            return self.plantilla.format(**stats)
        except (KeyError, ValueError):
            return self.plantilla


def _xg_ratio(s):
    xg = s.get("xg", 0)
    goles = s.get("goles", 0)
    return goles / max(xg, 0.1)


def _pct_duelos(s):
    tot = s.get("duelos_totales", 0)
    if tot < 5:
        return 0.0
    return s.get("duelos_ganados", 0) / tot


def _pct_duelos_aereos(s):
    tot = s.get("duelos_aereos_totales", 0)
    if tot < 5:
        return 0.0
    return s.get("duelos_aereos_ganados", 0) / tot


FRASES: list[Frase] = [
    # XG Ataque (prioridad 1)
    Frase(
        "Está marcando por encima de la estadística {goles} goles con {xg:.1f} xG.",
        lambda s: max(0.0, _xg_ratio(s) - 1.10) if abs(s.get("goles", 0) - s.get("xg", 0)) >= 1 else 0.0,
        tipo="xg_ataque", prioridad=1,
        pesos={"Delantero": 2.0, "Centrocampista": 1.2, "Defensa": 0.2, "Portero": 0.0},
    ),
    # XG Ataque (prioridad 2)
    Frase(
        "Marcando por debajo: esperados {xg:.1f} xG, solo {goles} goles.",
        lambda s: max(0.0, 1.0 - _xg_ratio(s)) if s.get("xg", 0) > 1.5 and abs(s.get("goles", 0) - s.get("xg", 0)) >= 1 else 0.0,
        tipo="xg_ataque", prioridad=2,
        pesos={"Delantero": 2.0, "Centrocampista": 1.2, "Defensa": 0.2, "Portero": 0.0},
    ),

    # Asistencias (prioridad 1)
    Frase(
        "Ha asistido por encima de lo esperado: {asistencias} asistencias con {xag:.1f} xAG.",
        lambda s: (s.get("asistencias", 0) / 12) if s.get("asistencias", 0) > s.get("xag", 0) and abs(s.get("asistencias", 0) - s.get("xag", 0)) >= 1 else 0.0,
        tipo="asistencias", prioridad=1,
        pesos={"Delantero": 1.8, "Centrocampista": 2.0, "Defensa": 0.8, "Portero": 0.0},
    ),
    # Asistencias (prioridad 2)
    Frase(
        "Genera oportunidades pero sus compañeros no convierten: {xag:.1f} xAG esperadas, solo {asistencias} asistencias.",
        lambda s: (s.get("xag", 0) / 15) if s.get("asistencias", 0) < s.get("xag", 0) and abs(s.get("asistencias", 0) - s.get("xag", 0)) >= 1 else 0.0,
        tipo="asistencias", prioridad=2,
        pesos={"Delantero": 1.8, "Centrocampista": 2.0, "Defensa": 0.8, "Portero": 0.0},
    ),

    # Ritmo Ofensivo
    Frase(
        "Todo un goleador, {goles} goles en {partidos} partidos.",
        lambda s: ((s.get("goles", 0) / max(s.get("partidos", 1), 1)) / 1.5) if s.get("goles", 0) >= 3 and abs(s.get("goles", 0) - s.get("xg", 0)) < 1 else 0.0,
        tipo="ritmo_ataque", prioridad=1,
        pesos={"Delantero": 2.0, "Centrocampista": 1.0, "Defensa": 0.1, "Portero": 0.0},
    ),

    # Temporada (prioridad 1)
    Frase(
        "Temporada sobresaliente: {goles} goles, {asistencias} asistencias y {promedio_puntos:.1f} pts/partido.",
        lambda s, posicion=None: (1.0 if (s.get("goles", 0) + s.get("asistencias", 0)) >= 11 else 0.0) if posicion == "Delantero" else (1.0 if (s.get("goles", 0) + s.get("asistencias", 0)) >= 5 else 0.0) if posicion == "Centrocampista" else (1.0 if (s.get("goles", 0) + s.get("asistencias", 0)) >= 3 else 0.0) if posicion == "Defensa" else 0.0,
        tipo="temporada", prioridad=1,
        pesos={"Delantero": 2.0, "Centrocampista": 1.8, "Defensa": 1.0, "Portero": 0.5},
    ),
    # Temporada (prioridad 2)
    Frase(
        "Temporada discreta: {promedio_puntos:.1f} pts media.",
        lambda s: 1.0 if 0 < s.get("promedio_puntos", 10) < 3 and s.get("partidos", 0) >= 5 else 0.0,
        tipo="temporada", prioridad=2,
        pesos={"Delantero": 1.0, "Centrocampista": 1.0, "Defensa": 1.0, "Portero": 1.0},
    ),

    # Regates
    Frase(
        "¡Imparable! {regates_completados} regates completados y {conducciones_progresivas} progresivas.",
        lambda s: (s.get("regates_completados", 0) / 40) if s.get("regates_completados", 0) >= 10 and s.get("conducciones_progresivas", 0) >= 20 else 0.0,
        tipo="regates", prioridad=1,
        pesos={"Delantero": 1.8, "Centrocampista": 1.5, "Defensa": 0.5, "Portero": 0.0},
    ),

    # Duelos (prioridad 1)
    Frase(
        "¡Todo un guerrero! {pct_duelos:.0f}% duelos ganados ({duelos_ganados}/{duelos_totales}).",
        lambda s: 1.0 if _pct_duelos(s) >= 0.6 and s.get("duelos_totales", 0) >= 5 else 0.0,
        tipo="duelos", prioridad=1,
        pesos={"Delantero": 0.5, "Centrocampista": 1.2, "Defensa": 2.0, "Portero": 0.5},
    ),
    # Duelos aéreos (prioridad 2)
    Frase(
        "¡Imbatible por arriba!: {pct_duelos_aereos:.0f}% duelos aéreos ganados ({duelos_aereos_ganados}/{duelos_aereos_totales}).",
        lambda s: 1.0 if _pct_duelos_aereos(s) >= 0.6 and s.get("duelos_aereos_totales", 0) >= 20 else 0.0,
        tipo="duelos", prioridad=2,
        pesos={"Delantero": 0.5, "Centrocampista": 0.8, "Defensa": 2.0, "Portero": 0.8},
    ),

    # Defensa pasiva (prioridad 1)
    Frase(
        "Líder desde atrás: {despejes} despejes y {entradas} entradas.",
        lambda s: 1.0 if s.get("despejes", 0) >= 10 and s.get("entradas", 0) >= 10 else 0.0,
        tipo="defensa_pasiva", prioridad=1,
        pesos={"Delantero": 0.1, "Centrocampista": 0.8, "Defensa": 2.0, "Portero": 0.5},
    ),
    

    # Portero paradas
    Frase(
        "¡Todo un seguro bajo palos! {porcentaje_paradas:.0f}% paradas.",
        lambda s: s.get("porcentaje_paradas", 0) / 100 if s.get("porcentaje_paradas", 0) > 65 else 0.0,
        tipo="portero_paradas", prioridad=2,
        pesos={"Delantero": 0.0, "Centrocampista": 0.0, "Defensa": 0.2, "Portero": 2.0},
    ),

    # Portero fiable
    Frase(
        "Muy fiable, {goles_en_contra} goles en {tiros_contra} tiros enfrentados.",
        lambda s: max(0.0, 1.0 - (s.get("goles_en_contra", 10) / max(s.get("partidos", 1) * 1.5, 1))) 
                  if s.get("tiros_contra", 0) > 0 else 0.0,
        tipo="portero_fiable", prioridad=2,
        pesos={"Delantero": 0.0, "Centrocampista": 0.0, "Defensa": 0.3, "Portero": 2.0},
    ),

    # Portero élite
    Frase(
        "Portero élite: {goles_en_contra} goles encajados y {psxg_total:.1f} goles esperados, ¡ha evitado {sobrepasos:.1f} goles!",
        lambda s: max(0.0, (s.get("psxg_total", 0) - s.get("goles_en_contra", 0)) / max(s.get("psxg_total", 1), 1)) if abs(s.get("psxg_total", 0) - s.get("goles_en_contra", 0)) >= 1 else 0.0,
        tipo="portero_elite", prioridad=1,
        pesos={"Delantero": 0.0, "Centrocampista": 0.0, "Defensa": 0.5, "Portero": 2.0},
    ),

    # ─── FRASES COMUNES (Forma, Tarjetas, Minutos) ──────────────────────────

    Frase(
        "Muy en forma, {promedio_puntos:.1f} pts de media en temporada.",
        lambda s: 1.0 if s.get("promedio_puntos", 0) >= 4.5 else 0.0,
        tipo="forma", prioridad=1,
        pesos={"Delantero": 1.5, "Centrocampista": 1.5, "Defensa": 1.5, "Portero": 1.5},
        es_comun=True,
    ),

    Frase(
        "¡Cuidado! {amarillas} amarillas, está apercibido.",
        lambda s: 1.0 if s.get("amarillas", 0) in [4, 9, 14, 19] else 0.0,
        tipo="tarjetas", prioridad=1,
        pesos={"Delantero": 1.5, "Centrocampista": 1.5, "Defensa": 1.5, "Portero": 1.0},
        es_comun=True,
    ),

    Frase(
        "Fijo en las alineaciones, ha jugado {minutos} minutos.",
        lambda s: min(1.0, s.get("minutos", 0) / 2700) if s.get("partidos", 0) >= 10 else 0.0,
        tipo="minutos", prioridad=1,
        pesos={"Delantero": 1.0, "Centrocampista": 1.8, "Defensa": 2.0, "Portero": 2.0},
        es_comun=True,
    ),

    Frase(
        "Pasador fiable, {pases_totales} pases con un {pases_accuracy:.0f}% de acierto.",
        lambda s: 1.0 if s.get("pases_accuracy", 0) >= 85 and s.get("pases_totales", 0) >= 100 else 0.0,
        tipo="control", prioridad=1,
        pesos={"Delantero": 0.5, "Centrocampista": 2.0, "Defensa": 1.2, "Portero": 0.3},
    ),
]

# Prioridades de frases por posición (menor número = mayor prioridad)
PRIORIDADES_POR_POSICION = {
    "Delantero": {
        "xg_ataque": 1,
        "tarjetas": 2,
        "ritmo_ataque": 3,
        "asistencias": 4,
        "regates": 5,
        "temporada": 6,
        "minutos": 7,
        "forma": 8,
    },
    "Centrocampista": {
        "asistencias": 1,
        "tarjetas": 2,
        "control": 3,
        "regates": 4,
        "duelos": 5,
        "minutos": 6,
        "ritmo_ataque": 7,
    },
    "Defensa": {
        "tarjetas": 1,
        "defensa_pasiva": 2,
        "duelos": 3,
        "control": 4,
        "forma": 5,
        "minutos": 6,
    },
    "Portero": {
        "tarjetas": 1,
        "portero_elite": 2,
        "portero_fiable": 3,
        "portero_paradas": 4,
        "forma": 5,
        "minutos": 6,
    },
}


def get_insights(stats: dict, posicion: str, n: int = 3) -> list:
    """Devuelve max N frases sin duplicar tipos. Defensa puede tener 2 de defensa/duelos."""
    comunes = []
    tipo_especificas = []

    for frase in FRASES:
        try:
            # Pasar posicion a la condición si la aceptas
            try:
                score_base = frase.condicion(stats, posicion)
            except TypeError:
                score_base = frase.condicion(stats)
            peso = frase.pesos.get(posicion, 1.0)
            score_final = score_base * peso
            if score_final > 0.05:
                if frase.es_comun:
                    comunes.append((frase, score_final))
                else:
                    tipo_especificas.append((frase, score_final))
        except Exception:
            continue

    # Agrupar especificas por tipo y ordenar
    por_tipo = {}
    for frase, score in tipo_especificas:
        if frase.tipo not in por_tipo:
            por_tipo[frase.tipo] = []
        por_tipo[frase.tipo].append((frase, score))

    seleccionadas = []
    for tipo, items in por_tipo.items():
        items.sort(key=lambda x: (-x[0].prioridad, -x[1]))
        seleccionadas.extend(items[:2])  # Máx 2 por tipo a nivel interno

    # Agrupar comunes por tipo
    comunes_por_tipo = {}
    for frase, score in comunes:
        if frase.tipo not in comunes_por_tipo:
            comunes_por_tipo[frase.tipo] = []
        comunes_por_tipo[frase.tipo].append((frase, score))

    for tipo, items in comunes_por_tipo.items():
        items.sort(key=lambda x: (-x[0].prioridad, -x[1]))
        seleccionadas.extend(items[:2])  # Máx 2 por tipo comunes

    # Ordenar por prioridad de posición y score
    prioridades_pos = PRIORIDADES_POR_POSICION.get(posicion, {})
    seleccionadas.sort(key=lambda x: (prioridades_pos.get(x[0].tipo, 999), -x[1]))
    
    # Iterar y seleccionar sin duplicar tipos (excepto Defensa con defensa_pasiva/duelos)
    tipos_usados = {}  # {tipo: count}
    top_n = []
    
    for frase, score in seleccionadas:
        tipo = frase.tipo
        count_tipo = tipos_usados.get(tipo, 0)
        
        # Si temporada está seleccionado, no agregar forma
        if "temporada" in tipos_usados and tipo == "forma":
            continue
        
        # Defensa puede tener 2 de defensa/duelos, otros max 1
        max_mismo_tipo = 2 if (posicion == "Defensa" and tipo in ["defensa_pasiva", "duelos"]) else 1
        
        if count_tipo < max_mismo_tipo:
            top_n.append((frase, score))
            tipos_usados[tipo] = count_tipo + 1
            
            if len(top_n) >= n:
                break
    
    insights_list = []
    for frase, score in top_n:
        texto = frase.render(stats)
        insights_list.append({"texto": texto, "score": round(score, 3)})
    
    return insights_list


# ── Vista ─────────────────────────────────────────────────────────────────────

class JugadorInsightView(APIView):
    """GET /api/jugador-insight/?jugador_id=123&temporada=25/26"""
    permission_classes = [AllowAny]

    def get(self, request):
        jugador_id = request.GET.get("jugador_id")
        temporada_display = request.GET.get("temporada", "25/26")
        numero_jornada_param = request.GET.get("jornada", None)  # Nuevo parámetro

        if not jugador_id:
            return Response({"insights": []})

        try:
            jugador = Jugador.objects.get(id=jugador_id)
        except Jugador.DoesNotExist:
            return Response({"insights": []})

        temporada_nombre = temporada_display.replace("/", "_")
        temporada = None
        try:
            temporada = Temporada.objects.get(nombre=temporada_nombre)
        except Temporada.DoesNotExist:
            temporada = Temporada.objects.order_by("-nombre").first()

        posicion = jugador.get_posicion_mas_frecuente() or "Centrocampista"

        filter_q = Q(jugador=jugador)
        if temporada:
            filter_q &= Q(partido__jornada__temporada=temporada)
        
        # Filtrar por jornada si se proporciona
        numero_jornada_actual = None
        if numero_jornada_param:
            try:
                numero_jornada_actual = int(numero_jornada_param)
                filter_q &= Q(partido__jornada__numero_jornada__lte=numero_jornada_actual)
            except (ValueError, TypeError):
                pass

        agg = (
            EstadisticasPartidoJugador.objects
            .filter(filter_q)
            .exclude(puntos_fantasy__gt=40)
            .aggregate(
                goles=Sum("gol_partido"),
                asistencias=Sum("asist_partido"),
                minutos=Sum("min_partido"),
                partidos=Count("id", filter=Q(min_partido__gt=0)),
                promedio_puntos=Avg("puntos_fantasy"),
                pases_totales=Sum("pases_totales"),
                pases_accuracy=Avg("pases_completados_pct"),
                xag=Sum("xag"),
                regates_completados=Sum("regates_completados"),
                conducciones_progresivas=Sum("conducciones_progresivas"),
                despejes=Sum("despejes"),
                entradas=Sum("entradas"),
                duelos_ganados=Sum("duelos_ganados"),
                duelos_perdidos=Sum("duelos_perdidos"),
                duelos_aereos_ganados=Sum("duelos_aereos_ganados"),
                duelos_aereos_perdidos=Sum("duelos_aereos_perdidos"),
                amarillas=Sum("amarillas"),
                xg=Sum("xg_partido"),
                goles_en_contra=Sum("goles_en_contra"),
                porcentaje_paradas=Avg("porcentaje_paradas"),
                tiros_contra=Sum("tiros"),
                psxg_total=Sum("psxg"),
            )
        )



        duelos_totales = (agg.get("duelos_ganados") or 0) + (agg.get("duelos_perdidos") or 0)
        duelos_aereos_totales = (agg.get("duelos_aereos_ganados") or 0) + (agg.get("duelos_aereos_perdidos") or 0)

        pct_duelos = 0.0
        if duelos_totales >= 5:
            pct_duelos = (agg.get("duelos_ganados") or 0) / duelos_totales * 100

        pct_duelos_aereos = 0.0
        if duelos_aereos_totales >= 5:
            pct_duelos_aereos = (agg.get("duelos_aereos_ganados") or 0) / duelos_aereos_totales * 100

        stats = {
            "goles": agg.get("goles") or 0,
            "asistencias": agg.get("asistencias") or 0,
            "minutos": agg.get("minutos") or 0,
            "partidos": agg.get("partidos") or 0,
            "promedio_puntos": round(agg.get("promedio_puntos") or 0, 1),
            "pases_totales": agg.get("pases_totales") or 0,
            "pases_accuracy": round(agg.get("pases_accuracy") or 0, 1),
            "xag": round(agg.get("xag") or 0, 2),
            "regates_completados": agg.get("regates_completados") or 0,
            "conducciones_progresivas": agg.get("conducciones_progresivas") or 0,
            "despejes": agg.get("despejes") or 0,
            "entradas": agg.get("entradas") or 0,
            "duelos_ganados": agg.get("duelos_ganados") or 0,
            "duelos_perdidos": agg.get("duelos_perdidos") or 0,
            "duelos_totales": duelos_totales,
            "duelos_aereos_ganados": agg.get("duelos_aereos_ganados") or 0,
            "duelos_aereos_totales": duelos_aereos_totales,
            "amarillas": agg.get("amarillas") or 0,
            "xg": round(agg.get("xg") or 0, 2),
            "goles_en_contra": agg.get("goles_en_contra") or 0,
            "porcentaje_paradas": round(agg.get("porcentaje_paradas") or 0, 1),
            "pct_duelos": round(pct_duelos, 1),
            "pct_duelos_aereos": round(pct_duelos_aereos, 1),
            "tiros_contra": agg.get("tiros_contra") or 0,
            "psxg_total": round(agg.get("psxg_total") or 0, 2),
            "sobrepasos": round((agg.get("psxg_total") or 0) - (agg.get("goles_en_contra") or 0), 2),
        }

        insights = get_insights(stats, posicion, n=3)
        return Response({"insights": insights, "posicion": posicion})
