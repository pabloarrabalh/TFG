"""
DRF API views – Authentication & User Info
Endpoints:
  GET  /api/me/
  POST /api/auth/login/
  POST /api/auth/logout/
  POST /api/auth/register/
"""
import json
import logging

from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _user_info(user):
    profile_photo = None
    nickname = None
    estado = 'active'
    if user.is_authenticated:
        try:
            p = user.profile
            if p.foto:
                profile_photo = p.foto.url
            nickname = p.nickname
            estado = p.estado or 'active'
        except Exception:
            pass
    return {
        'authenticated': user.is_authenticated,
        'id': user.id if user.is_authenticated else None,
        'username': user.username if user.is_authenticated else None,
        'first_name': user.first_name if user.is_authenticated else None,
        'last_name': user.last_name if user.is_authenticated else None,
        'email': user.email if user.is_authenticated else None,
        'nickname': nickname,
        'estado': estado,
        'profile_photo': profile_photo,
        'foto_url': profile_photo,
    }


# ── 1. ME ─────────────────────────────────────────────────────────────────────

class MeView(APIView):
    """GET /api/me/ – returns current user data + sets CSRF cookie"""
    permission_classes = [AllowAny]

    def get(self, request):
        from django.middleware.csrf import get_token
        get_token(request)  # Ensures CSRF cookie is set
        return Response(_user_info(request.user))


# ── 2. LOGIN / LOGOUT ─────────────────────────────────────────────────────────

class LoginView(APIView):
    """POST /api/auth/login/"""
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            username = (data.get('username') or '').strip()
            password = data.get('password') or ''
        except Exception:
            return Response({'error': 'JSON inválido'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request._request, username=username, password=password)
        if user is None:
            # Fallback: try by email
            try:
                u = User.objects.get(email=username)
                user = authenticate(request._request, username=u.username, password=password)
            except Exception:
                pass

        if user is None:
            return Response({'error': 'Credenciales incorrectas'}, status=status.HTTP_401_UNAUTHORIZED)

        auth_login(request._request, user)
        return Response({'status': 'ok', 'user': _user_info(user)})


class LogoutView(APIView):
    """POST /api/auth/logout/"""
    permission_classes = [AllowAny]

    def post(self, request):
        auth_logout(request._request)
        return Response({'status': 'ok'})


# ── 3. REGISTER ───────────────────────────────────────────────────────────────

class RegisterView(APIView):
    """POST /api/auth/register/"""
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        username = (data.get('username') or '').strip()
        nickname = (data.get('nickname') or '').strip()
        password1 = data.get('password1') or ''
        password2 = data.get('password2') or ''

        errors = {}
        if not first_name:
            errors['first_name'] = 'El nombre es obligatorio'
        if not email:
            errors['email'] = 'El email es obligatorio'
        if not username:
            errors['username'] = 'El nombre de usuario es obligatorio'
        if not nickname:
            errors['nickname'] = 'El apodo es obligatorio'
        if not password1:
            errors['password1'] = 'La contraseña es obligatoria'
        if password1 != password2:
            errors['password2'] = 'Las contraseñas no coinciden'
        if User.objects.filter(username=username).exists():
            errors['username'] = 'Ese nombre de usuario ya está en uso'
        if User.objects.filter(email=email).exists():
            errors['email'] = 'Ese email ya está registrado'
        
        # Importar UserProfile aquí para evitar circular imports
        from ..models import UserProfile
        if UserProfile.objects.filter(nickname=nickname).exists():
            errors['nickname'] = 'Ese apodo ya está en uso'

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )
        
        # Guardar nickname en el perfil
        profile = user.profile
        profile.nickname = nickname
        profile.save()
        
        auth_login(request._request, user)
        return Response({'status': 'ok', 'user': _user_info(user)})
