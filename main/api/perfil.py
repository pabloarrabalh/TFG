"""
DRF API views – User Profile
Endpoints:
  GET    /api/perfil/
  PATCH  /api/perfil/update/
  PATCH  /api/perfil/status/
  POST   /api/perfil/foto/
  PATCH  /api/perfil/preferencias-notificaciones/
  POST   /api/perfil/cambiar-jornada/
"""
import logging
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db.models import Count, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import *
from ..views.utils import shield_name

logger = logging.getLogger(__name__)

_SHIELD_MAP = {
    'Barcelona': 'barcelona.png',
    'Real Madrid': 'madrid.png',
    'Atlético Madrid': 'atletico_madrid.png',
    'Valencia': 'valencia.png',
    'Sevilla': 'sevilla.png',
}


# ── 1. GET PERFIL ─────────────────────────────────────────────────────────────

class PerfilView(APIView):
    """GET /api/perfil/ – returns the authenticated user's full profile data."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = user.profile
        favoritos = (
            EquipoFavorito.objects
            .filter(usuario=user)
            .select_related('equipo')
            .order_by('-fecha_agregado')
        )
        return Response({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'nickname': profile.nickname,
            'estado': profile.estado,
            'preferencias_notificaciones': profile.preferencias_notificaciones,
            'foto_url': profile.foto.url if profile.foto else None,
            'equipos_favoritos': [
                {
                    'id': f.equipo.id,
                    'nombre': f.equipo.nombre,
                    'escudo': shield_name(f.equipo.nombre),
                }
                for f in favoritos
            ],
        })


# ── 2. UPDATE PERFIL ──────────────────────────────────────────────────────────

class UpdatePerfilView(APIView):
    """PATCH /api/perfil/update/ – update editable user / profile fields."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        data = request.data
        errors = {}

        new_email = (data.get('email') or user.email).strip()
        new_nickname = (data.get('nickname') or user.profile.nickname).strip()

        if new_email != user.email:
            if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                errors['email'] = 'Este email ya está registrado'

        if new_nickname != user.profile.nickname:
            if UserProfile.objects.filter(nickname=new_nickname).exclude(user=user).exists():
                errors['nickname'] = 'Este nickname ya está en uso'

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = new_email
        user.save()

        user.profile.nickname = new_nickname
        user.profile.save()

        return Response({'status': 'ok'})


# ── 3. UPDATE STATUS ──────────────────────────────────────────────────────────

class UpdateStatusView(APIView):
    """PATCH /api/perfil/status/ – change presence status."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in ('active', 'away', 'dnd'):
            return Response(
                {'error': 'Estado inválido. Opciones: active, away, dnd'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.profile.estado = nuevo_estado
        request.user.profile.save()
        return Response({'status': 'ok', 'estado': nuevo_estado})


# ── 4. UPLOAD PHOTO ───────────────────────────────────────────────────────────

class UploadPhotoView(APIView):
    """POST /api/perfil/foto/ – upload or set profile photo.

    Accepts one of:
      - multipart field ``foto``         (file upload)
      - POST field ``shield_team``       (use a club shield from /static/escudos/)
      - POST field ``default_avatar``    (use a default avatar from /static/logos/ or /static/escudos/)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        if request.POST.get('shield_team'):
            shield_team = request.POST['shield_team']
            filename = _SHIELD_MAP.get(shield_team)
            if not filename:
                return Response(
                    {'error': 'Equipo no encontrado'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            path = os.path.join(settings.BASE_DIR, 'static', 'escudos', filename)
            if not os.path.exists(path):
                return Response(
                    {'error': f'Archivo no encontrado: {path}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                with open(path, 'rb') as f:
                    profile.foto.save(
                        f'shield_{shield_team.lower().replace(" ", "_")}.png',
                        ContentFile(f.read()),
                        save=True,
                    )
                return Response({'status': 'success', 'photo_url': profile.foto.url})
            except Exception as exc:
                logger.error(f"Error guardando escudo: {exc}")
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        elif request.FILES.get('foto'):
            try:
                profile.foto = request.FILES['foto']
                profile.save()
                return Response({'status': 'success', 'photo_url': profile.foto.url})
            except Exception as exc:
                logger.error(f"Error guardando foto: {exc}")
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        elif request.POST.get('default_avatar'):
            avatar = request.POST['default_avatar']
            path = os.path.join(settings.BASE_DIR, 'static', 'logos', f'{avatar}.png')
            if not os.path.exists(path):
                path = os.path.join(settings.BASE_DIR, 'static', 'escudos', f'{avatar}.png')
            if not os.path.exists(path):
                return Response(
                    {'error': 'Archivo no encontrado'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                with open(path, 'rb') as f:
                    profile.foto.save(f'{avatar}.png', ContentFile(f.read()), save=True)
                return Response({'status': 'success', 'photo_url': profile.foto.url})
            except Exception as exc:
                logger.error(f"Error guardando avatar: {exc}")
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {'error': 'No se proporcionó foto'},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ── 5. UPDATE PREFERENCIAS NOTIFICACIONES ─────────────────────────────────────

class UpdatePreferenciasNotificacionesView(APIView):
    """PATCH /api/perfil/preferencias-notificaciones/"""
    permission_classes = [IsAuthenticated]

    _VALID = frozenset(('all', 'friends', 'events', 'none'))

    def patch(self, request):
        valor = request.data.get('preferencias_notificaciones')
        if valor not in self._VALID:
            return Response(
                {'error': f'Valor inválido. Opciones: {", ".join(sorted(self._VALID))}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.profile.preferencias_notificaciones = valor
        request.user.profile.save()
        return Response({'status': 'ok', 'preferencias_notificaciones': valor})


# ── 6. CAMBIAR JORNADA ────────────────────────────────────────────────────────

class CambiarJornadaView(APIView):
    """POST /api/perfil/cambiar-jornada/ {jornada: int}

    Returns the player roster split by position for the requested jornada,
    enriched with next-fixture and fantasy-points data.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        nueva_jornada = request.data.get('jornada')
        if not isinstance(nueva_jornada, int):
            return Response(
                {'error': 'jornada debe ser un entero'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temporada_actual = Temporada.objects.last()
        if not temporada_actual:
            return Response(
                {'error': 'No hay temporada disponible'},
                status=status.HTTP_404_NOT_FOUND,
            )

        jornada_obj = Jornada.objects.filter(
            temporada=temporada_actual, numero_jornada=nueva_jornada
        ).first()
        if not jornada_obj:
            return Response(
                {'error': f'Jornada {nueva_jornada} no existe'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build fixture lookup {equipo_id: {rival_id, rival_nombre, es_local}}
        partidos_por_equipo: dict = {}
        for partido in (
            Partido.objects.filter(jornada=jornada_obj)
            .select_related('equipo_local', 'equipo_visitante')
        ):
            partidos_por_equipo[partido.equipo_local.id] = {
                'rival_id': partido.equipo_visitante.id,
                'rival_nombre': partido.equipo_visitante.nombre,
                'es_local': True,
            }
            partidos_por_equipo[partido.equipo_visitante.id] = {
                'rival_id': partido.equipo_local.id,
                'rival_nombre': partido.equipo_local.nombre,
                'es_local': False,
            }

        # Fallback to Calendario if no Partido rows yet
        if not partidos_por_equipo:
            for cal in (
                Calendario.objects.filter(jornada=jornada_obj)
                .select_related('equipo_local', 'equipo_visitante')
            ):
                partidos_por_equipo[cal.equipo_local.id] = {
                    'rival_id': cal.equipo_visitante.id,
                    'rival_nombre': cal.equipo_visitante.nombre,
                    'es_local': True,
                }
                partidos_por_equipo[cal.equipo_visitante.id] = {
                    'rival_id': cal.equipo_local.id,
                    'rival_nombre': cal.equipo_local.nombre,
                    'es_local': False,
                }

        # Players with < 60 min in their last 4 games → flagged as 'pocos_minutos'
        _min_map: dict = {}
        for row in (
            EstadisticasPartidoJugador.objects
            .filter(partido__jornada__temporada=temporada_actual)
            .values('jugador_id', 'min_partido')
            .order_by('jugador_id', '-partido__jornada__numero_jornada')
        ):
            jid = row['jugador_id']
            if jid not in _min_map:
                _min_map[jid] = []
            if len(_min_map[jid]) < 4:
                _min_map[jid].append(row['min_partido'] or 0)

        pocos_minutos = {
            jid for jid, mins in _min_map.items()
            if mins and sum(mins) < 60
        }

        jugadores_por_posicion: dict = {
            'Portero': [], 'Defensa': [], 'Centrocampista': [], 'Delantero': [],
        }
        seen: set = set()
        for ejt in (
            EquipoJugadorTemporada.objects
            .filter(temporada=temporada_actual)
            .select_related('jugador', 'equipo')
            .order_by('jugador__nombre')
        ):
            jugador = ejt.jugador
            if jugador.id in seen:
                continue
            seen.add(jugador.id)

            posicion = ejt.posicion or 'Delantero'
            if posicion not in jugadores_por_posicion:
                continue

            stats = EstadisticasPartidoJugador.objects.filter(
                partido__jornada__temporada=temporada_actual,
                jugador=jugador,
                puntos_fantasy__lte=50,
            ).aggregate(total_puntos=Sum('puntos_fantasy'))

            rival = partidos_por_equipo.get(ejt.equipo.id)
            jugadores_por_posicion[posicion].append({
                'id': jugador.id,
                'nombre': jugador.nombre,
                'apellido': jugador.apellido,
                'posicion': posicion,
                'equipo_id': ejt.equipo.id,
                'equipo_nombre': ejt.equipo.nombre,
                'puntos_fantasy_25_26': stats['total_puntos'] or 0,
                'proximo_rival_id': rival['rival_id'] if rival else None,
                'proximo_rival_nombre': rival['rival_nombre'] if rival else None,
                'pocos_minutos': jugador.id in pocos_minutos,
            })

        return Response({
            'status': 'success',
            'jornada': nueva_jornada,
            'jugadores_por_posicion': jugadores_por_posicion,
        })
