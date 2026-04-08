from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import *
from .api.jugador import JugadorDetailView 
from .api.equipo import EquipoDetailView
from .api.clasificacion import ClasificacionView
from .serializers import *

class JugadorListView(generics.ListAPIView):
    #GET /api/v2/jugadores/?q=&pos=&temporada=
    serializer_class = JugadorListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Jugador.objects.all()
        q = self.request.query_params.get('q', '').strip()
        pos = self.request.query_params.get('pos', '').strip()
        temporada_display = self.request.query_params.get('temporada', '').strip()

        if temporada_display:
            temporada_nombre = temporada_display.replace('/', '_')
            qs = qs.filter(equipojugadortemporada__temporada__nombre=temporada_nombre).distinct()

        if q:
            qs = (qs.filter(nombre__icontains=q) | qs.filter(apellido__icontains=q)).distinct()

        if pos:
            qs = qs.filter(estadisticas_partidos__posicion__icontains=pos).distinct()

        return qs.order_by('apellido', 'nombre')[:100]


class JugadorDetailView(APIView):
    #GET /api/v2/jugadores/<id>/?temporada=25/26
    permission_classes = [permissions.AllowAny]

    def get(self, request, jugador_id):
        return JugadorDetailView().get(request, jugador_id)


class JugadorPrediccionesView(generics.ListAPIView):
    #GET /api/v2/jugadores/<id>/predicciones/?temporada=25/26
    serializer_class = PrediccionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        jugador_id = self.kwargs['jugador_id']
        qs = PrediccionJugador.objects.filter(jugador_id=jugador_id)

        temporada_display = self.request.query_params.get('temporada', '')
        if temporada_display:
            qs = qs.filter(jornada__temporada__nombre=temporada_display.replace('/', '_'))

        return qs.select_related('jugador', 'jornada', 'jornada__temporada').order_by(
            'jornada__temporada__nombre', 'jornada__numero_jornada')


class EquipoListView(generics.ListAPIView):
    #GET /api/v2/equipos/
    serializer_class = EquipoListSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Equipo.objects.all().order_by('nombre')


class EquipoDetailView(APIView):
    #GET /api/v2/equipos/<nombre>/?temporada=25/26&jornada=N"
    permission_classes = [permissions.AllowAny]

    def get(self, request, equipo_nombre):
        return EquipoDetailView().get(request, equipo_nombre)


class PrediccionCreateView(generics.CreateAPIView):
    #POST /api/v2/predicciones/
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
    #GET /api/v2/clasificacion/?temporada=25/26&jornada=N
    return ClasificacionView().get(request)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def jornadas_view(request):
#GET /api/v2/jornadas/?temporada=25/26
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
