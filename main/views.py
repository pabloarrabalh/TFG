from django.shortcuts import render

def menu(request):
    """Vista principal del menú"""
    return render(request, 'menu.html', {'active_page': 'menu'})

def mi_plantilla(request):
    """Vista de Mi Plantilla"""
    return render(request, 'mi_plantilla.html', {'active_page': 'mi-plantilla'})

def clasificacion(request):
    """Vista de Clasificación de la liga"""
    return render(request, 'clasificacion.html', {'active_page': 'liga'})

def equipo(request, equipo_nombre=None):
    """Vista de detalles de equipo"""
    return render(request, 'equipo.html', {
        'active_page': 'equipos', 
        'equipo_nombre': equipo_nombre or 'FC Barcelona',
        'desde_clasificacion': equipo_nombre is not None
    })

def jugador(request):
    """Vista de estadísticas de jugador"""
    return render(request, 'jugador.html', {'active_page': 'estadisticas'})

def amigos(request):
    """Vista de amigos y comparaciones"""
    return render(request, 'amigos.html', {'active_page': 'amigos'})

def login_register(request):
    """Vista de login y registro"""
    return render(request, 'login_register.html', {'active_page': 'login'})
