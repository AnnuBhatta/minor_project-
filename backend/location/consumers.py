import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import UserLocation

User = get_user_model()

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join personal location group
        self.user_group = f"user_{self.user.id}_location"
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        
        # If user is a guardian, join emergency group
        if self.user.is_guardian:
            self.guardian_group = f"guardian_{self.user.id}_emergency"
            await self.channel_layer.group_add(
                self.guardian_group,
                self.channel_name
            )
        
        await self.accept()
        
        # Send initial location
        await self.send_initial_location()
    
    async def disconnect(self, close_code):
        # Leave groups
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
        
        if hasattr(self, 'guardian_group'):
            await self.channel_layer.group_discard(
                self.guardian_group,
                self.channel_name
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'get_location_history':
            user_id = data.get('user_id', self.user.id)
            locations = await self.get_location_history(user_id)
            await self.send(text_data=json.dumps({
                'type': 'location_history',
                'locations': locations
            }))
    
    async def location_update(self, event):
        """Handle location updates from backend"""
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'location': event['location']
        }))
    
    async def emergency_location(self, event):
        """Handle emergency location updates for guardians"""
        await self.send(text_data=json.dumps({
            'type': 'emergency_location',
            'location': event['location']
        }))
    
    async def send_initial_location(self):
        """Send the latest location when user connects"""
        location = await self.get_latest_location(self.user.id)
        if location:
            await self.send(text_data=json.dumps({
                'type': 'initial_location',
                'location': {
                    'user_id': self.user.id,
                    'user_name': self.user.get_full_name(),
                    'latitude': float(location.latitude),
                    'longitude': float(location.longitude),
                    'accuracy': location.accuracy,
                    'is_emergency': location.is_emergency,
                    'timestamp': location.timestamp.isoformat()
                }
            }))
    
    @database_sync_to_async
    def get_latest_location(self, user_id):
        try:
            return UserLocation.objects.filter(user_id=user_id).first()
        except:
            return None
    
    @database_sync_to_async
    def get_location_history(self, user_id, limit=100):
        locations = UserLocation.objects.filter(
            user_id=user_id
        )[:limit]
        
        return [{
            'latitude': float(loc.latitude),
            'longitude': float(loc.longitude),
            'timestamp': loc.timestamp.isoformat(),
            'is_emergency': loc.is_emergency
        } for loc in locations]