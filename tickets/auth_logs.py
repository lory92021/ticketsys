from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    AdminLog.objects.create(
        actor=user,
        target_user=user,
        action="LOGIN"
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    AdminLog.objects.create(
        actor=user,
        target_user=user,
        action="LOGOUT"
    )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    AdminLog.objects.create(
        actor=None,
        target_user=None,
        action="LOGIN FAILED",
        details=str(credentials)
    )
