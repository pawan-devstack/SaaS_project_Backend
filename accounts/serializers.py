from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Tenant, Property, Booking


# =========================
# REGISTER
# =========================
class RegisterSerializer(serializers.ModelSerializer):

    role = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']

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

        tenant = None

        # ✅ Host → create tenant
        if role == 'host':
            tenant = Tenant.objects.create(
                name=f"{validated_data['username']}'s workspace"
            )

        user = User(**validated_data)
        user.set_password(password)
        user.role = role
        user.tenant = tenant
        user.save()

        return user


# =========================
# 🔥 ADMIN CREATE (NEW)
# =========================
class AdminCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def validate(self, data):
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("Username already exists")
        return data

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)

        # 🔥 Make super admin
        user.is_superuser = True
        user.is_staff = True

        # role auto set hoga model me
        user.save()

        return user


# =========================
# LOGIN (JWT TOKEN)
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
            raise serializers.ValidationError("User is inactive")

        refresh = RefreshToken.for_user(user)

        return {
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'tenant': user.tenant.id if user.tenant else None
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }


# =========================
# PROPERTY
# =========================
class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ['id', 'title', 'price']

    def create(self, validated_data):
        user = self.context['request'].user

        if not user.tenant:
            raise serializers.ValidationError("User has no tenant")

        validated_data['tenant'] = user.tenant
        return super().create(validated_data)


# =========================
# BOOKING
# =========================
class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['id', 'property', 'check_in', 'check_out', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']

    def validate(self, data):
        if data['check_in'] >= data['check_out']:
            raise serializers.ValidationError("Invalid date range")

        user = self.context['request'].user

        # 🔐 Tenant security
        if user.tenant != data['property'].tenant:
            raise serializers.ValidationError("Tenant mismatch")

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)