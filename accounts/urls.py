from django.urls import path
from .views import *

urlpatterns = [
    # 🔐 Auth
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
    path('profile/', ProfileView.as_view()),

    # 🏠 Property
    path('properties/', PropertyListView.as_view()),
    path('properties/<int:pk>/', PropertyDetailView.as_view()),
    path('properties/<int:pk>/update/', PropertyUpdateView.as_view()),
    path('properties/<int:pk>/delete/', PropertyDeleteView.as_view()),

    # 📅 Booking
    path('bookings/create/<int:property_id>/', BookingCreateView.as_view()),
    path('bookings/user/', UserBookingListView.as_view()),
    path('bookings/host/', HostBookingListView.as_view()),
    path('bookings/<int:pk>/approve/', BookingApproveView.as_view()),
    path('bookings/<int:pk>/reject/', BookingRejectView.as_view()),

    # 👑 Admin
    path('admin/create/', CreateAdminView.as_view()),
    path('admin/users/', AdminUserListView.as_view()),
    path('admin/tenants/', AdminTenantListView.as_view()),
    path('admin/users/<int:user_id>/toggle/', AdminToggleUserStatusView.as_view()),
    path('admin/users/<int:user_id>/role/', AdminChangeRoleView.as_view()),
    path('admin/users/<int:user_id>/delete/', AdminDeleteUserView.as_view()),
]