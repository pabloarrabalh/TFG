import time

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken

from ..models import UserProfile

def _user_info(user):
    profile_photo = None
    nickname = None
    estado = 'active'
    if user.is_authenticated:
        try:
            p = user.profile
            if p.foto:
                profile_photo = f"{p.foto.url}?v={int(time.time())}"
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


def _issue_access_token(user):
    token = AccessToken.for_user(user)
    token['username'] = user.username
    return str(token)

class MeView(APIView):
    """GET /api/me/"""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(_user_info(request.user))


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
            try:
                u = User.objects.get(email=username)
                user = authenticate(request._request, username=u.username, password=password)
            except Exception:
                pass

        if user is None:
            return Response({'error': 'Credenciales incorrectas'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({'status': 'ok', 'user': _user_info(user), 'access': _issue_access_token(user)})


class LogoutView(APIView):
    """POST /api/auth/logout/"""
    permission_classes = [AllowAny]

    def post(self, request):
        return Response({'status': 'ok'})


class RegisterView(APIView):
    """POST /api/auth/register/"""
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        username = (data.get('username') or '').strip()
        nickname = (data.get('nickname') or username).strip()
        password1 = data.get('password1') or ''
        password2 = data.get('password2') or ''

        errors = {}
        if not email:
            errors['email'] = 'El email es obligatorio'
        if not username:
            errors['username'] = 'El apodo es obligatorio'
        if not nickname:
            errors['username'] = 'El apodo es obligatorio'
        if not password1:
            errors['password1'] = 'La contraseña es obligatoria'
        if password1 != password2:
            errors['password2'] = 'Las contraseñas no coinciden'
        if User.objects.filter(username__iexact=username).exists():
            errors['username'] = 'Ese apodo ya está en uso'
        if User.objects.filter(email__iexact=email).exists():
            errors['email'] = 'Ese email ya está registrado'
        if nickname and User.objects.filter(username__iexact=nickname).exists():
            errors['username'] = 'Ese apodo ya está en uso'
        if nickname and UserProfile.objects.filter(nickname__iexact=nickname).exists():
            errors['username'] = 'Ese apodo ya está en uso'

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
            )

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.nickname = nickname
            profile.save(update_fields=['nickname'])
        except IntegrityError:
            return Response(
                {'errors': {'username': 'Ese apodo ya está en uso'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return Response({
            'status': 'ok',
            'user': _user_info(user),
            'is_new_user': True,  # Para el tour
            'access': _issue_access_token(user),
        })
