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