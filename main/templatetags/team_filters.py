from django import template
import unicodedata

register = template.Library()

@register.filter
def normalize_team_name(value):
    """Normaliza el nombre del equipo para usar en clases CSS"""
    if not value:
        return ''
    
    # Convertir a minúsculas
    normalized = value.lower()
    
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