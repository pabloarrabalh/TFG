"""Authentication and user profile views"""
import sys
import traceback
import logging

from django.shortcuts import render, redirect
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .models import Equipo, EquipoFavorito, UserProfile
from .views_utils import normalize_team_name_python

logger = logging.getLogger(__name__)


def amigos(request):
    """Vista de amigos y comparaciones"""
    return render(request, 'amigos.html', {'active_page': 'amigos'})


def login_register(request):
    """Vista de login y registro"""
    return render(request, 'login_register.html', {'active_page': 'login'})


def login_view(request):
    """Maneja el login del usuario"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if next_url:
                return redirect(next_url)
            return redirect('menu')
        else:
            return render(request, 'login_register.html', {
                'login_error': 'Usuario o contraseña incorrectos',
                'active_page': 'login',
                'next': next_url,
            })

    next_url = request.GET.get('next', '')
    return render(request, 'login_register.html', {'active_page': 'login', 'next': next_url})


def register_view(request):
    """Maneja el registro de nuevos usuarios"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        next_url = request.POST.get('next', '')

        if not all([email, first_name, last_name, nickname, password1, password2]):
            return render(request, 'login_register.html', {
                'register_error': 'Todos los campos son obligatorios',
                'active_page': 'register', 'next': next_url,
            })

        if '@' not in email:
            return render(request, 'login_register.html', {
                'register_error': 'Email inválido',
                'active_page': 'register', 'next': next_url,
            })

        if password1 != password2:
            return render(request, 'login_register.html', {
                'register_error': 'Las contraseñas no coinciden',
                'active_page': 'register', 'next': next_url,
            })

        if len(password1) < 8:
            return render(request, 'login_register.html', {
                'register_error': 'La contraseña debe tener al menos 8 caracteres',
                'active_page': 'register', 'next': next_url,
            })

        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            return render(request, 'login_register.html', {
                'register_error': 'Este email ya está registrado',
                'active_page': 'register', 'next': next_url,
            })

        if UserProfile.objects.filter(nickname=nickname).exists():
            return render(request, 'login_register.html', {
                'register_error': 'Este nickname ya está en uso',
                'active_page': 'register', 'next': next_url,
            })

        try:
            user = User.objects.create_user(
                username=email, email=email,
                first_name=first_name, last_name=last_name,
                password=password1,
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.nickname = nickname
            profile.save()
            login(request, user)
            return redirect('select_favorite_teams')

        except Exception as e:
            logger.error(f"Error en registro: {e}\n{traceback.format_exc()}")
            return render(request, 'login_register.html', {
                'register_error': f'Error al crear la cuenta: {e}',
                'active_page': 'register', 'next': next_url,
            })

    next_url = request.GET.get('next', '')
    return render(request, 'login_register.html', {'active_page': 'login', 'next': next_url})


@login_required(login_url='login_register')
def select_favorite_teams(request):
    """Vista para seleccionar equipos favoritos después del registro"""
    equipos = Equipo.objects.all().order_by('nombre')
    equipos_favoritos = set(request.user.equipos_favoritos.values_list('equipo_id', flat=True))
    return render(request, 'select_favorite_teams.html', {
        'active_page': 'favoritos',
        'equipos': equipos,
        'equipos_favoritos': equipos_favoritos,
    })


@login_required(login_url='login_register')
@require_http_methods(['POST'])
def toggle_favorite_team(request):
    """Toggle un equipo como favorito para el usuario autenticado"""
    team_id = request.POST.get('team_id')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not team_id:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Team ID requerido'}, status=400)
        return redirect('equipos')

    try:
        equipo = Equipo.objects.get(id=team_id)
        favorito = EquipoFavorito.objects.filter(usuario=request.user, equipo=equipo).first()

        is_favorite = False
        if favorito:
            favorito.delete()
        else:
            EquipoFavorito.objects.create(usuario=request.user, equipo=equipo)
            is_favorite = True

        if is_ajax:
            return JsonResponse({'status': 'success', 'is_favorite': is_favorite})

    except Equipo.DoesNotExist:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Equipo no encontrado'}, status=404)

    return redirect('equipos')


def logout_view(request):
    """Cierra sesión del usuario"""
    logout(request)
    return redirect('menu')


def terms_conditions(request):
    """Vista de términos y condiciones"""
    return render(request, 'terms_conditions.html', {'active_page': 'terms'})


@login_required(login_url='login_register')
def perfil_usuario(request):
    """Vista del perfil del usuario con datos personales, equipos favoritos, etc."""
    equipos_favoritos = EquipoFavorito.objects.filter(
        usuario=request.user
    ).select_related('equipo').order_by('-fecha_agregado')

    for fav in equipos_favoritos:
        fav.equipo_nombre_escudo = normalize_team_name_python(fav.equipo.nombre)

    return render(request, 'perfil_usuario.html', {
        'active_page': 'perfil',
        'equipos_favoritos': equipos_favoritos,
    })


@login_required(login_url='login_register')
def upload_profile_photo(request):
    """Subir foto de perfil o escudo"""
    import os
    from django.core.files.base import ContentFile

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    shield_map = {
        'Barcelona': 'barcelona.png',
        'Real Madrid': 'madrid.png',
        'Atlético Madrid': 'atletico_madrid.png',
        'Valencia': 'valencia.png',
        'Sevilla': 'sevilla.png',
    }

    if request.POST.get('shield_team'):
        shield_team = request.POST.get('shield_team')
        shield_filename = shield_map.get(shield_team)
        if not shield_filename:
            return JsonResponse({'status': 'error', 'message': 'Equipo no encontrado'}, status=400)
        try:
            static_path = os.path.join(settings.BASE_DIR, 'static', 'escudos', shield_filename)
            if os.path.exists(static_path):
                with open(static_path, 'rb') as f:
                    profile.foto.save(
                        f'shield_{shield_team.lower().replace(" ", "_")}.png',
                        ContentFile(f.read()), save=True
                    )
                return JsonResponse({'status': 'success', 'photo_url': profile.foto.url if profile.foto else ''})
            else:
                return JsonResponse({'status': 'error', 'message': f'Archivo no encontrado: {static_path}'}, status=400)
        except Exception as e:
            logger.error(f"Error guardando escudo: {e}\n{traceback.format_exc()}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    elif request.FILES.get('foto'):
        try:
            profile.foto = request.FILES['foto']
            profile.save()
            return JsonResponse({'status': 'success', 'photo_url': profile.foto.url})
        except Exception as e:
            logger.error(f"Error guardando foto: {e}\n{traceback.format_exc()}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    elif request.POST.get('default_avatar'):
        default_avatar = request.POST.get('default_avatar')
        try:
            static_path = os.path.join(settings.BASE_DIR, 'static', 'logos', f'{default_avatar}.png')
            if not os.path.exists(static_path):
                static_path = os.path.join(settings.BASE_DIR, 'static', 'escudos', f'{default_avatar}.png')

            if os.path.exists(static_path):
                with open(static_path, 'rb') as f:
                    profile.foto.save(f'{default_avatar}.png', ContentFile(f.read()), save=True)
                return JsonResponse({'status': 'success', 'photo_url': profile.foto.url if profile.foto else ''})
            else:
                return JsonResponse({'status': 'error', 'message': f'Archivo no encontrado: {static_path}'}, status=400)
        except Exception as e:
            logger.error(f"Error guardando avatar: {e}\n{traceback.format_exc()}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'No se proporcionó foto'}, status=400)


@login_required(login_url='login_register')
def update_profile(request):
    """Actualizar datos del perfil"""
    if request.method == 'POST':
        user = request.user
        new_email = request.POST.get('email', user.email).strip()
        new_nickname = request.POST.get('nickname', user.profile.nickname).strip()

        if new_email != user.email and User.objects.filter(email=new_email).exists():
            return render(request, 'perfil_usuario.html', {
                'equipos_favoritos': user.profile.equipos_favoritos.all(),
                'edit_error': 'Este email ya está registrado',
            })

        if new_nickname != user.profile.nickname and UserProfile.objects.filter(nickname=new_nickname).exists():
            return render(request, 'perfil_usuario.html', {
                'equipos_favoritos': user.profile.equipos_favoritos.all(),
                'edit_error': 'Este nickname ya está en uso',
            })

        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = new_email
        user.save()
        user.profile.nickname = new_nickname
        user.profile.save()
        return redirect('perfil')

    return redirect('perfil')


@login_required(login_url='login_register')
def update_user_status(request):
    """Actualizar estado del usuario"""
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['active', 'away', 'dnd']:
            request.user.profile.estado = nuevo_estado
            request.user.profile.save()
    return redirect('perfil')


@login_required(login_url='login_register')
def delete_favorite_team(request, fav_id):
    """Eliminar equipo favorito"""
    try:
        fav = EquipoFavorito.objects.get(id=fav_id, usuario=request.user)
        fav.delete()
    except EquipoFavorito.DoesNotExist:
        pass
    return redirect('perfil')
