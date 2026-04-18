import math

from ..models import Temporada


def is_nan_or_inf(value) -> bool:
    try:
        return math.isnan(value) or math.isinf(value)
    except (TypeError, ValueError):
        return False


def safe_float(value, default=0.0) -> float:
    if value is None:
        return float(default)
    try:
        if is_nan_or_inf(value):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_float_or_none(value):
    if value is None:
        return None
    try:
        if is_nan_or_inf(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def sanitize_payload(value, default=0):
    if value is None:
        return None

    if isinstance(value, dict):
        return {k: sanitize_payload(v, default) for k, v in value.items()}

    if isinstance(value, list):
        return [sanitize_payload(item, default) for item in value]

    if isinstance(value, tuple):
        return tuple(sanitize_payload(item, default) for item in value)

    if isinstance(value, float) and is_nan_or_inf(value):
        return default

    return value


def get_latest_temporada():
    return Temporada.objects.order_by("-nombre").first()


def temporada_name_from_display(temporada_display: str | None, default: str = "25/26") -> str:
    raw = str(temporada_display or default).strip()
    return raw.replace("/", "_")


def temporada_display_from_name(temporada_name: str | None) -> str:
    if not temporada_name:
        return ""
    return str(temporada_name).replace("_", "/")


def get_temporada_by_display(temporada_display: str | None, default: str = "25/26"):
    temporada_nombre = temporada_name_from_display(temporada_display, default=default)
    try:
        return Temporada.objects.get(nombre=temporada_nombre)
    except Temporada.DoesNotExist:
        return get_latest_temporada()


def parse_int(value, default=None, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if min_value is not None and parsed < min_value:
        return default
    if max_value is not None and parsed > max_value:
        return default
    return parsed


def parse_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_unique_positive_int_ids(raw_ids) -> list[int]:
    if isinstance(raw_ids, list):
        values = raw_ids
    elif isinstance(raw_ids, str):
        values = [v.strip() for v in raw_ids.split(",") if v.strip()]
    else:
        values = []

    ids = []
    seen = set()
    for value in values:
        try:
            current_id = int(value)
        except (TypeError, ValueError):
            continue

        if current_id <= 0 or current_id in seen:
            continue

        seen.add(current_id)
        ids.append(current_id)

    return ids


def jugador_payload_basic(jugador_id, jugador_obj=None):
    if jugador_obj is None:
        return {"id": int(jugador_id)}
    return {
        "id": int(jugador_obj.id),
        "nombre": jugador_obj.nombre,
        "apellido": jugador_obj.apellido,
    }
