from django.urls import path
from .views import *

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('refresh/', RefreshTokenView.as_view(), name='token-refresh'),
    
    # Profile
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('update-fcm-token/', UpdateFCMTokenView.as_view(), name='update-fcm-token'),
    
    # Guardians (consent workflow)
    path('my-guardians/', MyGuardiansView.as_view(), name='my-guardians'),
    path('my-patients/', MyPatientsView.as_view(), name='my-patients'),
    path('search-guardians/', SearchGuardiansView.as_view(), name='search-guardians'),
    path('send-request/', SendGuardianRequestView.as_view(), name='send-request'),
    path('my-requests/', MyRequestsView.as_view(), name='my-requests'),
    path('approve-request/<int:pk>/', ApproveRequestView.as_view(), name='approve-request'),
    path('reject-request/<int:pk>/', RejectRequestView.as_view(), name='reject-request'),
    path('remove-guardian/', RemoveGuardianView.as_view(), name='remove-guardian'),
]