from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Property, Booking, Tenant, User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    PropertySerializer,
    BookingSerializer,
    AdminCreateSerializer
)
from .permissions import IsHost, IsEndUser, IsSuperAdmin


# =========================
# 🔥 BOOKING CONFLICT CHECK
# =========================
def is_conflict(prop, check_in, check_out):
    return Booking.objects.filter(
        property=prop,
        status='approved'
    ).filter(
        Q(check_in__lt=check_out) & Q(check_out__gt=check_in)
    ).exists()

# =========================
# 🔥 TOGGLE USER STATUS
# =========================
class AdminToggleUserStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        user.is_active = not user.is_active
        user.save()

        return Response({
            "message": "User status updated",
            "is_active": user.is_active
        })


# =========================
# 🔥 CHANGE ROLE
# =========================
class AdminChangeRoleView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        role = request.data.get("role")

        if role not in ['host', 'user']:
            return Response({"error": "Invalid role"}, status=400)

        user.role = role
        user.save()

        return Response({"message": "Role updated"})


# =========================
# 🔥 DELETE USER
# =========================
class AdminDeleteUserView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def delete(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        if user.is_super_admin:
            return Response({"error": "Cannot delete admin"}, status=403)

        user.delete()
        return Response({"message": "User deleted"})


# =========================
# REGISTER
# =========================
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response({
            "message": "User registered",
            "username": user.username,
            "role": user.role
        }, status=status.HTTP_201_CREATED)


# =========================
# LOGIN
# =========================
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=200)


# =========================
# PROFILE
# =========================
class ProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "username": request.user.username,
            "role": request.user.role,
            "id": request.user.id,
            "tenant": request.user.tenant.name if request.user.tenant else None
        })


# =========================
# 🔥 ADMIN CREATE
# =========================
class CreateAdminView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        serializer = AdminCreateSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Admin created"}, status=201)

        return Response(serializer.errors, status=400)


# =========================
# 🔥 ADMIN USERS LIST
# =========================
class AdminUserListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        users = User.objects.all()

        data = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "tenant": u.tenant.name if u.tenant else None
            }
            for u in users
        ]

        return Response(data)


# =========================
# 🔥 ADMIN TENANTS LIST
# =========================
class AdminTenantListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        tenants = Tenant.objects.all()

        return Response([
            {"id": t.id, "name": t.name}
            for t in tenants
        ])


# =========================
# BASE VIEW
# =========================
class PropertyBaseView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_property(self, pk, user):
        if user.is_super_admin:
            return get_object_or_404(Property, pk=pk)
        return get_object_or_404(Property, pk=pk, tenant=user.tenant)


# =========================
# CREATE PROPERTY
# =========================
class PropertyCreateView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsHost]

    def post(self, request):
        serializer = PropertySerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=201)


# =========================
# LIST PROPERTY
# =========================
class PropertyListView(PropertyBaseView):

    def get(self, request):
        user = request.user

        if user.is_super_admin:
            props = Property.objects.all()
        else:
            props = Property.objects.filter(tenant=user.tenant)

        serializer = PropertySerializer(props, many=True)
        return Response(serializer.data)


# =========================
# DETAIL PROPERTY
# =========================
class PropertyDetailView(PropertyBaseView):

    def get(self, request, pk):
        prop = self.get_property(pk, request.user)
        serializer = PropertySerializer(prop)
        return Response(serializer.data)


# =========================
# UPDATE PROPERTY
# =========================
class PropertyUpdateView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsHost]

    def put(self, request, pk):
        prop = self.get_property(pk, request.user)

        serializer = PropertySerializer(prop, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


# =========================
# DELETE PROPERTY (SAFE)
# =========================
class PropertyDeleteView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsHost]

    def delete(self, request, pk):
        prop = self.get_property(pk, request.user)

        if prop.tenant != request.user.tenant:
            return Response({"error": "Not allowed"}, status=403)

        prop.delete()
        return Response({"message": "Deleted successfully"})


# =========================
# CREATE BOOKING
# =========================
class BookingCreateView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsEndUser]

    def post(self, request, property_id):
        prop = self.get_property(property_id, request.user)

        check_in = request.data.get("check_in")
        check_out = request.data.get("check_out")

        # 🔥 conflict check
        if is_conflict(prop, check_in, check_out):
            return Response(
                {"error": "Property already booked for these dates"},
                status=400
            )

        serializer = BookingSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        serializer.save(property=prop)
        return Response(serializer.data, status=201)


# =========================
# USER BOOKINGS
# =========================
class UserBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(user=request.user)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)


# =========================
# HOST BOOKINGS
# =========================
class HostBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsHost]

    def get(self, request):
        bookings = Booking.objects.filter(property__tenant=request.user.tenant)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)


# =========================
# APPROVE BOOKING
# =========================
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
            return Response({"error": "Already processed"}, status=400)

        booking.status = 'approved'
        booking.save()

        return Response({"message": "Booking approved"})


# =========================
# REJECT BOOKING
# =========================
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
            return Response({"error": "Already processed"}, status=400)

        booking.status = 'rejected'
        booking.save()

        return Response({"message": "Booking rejected"})