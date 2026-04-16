from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
import logging

from .models import Property, Booking, Tenant, User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    PropertySerializer,
    BookingSerializer,
    AdminCreateSerializer
)
from .permissions import IsHost, IsEndUser, IsSuperAdmin

logger = logging.getLogger(__name__)


# =========================
# RESPONSE HELPERS
# =========================
def success_response(data=None, message="Success"):
    return Response({
        "success": True,
        "message": message,
        "data": data
    })


def error_response(message="Error", status_code=400):
    return Response({
        "success": False,
        "error": message
    }, status=status_code)


# =========================
# PAGINATION
# =========================
class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response({
            "success": True,
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "data": data
        })


# =========================
# BOOKING CONFLICT CHECK
# =========================
def is_conflict(prop, check_in, check_out):
    return Booking.objects.filter(
        property=prop,
        status='approved'
    ).filter(
        Q(check_in__lt=check_out) & Q(check_out__gt=check_in)
    ).exists()


# =========================
# AUTH
# =========================
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return success_response(
            {"username": user.username, "role": user.role},
            "User registered"
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return success_response(serializer.validated_data, "Login successful")


class ProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response({
            "username": request.user.username,
            "role": request.user.role,
            "tenant": request.user.tenant.name if request.user.tenant else None
        })


# =========================
# ADMIN
# =========================
class CreateAdminView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        serializer = AdminCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return success_response(message="Admin created")


class AdminUserListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        users = User.objects.all()
        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(users, request)

        data = [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "tenant": u.tenant.name if u.tenant else None
        } for u in result_page]

        return paginator.get_paginated_response(data)


class AdminTenantListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        tenants = Tenant.objects.all()
        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(tenants, request)

        data = [{"id": t.id, "name": t.name} for t in result_page]
        return paginator.get_paginated_response(data)


class AdminToggleUserStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        if user.is_super_admin:
            return error_response("Cannot modify super admin", 403)

        user.is_active = not user.is_active
        user.save()

        return success_response(
            {"is_active": user.is_active},
            "User status updated"
        )


class AdminDeleteUserView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def delete(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        if user.is_super_admin:
            return error_response("Cannot delete super admin", 403)

        user.delete()
        return Response(status=204)


class AdminChangeRoleView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        role = request.data.get("role")

        if role not in ['host', 'user']:
            return error_response("Invalid role")

        if role == 'host' and not user.tenant:
            user.tenant = Tenant.objects.create(
                name=f"{user.username}'s workspace"
            )

        if role == 'user' and not user.tenant:
            return error_response("User must belong to a tenant")

        user.role = role
        user.save()

        return success_response(message="Role updated")


# =========================
# PROPERTY
# =========================
class PropertyBaseView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_property(self, pk, user):
        if user.is_super_admin:
            return get_object_or_404(Property, pk=pk)
        return get_object_or_404(Property, pk=pk, tenant=user.tenant)


class PropertyCreateView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsHost]

    def post(self, request):
        serializer = PropertySerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"{request.user.username} created property")

        return success_response(serializer.data, "Property created")


class PropertyListView(PropertyBaseView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        props = Property.objects.all() if user.is_super_admin else \
                Property.objects.filter(tenant=user.tenant)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(props, request)

        serializer = PropertySerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PropertyDetailView(PropertyBaseView):
    def get(self, request, pk):
        prop = self.get_property(pk, request.user)
        serializer = PropertySerializer(prop)
        return success_response(serializer.data)


class PropertyUpdateView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsHost]

    def put(self, request, pk):
        prop = self.get_property(pk, request.user)

        serializer = PropertySerializer(
            prop,
            data=request.data,
            partial=True,  # 🔥 IMPORTANT FIX
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return success_response(serializer.data, "Updated")


class PropertyDeleteView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsHost]

    def delete(self, request, pk):
        prop = self.get_property(pk, request.user)
        prop.delete()
        return Response(status=204)


# =========================
# BOOKING
# =========================
class BookingCreateView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsEndUser]

    def post(self, request, property_id):
        prop = self.get_property(property_id, request.user)

        serializer = BookingSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        if is_conflict(prop, data['check_in'], data['check_out']):
            return error_response("Property already booked")

        serializer.save(property=prop)
        return success_response(serializer.data, "Booking created")


class UserBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(user=request.user)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(bookings, request)

        serializer = BookingSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


class HostBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsHost]

    def get(self, request):
        bookings = Booking.objects.filter(
            property__tenant=request.user.tenant
        )

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(bookings, request)

        serializer = BookingSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


class BookingApproveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsHost]

    def post(self, request, pk):
        booking = get_object_or_404(
            Booking,
            pk=pk,
            property__tenant=request.user.tenant
        )

        if booking.status != 'pending':
            return error_response("Already processed")

        booking.status = 'approved'
        booking.save()

        return success_response(message="Booking approved")


class BookingRejectView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsHost]

    def post(self, request, pk):
        booking = get_object_or_404(
            Booking,
            pk=pk,
            property__tenant=request.user.tenant
        )

        if booking.status != 'pending':
            return error_response("Already processed")

        booking.status = 'rejected'
        booking.save()

        return success_response(message="Booking rejected")