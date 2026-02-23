from django import template
import unicodedata

register = template.Library()

@register.filter
def normalize_team_name(value):
    """Normaliza el nombre del equipo para usar en clases CSS"""
    if not value:
        return ''
    
    normalized = value.lower().strip()
    
    # Remover prefijos comunes
    prefixes = ['fc ', 'cd ', 'ad ', 'rcd ', 'real ', 'ud ', 'cf ', 'sd ', 'ef ', 'ca ']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    
    # Remover acentos
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', normalized)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Reemplazar espacios con guiones
    normalized = normalized.replace(' ', '-')
    
    # Remover caracteres especiales
    normalized = ''.join(c if c.isalnum() or c == '-' else '' for c in normalized)
    
    return normalized

@register.filter
def shield_name(value):
    """Convierte el nombre del equipo a formato para archivos de escudos"""
    if not value:
        return ''
    
    # Convertir a minúsculas
    shield = value.lower().strip()

    # Remover acentos PRIMERO (antes de buscar prefijos)
    shield = ''.join(
        c for c in unicodedata.normalize('NFD', shield)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Casos específicos para equipos
    special_cases = {
        'atletico': 'atletico',
        'athletic': 'athletic_club',
        'rayo': 'rayo_vallecano',
        'celta': 'celta',
    }
    for key, replacement in special_cases.items():
        if shield.startswith(key):
            return replacement

    # Remover prefijos comunes (solo "real ", NO "atletico")
    prefixes = ['fc ', 'rcd ', 'cd ', 'cf ', 'sd ', 'ef ', 'ca ', 'ud ', 'real ']
    for prefix in prefixes:
        if shield.startswith(prefix):
            shield = shield[len(prefix):]
            break

    # Reemplazar espacios con guiones bajos
    shield = shield.replace(' ', '_')
    
    # Remover caracteres especiales (mantener solo alfanuméricos y guiones bajos)
    shield = ''.join(c if c.isalnum() or c == '_' else '' for c in shield)

    return shield



@register.filter
def split(value, separator=" "):
    """Divide un string por un separador"""
    if not value:
        return []
    return value.split(separator)

@register.filter
def format_temporada(value):
    """Convierte formato de temporada de 23_24 a 23/24"""
    if not value:
        return ''
    return value.replace('_', '/')

@register.filter
def weekday_name(value):
    """Devuelve el nombre del día de la semana en español"""
    if not value:
        return ''
    days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    return days[value.weekday()]

@register.filter
def format_fecha_partido(value):
    """Devuelve la fecha formateada como 'Domingo 23 Febrero, 21:30'"""
    if not value:
        return ''
    
    days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    months = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
              'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    weekday = days[value.weekday()]
    day = value.day
    month = months[value.month - 1]
    time = value.strftime('%H:%M')
    
    return f"{weekday} {day} {month}, {time}"

@register.filter
def display_team_name(value):
    """Mapea los nombres de equipos para mostrar versiones formales"""
    if not value:
        return ''
    
    name_mapping = {
        'barcelona': 'FC Barcelona',
        'alavés': 'Deportivo Alavés',
        'alaves': 'Deportivo Alavés',
        'atlético madrid': 'Atlético de Madrid',
        'atletico madrid': 'Atlético de Madrid',
        'levante': 'Levante UD',
        'real mallorca': 'RCD Mallorca',
        'celta vigo': 'Celta de Vigo',
        'celta de vigo': 'Celta de Vigo',
    }
    
    lower_value = value.lower().strip()
    return name_mapping.get(lower_value, value)