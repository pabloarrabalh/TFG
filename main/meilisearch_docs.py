import os

from dotenv import load_dotenv

from .models import Equipo, Jugador

# Cargar variables de entorno
load_dotenv()

MEILISEARCH_AVAILABLE = False
meilisearch_client = None
_raw_meilisearch_client = None


try:
    import meilisearch
    from meilisearch.errors import MeilisearchApiError
except ImportError:
    meilisearch = None

    class MeilisearchApiError(Exception):
        pass


JUGADORES_SETTINGS = {
    "searchableAttributes": ["nombre_completo", "nombre", "apellido", "nacionalidad", "posicion"],
    "filterableAttributes": ["id", "nacionalidad", "posicion"],
    "sortableAttributes": ["id"],
}

EQUIPOS_SETTINGS = {
    "searchableAttributes": ["nombre", "estadio"],
    "filterableAttributes": ["id"],
    "sortableAttributes": ["id"],
}


def _wait_for_task(task_info):
    if not _raw_meilisearch_client or not isinstance(task_info, dict):
        return

    task_uid = task_info.get("taskUid")
    if task_uid is None:
        task_uid = task_info.get("uid")
    if task_uid is None:
        return

    try:
        _raw_meilisearch_client.wait_for_task(task_uid, timeout_in_ms=30000)
    except Exception:
        # Si no podemos esperar la tarea, dejamos que continúe de forma asíncrona.
        return


def _ensure_index(index_uid, settings):
    if not _raw_meilisearch_client:
        return None

    index = _raw_meilisearch_client.index(index_uid)

    try:
        index.get_stats()
    except Exception:
        try:
            _wait_for_task(_raw_meilisearch_client.create_index(index_uid, {"primaryKey": "id"}))
            index = _raw_meilisearch_client.index(index_uid)
        except Exception:
            return None

    try:
        _wait_for_task(index.update_settings(settings))
    except Exception:
        # El índice puede funcionar aunque no se apliquen ajustes avanzados.
        pass

    return index


class MeilisearchClientAdapter:
    """Adaptador con interfaz similar al cliente usado anteriormente."""

    def __init__(self, client):
        self.client = client

    @staticmethod
    def _extract_query_from_body(body):
        if not isinstance(body, dict):
            return ""

        query_obj = body.get("query", {})
        if not isinstance(query_obj, dict):
            return ""

        bool_obj = query_obj.get("bool", {})
        if not isinstance(bool_obj, dict):
            return ""

        should_list = bool_obj.get("should", [])
        if not isinstance(should_list, list):
            return ""

        for clause in should_list:
            if not isinstance(clause, dict):
                continue

            for key in ("match_phrase_prefix", "match"):
                if key not in clause:
                    continue

                match_data = clause.get(key, {})
                if not isinstance(match_data, dict):
                    continue

                for value in match_data.values():
                    if isinstance(value, dict):
                        query = value.get("query")
                    else:
                        query = value

                    if isinstance(query, str) and query.strip():
                        return query.strip()

        return ""

    def search(self, index, body):
        query = self._extract_query_from_body(body)
        limit = 10
        if isinstance(body, dict):
            maybe_limit = body.get("size")
            if isinstance(maybe_limit, int) and maybe_limit > 0:
                limit = maybe_limit

        result = self.client.index(index).search(query, {"limit": limit})
        hits = result.get("hits", []) if isinstance(result, dict) else []
        return {"hits": {"hits": [{"_source": hit} for hit in hits]}}

    def index(self, index, id, body):
        doc = dict(body) if isinstance(body, dict) else {}
        doc["id"] = id
        target = _ensure_index(
            index,
            JUGADORES_SETTINGS if index == "jugadores" else EQUIPOS_SETTINGS,
        )
        if not target:
            raise RuntimeError("No se pudo preparar el índice en Meilisearch")

        _wait_for_task(target.add_documents([doc], primary_key="id"))

    def delete(self, index, id, ignore=None):
        try:
            _wait_for_task(self.client.index(index).delete_document(id))
        except MeilisearchApiError as exc:
            if ignore == 404:
                message = str(exc).lower()
                if "not found" in message or "index_not_found" in message:
                    return
            raise

    def count(self, index):
        stats = self.client.index(index).get_stats()
        return {"count": int(stats.get("numberOfDocuments", 0))}


if meilisearch is not None:
    meili_host = os.getenv("MEILISEARCH_HOST", "http://localhost:7700")
    if not meili_host.startswith("http://") and not meili_host.startswith("https://"):
        meili_host = f"http://{meili_host}"

    meili_api_key = os.getenv("MEILISEARCH_API_KEY", "")

    try:
        _raw_meilisearch_client = meilisearch.Client(
            meili_host,
            api_key=meili_api_key or None,
        )
        _raw_meilisearch_client.health()
        meilisearch_client = MeilisearchClientAdapter(_raw_meilisearch_client)
        MEILISEARCH_AVAILABLE = True
    except Exception:
        MEILISEARCH_AVAILABLE = False


if MEILISEARCH_AVAILABLE:
    def limpiar_indices():
        for index_uid, settings in (
            ("jugadores", JUGADORES_SETTINGS),
            ("equipos", EQUIPOS_SETTINGS),
        ):
            index = _ensure_index(index_uid, settings)
            if not index:
                continue

            try:
                _wait_for_task(index.delete_all_documents())
            except Exception:
                continue

    def indexar_jugadores():
        try:
            if not meilisearch_client:
                return

            index = _ensure_index("jugadores", JUGADORES_SETTINGS)
            if not index:
                return

            jugadores = Jugador.objects.all()
            total = jugadores.count()

            if total == 0:
                return

            documents = []
            contador = 0

            for jugador in jugadores:
                doc = {
                    "id": jugador.id,
                    "nombre_completo": f"{jugador.nombre} {jugador.apellido}",
                    "nombre": jugador.nombre,
                    "apellido": jugador.apellido,
                    "nacionalidad": jugador.nacionalidad,
                    "posicion": jugador.get_posicion_mas_frecuente() or "Desconocida",
                }
                documents.append(doc)
                contador += 1

                if contador % 100 == 0:
                    try:
                        _wait_for_task(index.add_documents(documents, primary_key="id"))
                    except Exception:
                        pass
                    documents = []

            if documents:
                try:
                    _wait_for_task(index.add_documents(documents, primary_key="id"))
                except Exception:
                    pass
        except Exception:
            return

    def indexar_equipos():
        try:
            if not meilisearch_client:
                return

            index = _ensure_index("equipos", EQUIPOS_SETTINGS)
            if not index:
                return

            equipos = Equipo.objects.all()
            total = equipos.count()

            if total == 0:
                return

            documents = []
            contador = 0

            for equipo in equipos:
                doc = {
                    "id": equipo.id,
                    "nombre": equipo.nombre,
                    "estadio": equipo.estadio or "Desconocido",
                }
                documents.append(doc)
                contador += 1

                if contador % 100 == 0:
                    try:
                        _wait_for_task(index.add_documents(documents, primary_key="id"))
                    except Exception:
                        pass
                    documents = []

            if documents:
                try:
                    _wait_for_task(index.add_documents(documents, primary_key="id"))
                except Exception:
                    pass
        except Exception:
            return

    def reindexar_todo():
        limpiar_indices()
        indexar_jugadores()
        indexar_equipos()

else:
    # Solo en local, no debería llegar nunca al desplegar.
    meilisearch_client = None

    def limpiar_indices():
        pass

    def indexar_jugadores():
        pass

    def indexar_equipos():
        pass

    def reindexar_todo():
        pass
