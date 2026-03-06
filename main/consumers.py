"""
WebSocket consumers for real-time notifications.
"""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class NotificacionConsumer(AsyncWebsocketConsumer):
    """
    ws://host/ws/notificaciones/
    Authenticated via Django session (AuthMiddlewareStack).
    - On connect: sends full notification list as 'init' message.
    - When a new Notificacion is saved: server pushes 'nueva' message.
    """

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = f'notificaciones_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Send current notifications immediately on connect
        notifs, no_leidas = await self._get_notificaciones(user)
        await self.send(text_data=json.dumps({
            'type': 'init',
            'notificaciones': notifs,
            'no_leidas': no_leidas,
        }))

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Client can request a refresh."""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'fetch':
                user = self.scope['user']
                notifs, no_leidas = await self._get_notificaciones(user)
                await self.send(text_data=json.dumps({
                    'type': 'init',
                    'notificaciones': notifs,
                    'no_leidas': no_leidas,
                }))
        except Exception:
            pass

    # ── Channel group message handler ─────────────────────────────────────────
    async def notificacion_nueva(self, event):
        """Called by channel layer group_send when a new notification arrives."""
        await self.send(text_data=json.dumps({
            'type': 'nueva',
            'notificacion': event['notificacion'],
            'no_leidas': event['no_leidas'],
        }))

    # ── DB helpers ────────────────────────────────────────────────────────────
    @database_sync_to_async
    def _get_notificaciones(self, user):
        from .models import Notificacion
        notifs = []
        for n in (
            Notificacion.objects
            .filter(usuario=user)
            .order_by('-fecha_creada')[:50]
        ):
            notifs.append({
                'id': n.id,
                'tipo': n.tipo,
                'titulo': n.titulo,
                'mensaje': n.mensaje,
                'leida': n.leida,
                'creada_en': n.fecha_creada.isoformat(),
                'datos': n.datos,
            })
        no_leidas = Notificacion.objects.filter(usuario=user, leida=False).count()
        return notifs, no_leidas
