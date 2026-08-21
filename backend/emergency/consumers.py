import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class EmergencyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
            
        # ✅ Join emergency group for this user
        self.group_name = f"emergency_{self.user.id}"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        await self.send_online_status(True)
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.send_online_status(False)
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'location_update':
            location = data.get('location')
            if location:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'location_update',
                        'location': location,
                        'user_id': self.user.id
                    }
                )
    
    # ✅ Send emergency alert with location to WebSocket
    async def emergency_alert(self, event):
        await self.send(text_data=json.dumps({
            'type': 'emergency_alert',
            'data': event.get('alert', {})
        }))
    
    async def emergency_location(self, event):
        """Handle emergency location broadcast from location app"""
        await self.send(text_data=json.dumps({
            'type': 'emergency_location',
            'location': event.get('location', {})
        }))
    
    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'location': event['location'],
            'user_id': event.get('user_id', self.user.id)
        }))
    
    @database_sync_to_async
    def send_online_status(self, is_online):
        try:
            user = User.objects.get(id=self.user.id)
            user.is_online = is_online
            user.last_active = timezone.now()
            user.save()
        except User.DoesNotExist:
            pass