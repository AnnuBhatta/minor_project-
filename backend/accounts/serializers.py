from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator
from .models import User, GuardianRequest

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'date_of_birth', 'address',
            'emergency_contact_name', 'emergency_contact_phone', 
            'emergency_contact_email', 'emergency_contact_relation',
            'medical_conditions', 'allergies', 'medications', 'blood_group',
            'profile_picture', 'is_guardian', 'is_patient', 'fcm_token',
            'created_at', 'updated_at', 'last_active', 'is_online'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_active', 'is_online']
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )
    email = serializers.EmailField(validators=[EmailValidator()])

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2', 
            'first_name', 'last_name', 'phone', 
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_email', 'is_guardian'
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'phone': {'required': False},
            'emergency_contact_name': {'required': False},
            'emergency_contact_phone': {'required': False},
            'emergency_contact_email': {'required': False},
            'email': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        
        # Check if email already exists
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({
                "email": "A user with this email already exists."
            })
        
        # Check if username already exists
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({
                "username": "A user with this username already exists."
            })
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # Try to find user by username or email
            user = None
            if '@' in username:
                # Login with email
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass
            else:
                # Login with username
                user = authenticate(username=username, password=password)
            
            if not user:
                raise serializers.ValidationError(
                    'Invalid credentials. Please check your username/email and password.'
                )
            
            if not user.is_active:
                raise serializers.ValidationError('This account is inactive.')
                
        else:
            raise serializers.ValidationError(
                'Must include "username" and "password".'
            )
        
        attrs['user'] = user
        return attrs

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True, 
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password2 = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "Password fields didn't match."
            })
        return attrs

class FCMTokenSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(required=True, max_length=255)

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'date_of_birth', 'address',
            'emergency_contact_name', 'emergency_contact_phone', 
            'emergency_contact_email', 'emergency_contact_relation',
            'medical_conditions', 'allergies', 'medications', 'blood_group',
            'profile_picture', 'is_guardian'
        ]
        read_only_fields = ['is_guardian']

class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'phone', 'is_guardian', 'is_online']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class UserSearchSerializer(serializers.ModelSerializer):
    """Minimal guardian info for search results (no private fields leaked)."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'first_name', 'last_name', 'phone', 'is_guardian']

    def get_full_name(self, obj):
        return obj.get_full_name()


class GuardianRequestSerializer(serializers.ModelSerializer):
    patient = UserListSerializer(read_only=True)
    guardian = UserListSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    incoming = serializers.SerializerMethodField()

    class Meta:
        model = GuardianRequest
        fields = [
            'id', 'patient', 'guardian', 'status', 'status_display',
            'message', 'incoming', 'created_at', 'updated_at',
        ]

    def get_incoming(self, obj):
        """True when the request targets the current user (guardian side)."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.guardian_id == request.user.id
        return False
    