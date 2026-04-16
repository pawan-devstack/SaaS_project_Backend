from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.tokens import RefreshToken
import uuid

from .utils import send_verification_email
from .models import User, Tenant, Property, Booking


# =========================
# REGISTER
# =========================
class RegisterSerializer(serializers.ModelSerializer):

    role = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    tenant_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role', 'tenant_id']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_role(self, value):
        if value not in dict(User.ROLE_CHOICES):
            raise serializers.ValidationError("Invalid role")

        if value == 'super_admin':
            raise serializers.ValidationError("Cannot register as super admin")

        return value

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop('password')
        role = validated_data.pop('role')
        tenant_id = validated_data.pop('tenant_id', None)

        tenant = None

        # 🏠 HOST → CREATE TENANT
        if role == "host":
            tenant = Tenant.objects.create(
                name=f"{validated_data['username']}'s Workspace"
            )

        # 👤 USER → JOIN TENANT
        elif role == "user":
            if not tenant_id:
                raise serializers.ValidationError("Tenant is required")

            tenant = Tenant.objects.filter(id=tenant_id).first()
            if not tenant:
                raise serializers.ValidationError("Invalid tenant")

        # 👑 ADMIN → no tenant

        user = User(**validated_data)
        user.set_password(password)
        user.role = role
        user.tenant = tenant
        user.is_active = False
        user.save()

        # 🔥 EMAIL SEND
        try:
            send_verification_email(user)
        except Exception as e:
            print("Email error:", e)

        return user


# =========================
# ADMIN CREATE
# =========================
class AdminCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return user


# =========================
# LOGIN
# =========================
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(
            username=data['username'],
            password=data['password']
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            raise serializers.ValidationError("Please verify your email")

        refresh = RefreshToken.for_user(user)

        return {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'tenant': user.tenant.id if user.tenant else None,
                'is_super_admin': user.is_super_admin
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }


# =========================
# PROPERTY (HOST)
# =========================
class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ['id', 'title', 'price', 'status', 'image']
        read_only_fields = ['status']

    def create(self, validated_data):
        user = self.context['request'].user

        if not user.is_host and not user.is_super_admin:
            raise serializers.ValidationError("Only host can create property")

        validated_data['tenant'] = user.tenant
        validated_data['host'] = user
        validated_data['created_by'] = user

        return super().create(validated_data)

    def update(self, instance, validated_data):
        user = self.context['request'].user

        if instance.host != user and not user.is_super_admin:
            raise serializers.ValidationError("You can update only your property")

        return super().update(instance, validated_data)


# =========================
# ADMIN PROPERTY
# =========================
class AdminPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ['id', 'title', 'price', 'status']

    def update(self, instance, validated_data):
        user = self.context['request'].user

        if not user.is_super_admin:
            raise serializers.ValidationError("Only admin can update property")

        return super().update(instance, validated_data)


# =========================
# BOOKING
# =========================
class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['id', 'property', 'check_in', 'check_out', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']

    def validate(self, data):
        request = self.context['request']
        prop = data.get('property')

        if not prop:
            raise serializers.ValidationError("Property required")

        if data['check_in'] >= data['check_out']:
            raise serializers.ValidationError("Invalid date range")

        # Tenant security
        if request.user.tenant != prop.tenant:
            raise serializers.ValidationError("Tenant mismatch")

        # Property status
        if prop.status != 'active':
            raise serializers.ValidationError("Property not available")

        # 🔥 Overlapping booking check
        overlap = Booking.objects.filter(
            property=prop,
            check_in__lt=data['check_out'],
            check_out__gt=data['check_in'],
            status='approved',
            is_deleted=False
        )

        if overlap.exists():
            raise serializers.ValidationError("Property already booked")

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)