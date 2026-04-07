from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError


# =========================
# Tenant Model
# =========================
class Tenant(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =========================
# Property Model
# =========================
class Property(models.Model):
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='properties'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Validation
    def clean(self):
        if not self.tenant:
            raise ValidationError("Property must belong to a tenant")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# =========================
# Custom User Model
# =========================
class User(AbstractUser):

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        if self.role == 'host' and not self.tenant:
            raise ValidationError("Host must belong to a tenant")

        if self.role == 'user' and self.tenant is None:
            pass  # allow for now (can enforce later)

    # =========================
    # Save override
    # =========================
    def save(self, *args, **kwargs):
        if self.is_superuser and self.role != 'super_admin':
            self.role = 'super_admin'

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} - {self.role}"


# =========================
# Booking Model
# =========================
class Booking(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
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

    created_at = models.DateTimeField(auto_now_add=True)

    # =========================
    # Validation
    # =========================
    def clean(self):
        if self.check_in >= self.check_out:
            raise ValidationError("Check-out must be after check-in")

        # 🔥 SaaS Security Check
        if self.user.tenant != self.property.tenant:
            raise ValidationError("User and Property must belong to same tenant")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.property.title}"