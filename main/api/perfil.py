
import os
import re
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.db.models import Count, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import *
from ..views.utils import shield_name


def _build_unique_name(prefix: str, source_name: str) -> str:
    ext = Path(source_name or '').suffix.lower() or '.png'
    return f'{prefix}_{uuid.uuid4().hex}{ext}'


def _cache_busted_url(file_field) -> str | None:
    if not file_field:
        return None
    return f"{file_field.url}?v={int(time.time())}"


def _store_user_upload_copy(file_bytes: bytes, original_name: str) -> None:
    target_dir = os.path.join(settings.BASE_DIR, 'frontend-web', 'userprofilefotos')
    os.makedirs(target_dir, exist_ok=True)
    filename = _build_unique_name('upload', original_name)
    with open(os.path.join(target_dir, filename), 'wb') as f:
        f.write(file_bytes)


def _resolve_default_avatar_path(raw_avatar: str) -> Path | None:
    avatar = (raw_avatar or '').strip()
    if not avatar:
        return None

    avatar = avatar[:-4] if avatar.lower().endswith('.png') else avatar
    if not re.fullmatch(r'[A-Za-z0-9_-]+', avatar):
        return None

    static_root = Path(settings.BASE_DIR) / 'static'
    direct_candidates = [
        static_root / 'logos' / f'{avatar}.png',
        static_root / 'logos' / f'{avatar.lower()}.png',
        static_root / 'escudos' / f'{avatar}.png',
        static_root / 'escudos' / f'{avatar.lower()}.png',
    ]
    for candidate in direct_candidates:
        if candidate.exists():
            return candidate

    for folder in ('logos', 'escudos'):
        for candidate in (static_root / folder).glob('*.png'):
            if candidate.stem.lower() == avatar.lower():
                return candidate
    return None



class PerfilView(APIView):
    """GET /api/perfil/ """
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
            'foto_url': _cache_busted_url(profile.foto),
            'equipos_favoritos': [
                {
                    'id': f.equipo.id,
                    'nombre': f.equipo.nombre,
                    'escudo': shield_name(f.equipo.nombre),
                }
                for f in favoritos
            ],
        })


class UpdatePerfilView(APIView):
    """PATCH /api/perfil/update/."""
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
            if new_nickname and UserProfile.objects.filter(nickname__iexact=new_nickname).exclude(user=user).exists():
                errors['nickname'] = 'Este nickname ya está en uso'
            if new_nickname and User.objects.filter(username__iexact=new_nickname).exclude(pk=user.pk).exists():
                errors['nickname'] = 'Este nickname ya está en uso'

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = new_email
        user.save()

        user.profile.nickname = new_nickname
        try:
            user.profile.save()
        except IntegrityError:
            return Response(
                {'errors': {'nickname': 'Este nickname ya está en uso'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({'status': 'ok'})


class UpdateStatusView(APIView):
    """PATCH /api/perfil/status/"""
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


class UploadPhotoView(APIView):
    """POST /api/perfil/foto/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        default_avatar = request.data.get('default_avatar')
        uploaded_photo = request.FILES.get('foto')

        if uploaded_photo:
            try:
                file_bytes = uploaded_photo.read()
                generated_name = _build_unique_name('user_photo', uploaded_photo.name)
                profile.foto.save(generated_name, ContentFile(file_bytes), save=True)
                _store_user_upload_copy(file_bytes, uploaded_photo.name)
                return Response({'status': 'success', 'photo_url': _cache_busted_url(profile.foto)})
            except Exception as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        elif default_avatar:
            avatar_path = _resolve_default_avatar_path(default_avatar)
            if not avatar_path:
                return Response(
                    {'error': 'Avatar predeterminado no encontrado'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                with open(avatar_path, 'rb') as f:
                    file_bytes = f.read()
                    generated_name = _build_unique_name(avatar_path.stem, avatar_path.name)
                    profile.foto.save(generated_name, ContentFile(file_bytes), save=True)
                return Response({'status': 'success', 'photo_url': _cache_busted_url(profile.foto)})
            except Exception as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {'error': 'No se proporcionó foto'},
            status=status.HTTP_400_BAD_REQUEST,
        )


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


