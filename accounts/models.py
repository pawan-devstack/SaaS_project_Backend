from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError


# =========================
# 🔥 Base Model
# =========================
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


# =========================
# Tenant Model
# =========================
class Tenant(BaseModel):
    name = models.CharField(max_length=255, unique=True)

    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tenants'
    )

    def __str__(self):
        return self.name


# =========================
# Custom User Model
# =========================
class User(AbstractUser, BaseModel):

    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('host', 'Host'),
        ('user', 'End User'),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',
        db_index=True
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users'
    )

    # =========================
    # Role Helpers
    # =========================
    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_host(self):
        return self.role == 'host'

    @property
    def is_user(self):
        return self.role == 'user'

    # =========================
    # Validation
    # =========================
    def clean(self):

        if self.is_superuser:
            self.tenant = None
            return

        if self.role in ['host', 'user'] and not self.tenant:
            raise ValidationError("Host/User must belong to a tenant")

    def save(self, *args, **kwargs):
        if not kwargs.pop('skip_validation', False):
            self.full_clean()

        if self.is_superuser:
            self.role = 'super_admin'
            self.tenant = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} - {self.role}"


# =========================
# Property Model
# =========================
class Property(BaseModel):

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('blocked', 'Blocked'),
    )

    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='properties/', null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='properties'
    )

    host = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='host_properties'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_properties'
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_properties'
    )

    def clean(self):
        if not self.tenant:
            raise ValidationError("Property must belong to a tenant")

        if not self.host or self.host.role != 'host':
            raise ValidationError("Only host can own property")

        if self.host.tenant != self.tenant:
            raise ValidationError("Host and Property tenant mismatch")

    def __str__(self):
        return self.title

    class Meta:
        indexes = [
            models.Index(fields=['tenant']),
            models.Index(fields=['host']),
            models.Index(fields=['status']),
        ]


# =========================
# Booking Model
# =========================
class Booking(BaseModel):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    check_in = models.DateField()
    check_out = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    cancelled_at = models.DateTimeField(null=True, blank=True)

    def clean(self):

        if self.check_in >= self.check_out:
            raise ValidationError("Check-out must be after check-in")

        if self.user.tenant != self.property.tenant:
            raise ValidationError("User and Property must belong to same tenant")

        overlapping = Booking.objects.filter(
            property=self.property,
            check_in__lt=self.check_out,
            check_out__gt=self.check_in,
            status='approved',
            is_deleted=False
        ).exclude(id=self.id)

        if overlapping.exists():
            raise ValidationError("Property already booked for selected dates")

    def __str__(self):
        return f"{self.user.username} → {self.property.title}"

    class Meta:
        indexes = [
            models.Index(fields=['property', 'status']),
            models.Index(fields=['check_in', 'check_out']),
        ]