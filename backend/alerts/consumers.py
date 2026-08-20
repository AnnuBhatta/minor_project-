import json

from channels.generic.websocket import AsyncWebsocketConsumer


class AlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket endpoint for live alert delivery: /ws/alerts/

    A patient's session joins `user_<id>_alerts`; a guardian's session
    additionally joins `guardian_<id>_alerts` so it receives alerts raised
    for every patient under its care. Payload shape matches what the web
    frontend already expects:
        {'type': 'new_alert', 'alert': {...}}
    """

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_group = f"user_{self.user.id}_alerts"
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        if self.user.is_guardian:
            self.guardian_group = f"guardian_{self.user.id}_alerts"
            await self.channel_layer.group_add(self.guardian_group, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        if hasattr(self, 'guardian_group'):
            await self.channel_layer.group_discard(self.guardian_group, self.channel_name)

    async def new_alert(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_alert',
            'alert': event['alert'],
        }))
