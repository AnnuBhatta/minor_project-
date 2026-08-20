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
            
        self.group_name = f"emergency_{self.user.id}"
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send online status
        await self.send_online_status(True)
    
    async def disconnect(self, close_code):
        # Leave group
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        # Update online status
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.send_online_status(False)
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'location_update':
            # Handle location updates
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
    
    async def location_update(self, event):
        # Send location update to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'location': event['location'],
            'user_id': event['user_id']
        }))
    
    async def emergency_alert(self, event):
        # Send emergency alert to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'emergency_alert',
            'data': event['data']
        }))
    
    @database_sync_to_async
    def send_online_status(self, is_online):
        user = User.objects.get(id=self.user.id)
        user.is_online = is_online
        user.last_active = timezone.now()
        user.save()
