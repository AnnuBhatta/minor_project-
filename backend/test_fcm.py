import os
import sys
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from emergency.services import send_emergency_test_notification

User = get_user_model()

def test_fcm():
    """Test FCM notifications"""
    email = input("Enter user email to test: ")
    
    try:
        user = User.objects.get(email=email)
        result = send_emergency_test_notification(user)
        
        if result['success']:
            print(f"✅ Test notification sent! Message ID: {result['message_id']}")
        else:
            print(f"❌ Failed: {result['error']}")
            
    except User.DoesNotExist:
        print(f"❌ User with email {email} not found")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_fcm()