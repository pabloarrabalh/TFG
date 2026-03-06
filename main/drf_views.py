"""
DRF-based REST API – v2
Base URL: /api/v2/

Recursos expuestos:
  GET /api/v2/jugadores/                    — lista de jugadores
  GET /api/v2/jugadores/<id>/               — detalle jugador
  GET /api/v2/jugadores/<id>/predicciones/  — predicciones vs real
  GET /api/v2/equipos/                      — lista de equipos
  GET /api/v2/equipos/<nombre>/             — detalle equipo
  GET /api/v2/clasificacion/                — tabla de clasificación
  GET /api/v2/jornadas/                     — jornadas por temporada
  POST /api/v2/predicciones/                — guardar predicción (requiere auth)
"""
from rest_framework import serializers, generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Sum, Count, Q, Avg

from .models import (
    Jugador, Equipo, Temporada, Jornada,
    EquipoJugadorTemporada, EstadisticasPartidoJugador,
    ClasificacionJornada, PrediccionJugador,
)
from .views.utils import shield_name
from .api.jugador import JugadorDetailView as JugadorDetailViewV1
from .api.equipo import EquipoDetailView as EquipoDetailViewV1
from .api.clasificacion import ClasificacionView as ClasificacionViewV1


# ─────────────────────────────────────────────────────────────────────────────
# Serializers
# ─────────────────────────────────────────────────────────────────────────────

class TemporadaSerializer(serializers.ModelSerializer):
    display = serializers.SerializerMethodField()

    class Meta:
        model = Temporada
        fields = ['id', 'nombre', 'display']

    def get_display(self, obj):
        return obj.nombre.replace('_', '/')


class JugadorListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listas."""
    posicion = serializers.SerializerMethodField()

    class Meta:
        model = Jugador
        fields = ['id', 'nombre', 'apellido', 'nacionalidad', 'posicion']

    def get_posicion(self, obj):
        return obj.get_posicion_mas_frecuente() or ''


class EquipoListSerializer(serializers.ModelSerializer):
    escudo = serializers.SerializerMethodField()
    jugadores_count = serializers.SerializerMethodField()

    class Meta:
        model = Equipo
        fields = ['id', 'nombre', 'estadio', 'escudo', 'jugadores_count']

    def get_escudo(self, obj):
        return shield_name(obj.nombre)

    def get_jugadores_count(self, obj):
        temporada = Temporada.objects.order_by('-nombre').first()
        if not temporada:
            return 0
        return EquipoJugadorTemporada.objects.filter(equipo=obj, temporada=temporada).count()


class PrediccionSerializer(serializers.ModelSerializer):
    jornada_numero = serializers.IntegerField(source='jornada.numero_jornada', read_only=True)
    temporada = serializers.CharField(source='jornada.temporada.nombre', read_only=True)
    real = serializers.SerializerMethodField()

    class Meta:
        model = PrediccionJugador
        fields = ['id', 'jugador_id', 'jornada_id', 'jornada_numero', 'temporada',
                  'prediccion', 'modelo', 'creada_en', 'real']
        read_only_fields = ['id', 'creada_en', 'jornada_numero', 'temporada', 'real']

    def get_real(self, obj):
        pts = EstadisticasPartidoJugador.objects.filter(
            jugador=obj.jugador,
            partido__jornada=obj.jornada,
        ).aggregate(s=Sum('puntos_fantasy'))['s']
        return float(pts) if pts is not None else None


class PrediccionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrediccionJugador
        fields = ['jugador', 'jornada', 'prediccion', 'modelo']

    def validate(self, data):
        # Verificar unicidad (jugador + jornada + modelo)
        qs = PrediccionJugador.objects.filter(
            jugador=data['jugador'],
            jornada=data['jornada'],
            modelo=data.get('modelo', 'xgb'),
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Ya existe una predicción para este jugador, jornada y modelo."
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

class JugadorListView(generics.ListAPIView):
    """GET /api/v2/jugadores/?q=&pos=&temporada="""
    serializer_class = JugadorListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Jugador.objects.all()
        q = self.request.query_params.get('q', '').strip()
        pos = self.request.query_params.get('pos', '').strip()
        temporada_display = self.request.query_params.get('temporada', '').strip()

        if temporada_display:
            temporada_nombre = temporada_display.replace('/', '_')
            qs = qs.filter(
                equipojugadortemporada__temporada__nombre=temporada_nombre
            ).distinct()

        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) | Q(apellido__icontains=q)
            )

        if pos:
            qs = qs.filter(
                estadisticas_partidos__posicion__icontains=pos
            ).distinct()

        return qs.order_by('apellido', 'nombre')[:100]


class JugadorDetailView(APIView):
    """GET /api/v2/jugadores/<id>/?temporada=25/26
    Proxy ligero — delega en la vista existente para no duplicar lógica.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, jugador_id):
        return JugadorDetailViewV1().get(request, jugador_id)


class JugadorPrediccionesView(generics.ListAPIView):
    """GET /api/v2/jugadores/<id>/predicciones/?temporada=25/26"""
    serializer_class = PrediccionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        jugador_id = self.kwargs['jugador_id']
        qs = PrediccionJugador.objects.filter(jugador_id=jugador_id)

        temporada_display = self.request.query_params.get('temporada', '')
        if temporada_display:
            qs = qs.filter(
                jornada__temporada__nombre=temporada_display.replace('/', '_')
            )

        return qs.select_related('jugador', 'jornada', 'jornada__temporada').order_by(
            'jornada__temporada__nombre', 'jornada__numero_jornada'
        )


class EquipoListView(generics.ListAPIView):
    """GET /api/v2/equipos/"""
    serializer_class = EquipoListSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Equipo.objects.all().order_by('nombre')


class EquipoDetailView(APIView):
    """GET /api/v2/equipos/<nombre>/?temporada=25/26&jornada=N"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, equipo_nombre):
        return EquipoDetailViewV1().get(request, equipo_nombre)


class PrediccionCreateView(generics.CreateAPIView):
    """POST /api/v2/predicciones/ — crea o actualiza predicción (upsert)"""
    serializer_class = PrediccionCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        obj, created = PrediccionJugador.objects.update_or_create(
            jugador=serializer.validated_data['jugador'],
            jornada=serializer.validated_data['jornada'],
            modelo=serializer.validated_data.get('modelo', 'xgb'),
            defaults={'prediccion': serializer.validated_data['prediccion']},
        )

        out = PrediccionSerializer(obj)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out.data, status=code)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def clasificacion_view(request):
    """GET /api/v2/clasificacion/?temporada=25/26&jornada=N"""
    return ClasificacionViewV1().get(request)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def jornadas_view(request):
    """GET /api/v2/jornadas/?temporada=25/26"""
    temporada_display = request.query_params.get('temporada', '25/26')
    temporada_nombre = temporada_display.replace('/', '_')

    try:
        temporada = Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        return Response({'error': 'Temporada no encontrada'}, status=404)

    jornadas = Jornada.objects.filter(temporada=temporada).order_by('numero_jornada')
    return Response({
        'temporada': temporada_display,
        'jornadas': [{'numero': j.numero_jornada} for j in jornadas],
    })
