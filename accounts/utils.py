from django.core.signing import TimestampSigner
from django.core.mail import send_mail
from django.conf import settings

signer = TimestampSigner()


def send_verification_email(user):
    token = signer.sign(user.email)

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
    verification_link = f"{frontend_url}/verify/{token}"

    print("EMAIL LINK:", verification_link)  # 🔥 debug

    send_mail(
        subject="Verify your email",
        message=f"Click the link to verify your email:\n{verification_link}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,  # 🔥 important
    )


def send_reset_password_email(user):
    token = signer.sign(user.email)

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{frontend_url}/reset-password/{token}"

    print("RESET LINK:", reset_link)

    send_mail(
        subject="Reset your password",
        message=f"Click to reset password:\n{reset_link}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        fail_silently=False,
    )