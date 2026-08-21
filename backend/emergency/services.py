from django.contrib.auth import get_user_model
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import firebase_admin
from firebase_admin import credentials, messaging, exceptions
from datetime import datetime
import json
import os

User = get_user_model()

class FCMService:
    """Singleton Firebase Admin SDK service"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FCMService, cls).__new__(cls)
            cls._instance._initialize_firebase()
        return cls._instance
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            if not firebase_admin._apps:
                cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-adminsdk.json')
                
                if os.getenv('FIREBASE_CREDENTIALS'):
                    cred_json = json.loads(os.getenv('FIREBASE_CREDENTIALS'))
                    cred = credentials.Certificate(cred_json)
                elif os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                else:
                    cred = credentials.Certificate({
                        "type": "service_account",
                        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                        "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
                        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_CERT_URL', '')
                    })
                
                firebase_admin.initialize_app(cred)
                print("✅ Firebase Admin SDK initialized successfully!")
            else:
                print("ℹ️ Firebase Admin SDK already initialized")
                
        except Exception as e:
            print(f"❌ Failed to initialize Firebase Admin SDK: {e}")
            raise

def get_fcm_service():
    """Get FCM service instance"""
    return FCMService()

def send_emergency_alert(emergency_event):
    """
    Send emergency alerts via FCM and WebSocket to guardians
    """
    try:
        get_fcm_service()
        
        user = emergency_event.user
        location = emergency_event.location or {'lat': 0, 'lng': 0}
        
        # Get approved guardians only
        from accounts.models import GuardianRequest
        approved_guardian_ids = GuardianRequest.objects.filter(
            patient=user, status='approved'
        ).values_list('guardian_id', flat=True)
        guardians = User.objects.filter(id__in=approved_guardian_ids)
        
        if not guardians:
            print(f"⚠️ No approved guardians found for user {user.id}")
            return False
        
        channel_layer = get_channel_layer()
        alert_title = f"🚨 EMERGENCY ALERT from {user.get_full_name()}"
        alert_body = emergency_event.description or f"Emergency event at {emergency_event.created_at.strftime('%I:%M %p')}"
        
        # Location data for FCM
        location_string = f"📍 Location: {location.get('lat', 0)}, {location.get('lng', 0)}"
        
        # Prepare data payload
        data_payload = {
            'emergency_id': str(emergency_event.id),
            'user_id': str(user.id),
            'user_name': user.get_full_name(),
            'user_email': user.email,
            'user_phone': user.phone or '',
            'severity': emergency_event.severity,
            'timestamp': emergency_event.created_at.isoformat(),
            'lat': str(location.get('lat', 0)),
            'lng': str(location.get('lng', 0)),
            'is_manual': str(emergency_event.is_manual),
            'description': emergency_event.description or '',
            'type': 'emergency_alert'
        }
        
        sent_count = 0
        for guardian in guardians:
            # WebSocket: Send to guardian's emergency group
            async_to_sync(channel_layer.group_send)(
                f"emergency_{guardian.id}",
                {
                    'type': 'emergency_alert',
                    'alert': {
                        'id': emergency_event.id,
                        'user_id': user.id,
                        'user_name': user.get_full_name(),
                        'title': alert_title,
                        'message': alert_body,
                        'severity': emergency_event.severity or 'critical',
                        'status': 'pending',
                        'location': {
                            'lat': location.get('lat', 0),
                            'lng': location.get('lng', 0)
                        },
                        'timestamp': emergency_event.created_at.isoformat(),
                        'user_email': user.email,
                        'user_phone': user.phone or ''
                    }
                }
            )
            print(f"✅ WebSocket emergency alert sent to guardian {guardian.id}")
            
            # FCM: Send push notification if device token exists
            if guardian.fcm_token:
                try:
                    fcm_result = send_fcm_notification(
                        device_token=guardian.fcm_token,
                        title=alert_title,
                        body=alert_body[:100],
                        data=data_payload
                    )
                    if fcm_result:
                        sent_count += 1
                        print(f"✅ FCM notification sent to {guardian.email}")
                except Exception as e:
                    print(f"❌ FCM error for {guardian.email}: {e}")
        
        print(f"✅ Sent {sent_count} FCM emergency notifications")
        return sent_count > 0 or guardians.count() > 0
        
    except Exception as e:
        print(f"❌ Error sending emergency alert: {e}")
        return False

def send_fcm_notification(device_token, title, body, data=None):
    """Send FCM notification to a single device"""
    try:
        if not device_token:
            return None
            
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=device_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='emergency_sound',
                    channel_id='emergency_alerts',
                    priority='max',
                    default_sound=True,
                    default_vibrate_timings=True,
                    visibility='public'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1,
                        content_available=True,
                        mutable_content=True,
                        alert={
                            'title': title,
                            'body': body
                        }
                    )
                ),
                headers={
                    'apns-priority': '10',
                    'apns-push-type': 'alert'
                }
            )
        )
        
        response = messaging.send(message)
        print(f"✅ FCM message sent: {response}")
        return response
        
    except exceptions.FirebaseError as e:
        print(f"❌ FCM Firebase error: {e.code} - {e.message}")
        return None
    except Exception as e:
        print(f"❌ FCM error: {e}")
        return None

def get_emergency_recipients(user):
    """Get all emergency contacts for a user"""
    recipients = []
    emails = set()
    
    if user.emergency_contact_email:
        try:
            contact = User.objects.get(email=user.emergency_contact_email)
            if contact.email not in emails:
                recipients.append(contact)
                emails.add(contact.email)
        except User.DoesNotExist:
            pass
    
    from accounts.models import GuardianRequest
    approved_guardian_ids = GuardianRequest.objects.filter(
        patient=user, status='approved'
    ).values_list('guardian_id', flat=True)
    guardians = User.objects.filter(id__in=approved_guardian_ids)
    for guardian in guardians:
        if guardian.email and guardian.email not in emails:
            recipients.append(guardian)
            emails.add(guardian.email)
    
    if user.fcm_token and user.email not in emails:
        recipients.append(user)
        emails.add(user.email)
    
    return recipients

def send_emergency_test_notification(user, test_message="Test emergency notification"):
    try:
        get_fcm_service()
        
        if not user.fcm_token:
            return {"success": False, "error": "User has no FCM token"}
        
        result = send_fcm_notification(
            device_token=user.fcm_token,
            title="🧪 Test Emergency Alert",
            body=test_message,
            data={
                'type': 'test_alert',
                'timestamp': datetime.now().isoformat()
            }
        )
        
        return {"success": True, "message_id": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_emergency_to_contacts(emergency_event):
    """Send emergency alert to all contacts (guardians + direct emergency email)"""
    user = emergency_event.user
    try:
        from alerts.services import send_alert_email
        return send_alert_email(
            patient=user,
            alert_type='emergency',
            severity=emergency_event.severity or 'high',
            title='🚨 EMERGENCY ALERT',
            message=emergency_event.description or f"Emergency event triggered by {user.get_full_name()}",
            timestamp=emergency_event.created_at,
            location=emergency_event.location,
        )
    except Exception:
        import logging
        logging.getLogger('emergency').exception(
            'Failed to send emergency email for user %s', user.id,
        )
        return False