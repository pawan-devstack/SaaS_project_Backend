from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
import logging
import uuid
from django.utils import timezone
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.contrib.auth.password_validation import validate_password

from .models import Property, Booking, Tenant, User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    PropertySerializer,
    BookingSerializer,
    AdminCreateSerializer,
    AdminPropertySerializer
)
from .utils import send_verification_email, send_reset_password_email
from .permissions import IsHost, IsEndUser, IsSuperAdmin
from .models import Tenant

logger = logging.getLogger(__name__)
signer = TimestampSigner()


class PublicTenantListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tenants = Tenant.objects.filter(is_deleted=False)

        data = [
            {
                "id": t.id,
                "name": t.name,
            }
            for t in tenants
        ]

        return Response({
            "success": True,
            "data": data
        })

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
# AUTH
# =========================
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(
            data=request.data,
            context={'request': request}
        )
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
        users = User.objects.filter(is_deleted=False)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(users, request)

        data = [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "tenant": u.tenant.name if u.tenant else None,
            "is_active": u.is_active
        } for u in result_page]

        return paginator.get_paginated_response(data)


class AdminTenantListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        tenants = Tenant.objects.filter(is_deleted=False)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(tenants, request)

        data = [
            {"id": t.id, "name": t.name} 
            for t in result_page
            ]
        return paginator.get_paginated_response(data)


class AdminToggleUserStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id, is_deleted=False)

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
        user = get_object_or_404(User, id=user_id, is_deleted=False)

        if user.is_super_admin:
            return error_response("Cannot delete super admin", 403)

        user.is_deleted = True
        user.save()

        return success_response(message="User deleted (soft)")


class AdminChangeRoleView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id, is_deleted=False)
        role = request.data.get("role")

        if role not in ['host', 'user']:
            return error_response("Invalid role")

        if role == 'host' and not user.tenant:
            user.tenant = Tenant.objects.create(
                name=f"{user.username}-{uuid.uuid4().hex[:6]}",
                created_by=request.user
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
            return get_object_or_404(Property, pk=pk, is_deleted=False)

        if user.is_host:
            return get_object_or_404(
                Property,
                pk=pk,
                tenant=user.tenant,
                host=user,
                is_deleted=False
            )

        return get_object_or_404(
            Property,
            pk=pk,
            tenant=user.tenant,
            is_deleted=False
        )


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
    def get(self, request):
        user = request.user

        if user.is_super_admin:
            queryset = Property.objects.filter(is_deleted=False)
        elif user.is_host:
            queryset = Property.objects.filter(host=user, is_deleted=False)
        else:
            queryset = Property.objects.filter(tenant=user.tenant, is_deleted=False)

        queryset = queryset.select_related('tenant', 'host')

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(title__icontains=search)

        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")

        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        sort = request.query_params.get("sort")
        if sort in ["price", "-price"]:
            queryset = queryset.order_by(sort)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(queryset, request)

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

        if prop.host != request.user and not request.user.is_super_admin:
            return error_response("Not allowed", 403)

        serializer = PropertySerializer(
            prop,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return success_response(serializer.data, "Updated")


class PropertyDeleteView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsHost]

    def delete(self, request, pk):
        prop = self.get_property(pk, request.user)

        if prop.host != request.user and not request.user.is_super_admin:
            return error_response("Not allowed", 403)

        prop.is_deleted = True
        prop.save()

        return success_response(message="Property deleted (soft)")


# =========================
# ADMIN PROPERTY CONTROL
# =========================
class AdminPropertyUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, pk):
        prop = get_object_or_404(Property, pk=pk, is_deleted=False)

        serializer = AdminPropertySerializer(
            prop,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return success_response(serializer.data, "Property updated by admin")


class AdminDashboardStatsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        data = {
            # 👤 Only normal users
            "total_users": User.objects.filter(
                role="user",
                is_deleted=False
            ).count(),

            # 🏠 Only hosts
            "total_hosts": User.objects.filter(
                role="host",
                is_deleted=False
            ).count(),

            # 👑 Only admins (optional)
            "total_admins": User.objects.filter(
                role="super_admin",
                is_deleted=False
            ).count(),

            "total_properties": Property.objects.filter(is_deleted=False).count(),
            "total_bookings": Booking.objects.filter(is_deleted=False).count(),
            "pending_bookings": Booking.objects.filter(
                status='pending',
                is_deleted=False
            ).count(),
        }

        return success_response(data)


# =========================
# BOOKING
# =========================
class BookingCreateView(PropertyBaseView):
    permission_classes = [IsAuthenticated, IsEndUser]

    def post(self, request, property_id):
        prop = self.get_property(property_id, request.user)

        if prop.host == request.user:
            return error_response("You cannot book your own property")

        serializer = BookingSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        serializer.save(property=prop)

        logger.info(f"{request.user.username} created booking")
        return success_response(serializer.data, "Booking created")


class UserBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(user=request.user, is_deleted=False)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(bookings, request)

        serializer = BookingSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


class HostBookingListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsHost]

    def get(self, request):
        bookings = Booking.objects.filter(property__host=request.user, is_deleted=False)

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
            property__host=request.user,
            is_deleted=False
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
            property__host=request.user,
            is_deleted=False
        )

        if booking.status != 'pending':
            return error_response("Already processed")

        booking.status = 'rejected'
        booking.save()

        return success_response(message="Booking rejected")


class BookingCancelView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsEndUser]

    def post(self, request, pk):
        booking = get_object_or_404(
            Booking,
            pk=pk,
            user=request.user,
            is_deleted=False
        )

        if booking.status in ['cancelled', 'rejected']:
            return error_response("Cannot cancel this booking")

        booking.status = 'cancelled'
        booking.cancelled_at = timezone.now()
        booking.save()

        return success_response(message="Booking cancelled")


# =========================
# EMAIL VERIFICATION
# =========================
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            email = signer.unsign(token, max_age=3600)
            user = User.objects.get(email=email)

            if user.is_active:
                return success_response(message="Already verified")

            user.is_active = True
            user.save()

            return success_response(message="Email verified successfully")

        except SignatureExpired:
            return error_response("Link expired")

        except BadSignature:
            return error_response("Invalid token")

        except User.DoesNotExist:
            return error_response("User not found", 404)


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        try:
            user = User.objects.get(email=email)

            if not user.is_active:
                send_verification_email(user)

        except User.DoesNotExist:
            pass

        return Response({"message": "If email exists, verification sent"})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        try:
            user = User.objects.get(email=email)
            send_reset_password_email(user)
        except User.DoesNotExist:
            pass

        return Response({"message": "If email exists, reset link sent"})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, token):
        new_password = request.data.get("password")

        try:
            validate_password(new_password)

            email = signer.unsign(token, max_age=3600)
            user = User.objects.get(email=email)

            user.set_password(new_password)
            user.save()

            return success_response(message="Password reset successful")

        except SignatureExpired:
            return error_response("Link expired")

        except BadSignature:
            return error_response("Invalid token")

        except Exception as e:
            return error_response(str(e))
        
class HostDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsHost]

    def get(self, request):
        user = request.user

        # 🏠 properties of host
        properties = Property.objects.filter(
            host=user,
            is_deleted=False
        )

        # 📅 bookings for host properties
        bookings = Booking.objects.filter(
            property__host=user,
            is_deleted=False
        )

        total_properties = properties.count()
        total_bookings = bookings.count()

        # 💰 earnings (safe way)
        total_earnings = sum([
            getattr(b, "amount", 0) or 0 for b in bookings
        ])

        # 📌 recent bookings
        recent_bookings = bookings.order_by("-id")[:5]

        data = {
            "total_properties": total_properties,
            "total_bookings": total_bookings,
            "total_earnings": total_earnings,
            "recent_bookings": [
                {
                    "id": b.id,
                    "property_name": b.property.title,
                    "user_name": b.user.username,
                    "date": str(b.created_at.date()) if b.created_at else "",
                    "status": b.status,
                }
                for b in recent_bookings
            ],
        }

        return success_response(data)        