from rest_framework import status, generics, permissions, views
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
from django.utils import timezone
from .serializers import *
from .models import User, GuardianRequest

User = get_user_model()

class RegisterView(generics.GenericAPIView):
    """
    Register a new user account
    """
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)

class LoginView(generics.GenericAPIView):
    """
    Login user and return JWT tokens
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        # Update last active and online status
        user.last_active = timezone.now()
        user.is_online = True
        user.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

class LogoutView(generics.GenericAPIView):
    """
    Logout user by blacklisting refresh token
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            # Update online status
            user = request.user
            user.is_online = False
            user.save()
            
            return Response({
                'message': 'Successfully logged out'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get or update current user profile
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileUpdateSerializer

    def get_object(self):
        return self.request.user
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserSerializer
        return UserProfileUpdateSerializer

class ChangePasswordView(generics.GenericAPIView):
    """
    Change user password
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        # Check old password
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({
                'old_password': 'Wrong password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)

class UpdateFCMTokenView(generics.GenericAPIView):
    """
    Update Firebase Cloud Messaging token for push notifications
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FCMTokenSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.fcm_token = serializer.validated_data['fcm_token']
        user.save()
        
        return Response({
            'message': 'FCM token updated successfully'
        }, status=status.HTTP_200_OK)

class SearchGuardiansView(generics.ListAPIView):
    """
    Search guardian accounts by email / username / name. Excludes the caller,
    guardians already approved, and guardians with a pending request.
    GET /api/auth/search-guardians/?q=term  (minimum 2 characters)
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSearchSerializer
    pagination_class = None

    def get_queryset(self):
        q = self.request.query_params.get('q', '').strip()
        if len(q) < 2:
            return User.objects.none()

        user = self.request.user
        approved_ids = user.guardians.values_list('id', flat=True)
        pending_ids = GuardianRequest.objects.filter(
            patient=user, status='pending',
        ).values_list('guardian_id', flat=True)

        return (
            User.objects.filter(is_guardian=True)
            .annotate(
                full_name=Concat(
                    'first_name', Value(' '), 'last_name',
                    output_field=CharField(),
                )
            )
            .exclude(id=user.id)
            .exclude(id__in=approved_ids)
            .exclude(id__in=pending_ids)
            .filter(
                Q(email__icontains=q)
                | Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(full_name__icontains=q)
            )
            .distinct()[:20]
        )


class SendGuardianRequestView(generics.GenericAPIView):
    """
    Patient asks a guardian to monitor them. POST body: {guardian_id, message?}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        guardian_id = request.data.get('guardian_id')
        message = (request.data.get('message') or '').strip()

        if not guardian_id:
            return Response({'error': 'guardian_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if str(guardian_id) == str(request.user.id):
            return Response({'error': 'You cannot send a request to yourself'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            guardian = User.objects.get(id=guardian_id, is_guardian=True)
        except User.DoesNotExist:
            return Response({'error': 'Guardian not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.guardians.filter(id=guardian.id).exists():
            return Response(
                {'error': f'{guardian.get_full_name()} is already your guardian'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request_obj, created = GuardianRequest.objects.get_or_create(
            patient=request.user,
            guardian=guardian,
            defaults={'message': message},
        )

        if not created:
            if request_obj.status == 'approved':
                return Response({'error': 'Request already approved'}, status=status.HTTP_400_BAD_REQUEST)
            if request_obj.status == 'pending':
                return Response(
                    {'error': 'A request is already pending with this guardian'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Previously rejected → allow re-requesting.
            request_obj.status = 'pending'
            if message:
                request_obj.message = message
            request_obj.save()

        return Response({
            'message': f'Request sent to {guardian.get_full_name()}. Waiting for their approval.',
            'request': GuardianRequestSerializer(request_obj, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)


class MyRequestsView(generics.ListAPIView):
    """
    All guardian requests involving the current user (as patient or guardian).
    Response shape: { "requests": [...] }, each item has an `incoming` flag.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GuardianRequestSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            GuardianRequest.objects
            .filter(Q(patient=self.request.user) | Q(guardian=self.request.user))
            .select_related('patient', 'guardian')
        )

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True, context={'request': request})
        return Response({'requests': serializer.data})


class ApproveRequestView(generics.GenericAPIView):
    """
    Guardian approves a patient's request. POST /api/auth/approve-request/<id>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            req = GuardianRequest.objects.select_related('patient', 'guardian').get(id=pk)
        except GuardianRequest.DoesNotExist:
            return Response({'error': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)

        if req.guardian_id != request.user.id:
            return Response({'error': 'You are not the guardian for this request'}, status=status.HTTP_403_FORBIDDEN)

        if req.status != 'pending':
            return Response({'error': f'Request is already {req.get_status_display().lower()}'}, status=status.HTTP_400_BAD_REQUEST)

        req.patient.guardians.add(req.guardian)
        req.status = 'approved'
        req.save(update_fields=['status', 'updated_at'])

        return Response({
            'message': f'You are now monitoring {req.patient.get_full_name()}.',
        }, status=status.HTTP_200_OK)


class RejectRequestView(generics.GenericAPIView):
    """
    Guardian rejects a patient's request. POST /api/auth/reject-request/<id>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            req = GuardianRequest.objects.select_related('patient', 'guardian').get(id=pk)
        except GuardianRequest.DoesNotExist:
            return Response({'error': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)

        if req.guardian_id != request.user.id:
            return Response({'error': 'You are not the guardian for this request'}, status=status.HTTP_403_FORBIDDEN)

        if req.status != 'pending':
            return Response({'error': f'Request is already {req.get_status_display().lower()}'}, status=status.HTTP_400_BAD_REQUEST)

        req.status = 'rejected'
        req.save(update_fields=['status', 'updated_at'])

        return Response({
            'message': f'Request from {req.patient.get_full_name()} rejected.',
        }, status=status.HTTP_200_OK)


class RemoveGuardianView(generics.GenericAPIView):
    """
    Patient removes a guardian from their approved list. Also revokes the
    approved request so it can be re-requested later.
    POST body: {guardian_id}
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        guardian_id = request.data.get('guardian_id')
        if not guardian_id:
            return Response({
                'error': 'guardian_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            guardian = User.objects.get(id=guardian_id)
        except User.DoesNotExist:
            return Response({
                'error': 'Guardian not found'
            }, status=status.HTTP_404_NOT_FOUND)

        request.user.guardians.remove(guardian)
        GuardianRequest.objects.filter(
            patient=request.user, guardian=guardian,
        ).update(status='rejected')

        return Response({
            'message': f'{guardian.get_full_name()} removed from guardians',
        }, status=status.HTTP_200_OK)


class MyPatientsView(generics.ListAPIView):
    """
    List the patients who have added the current user as a guardian (approved only).
    Response shape: { "patients": [{id, full_name, email, phone, is_online}] }
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserListSerializer
    pagination_class = None

    def get_queryset(self):
        approved_ids = GuardianRequest.objects.filter(
            guardian=self.request.user, status='approved',
        ).values_list('patient_id', flat=True)
        return User.objects.filter(id__in=approved_ids)

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({'patients': serializer.data})


class MyGuardiansView(generics.ListAPIView):
    """
    List all guardians linked to the logged-in patient (approved requests only).
    Response shape: { "guardians": [{id, full_name, email, phone}] }
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserListSerializer
    pagination_class = None

    def get_queryset(self):
        approved_ids = GuardianRequest.objects.filter(
            patient=self.request.user, status='approved',
        ).values_list('guardian_id', flat=True)
        return User.objects.filter(id__in=approved_ids)

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({'guardians': serializer.data})


class RefreshTokenView(views.APIView):
    """
    Refresh access token using refresh token
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({
                'error': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token = RefreshToken(refresh_token)
            return Response({
                'access': str(token.access_token)
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)