from django.urls import path
from .views import *

app_name = "accounts"

urlpatterns = [

    # 🔐 AUTH
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
    path('profile/', ProfileView.as_view()),

    path('verify-email/<str:token>/', VerifyEmailView.as_view()),
    path('resend-verification/', ResendVerificationView.as_view()),
    path('forgot-password/', ForgotPasswordView.as_view()),
    path('reset-password/<str:token>/', ResetPasswordView.as_view()),

    # 🔓 PUBLIC
    path('public/tenants/', PublicTenantListView.as_view()),

    # 👑 ADMIN
    path('admin/dashboard/', AdminDashboardStatsView.as_view()),
    path('admin/create/', CreateAdminView.as_view()),
    path('admin/users/', AdminUserListView.as_view()),
    path('admin/tenants/', AdminTenantListView.as_view()),
    path('admin/properties/<int:pk>/', AdminPropertyUpdateView.as_view()),
    path('admin/users/<int:user_id>/toggle/', AdminToggleUserStatusView.as_view()),
    path('admin/users/<int:user_id>/role/', AdminChangeRoleView.as_view()),
    path('admin/users/<int:user_id>/delete/', AdminDeleteUserView.as_view()),

    # 🏠 PROPERTY
    path('host/dashboard/', HostDashboardView.as_view()),
    path('properties/create/', PropertyCreateView.as_view()),
    path('properties/', PropertyListView.as_view()),
    path('properties/<int:pk>/', PropertyDetailView.as_view()),
    path('properties/<int:pk>/update/', PropertyUpdateView.as_view()),
    path('properties/<int:pk>/delete/', PropertyDeleteView.as_view()),

    # 📅 BOOKING
    path('bookings/create/<int:property_id>/', BookingCreateView.as_view()),
    path('bookings/user/', UserBookingListView.as_view()),
    path('bookings/host/', HostBookingListView.as_view()),
    path('bookings/<int:pk>/approve/', BookingApproveView.as_view()),
    path('bookings/<int:pk>/reject/', BookingRejectView.as_view()),
    path('bookings/<int:pk>/cancel/', BookingCancelView.as_view()),
]