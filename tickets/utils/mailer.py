from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth.models import User

from tickets.models import AdminLog


def send_ticket_email(
    *,
    subject,
    text_content,
    html_content,
    recipient_list,
    actor=None,
    target_user=None,
    ticket=None
):
    """
    Invia email HTML + testo e LOGGA nel DB l'invio.
    """

    if not recipient_list:
        return

    # ✅ INVIO EMAIL
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list
    )

    email.attach_alternative(html_content, "text/html")
    email.send()

    # ✅ LOG DATABASE (UNO PER OGNI DESTINATARIO)
    for recipient in recipient_list:

        target = None
        try:
            target = User.objects.get(email=recipient)
        except User.DoesNotExist:
            target = None

        AdminLog.objects.create(
            actor=actor,                     # chi ha causato l'evento
            target_user=target or target_user,
            ticket=ticket,
            action="EMAIL SENT",
            details=(
                f"Oggetto: {subject}\n"
                f"Destinatario: {recipient}"
            )
        )


def build_ticket_email_html(title, message, ticket_url, button_text):
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; background:#f4f6f9; padding:30px;">
            <div style="max-width:600px; margin:auto; background:white; padding:30px; border-radius:8px;">
                <h2 style="color:#2c3e50;">{title}</h2>
                <p style="font-size:15px; color:#333;">{message}</p>

                <div style="text-align:center; margin:40px 0;">
                    <a href="{ticket_url}"
                       style="background:#0d6efd; color:white; padding:14px 28px;
                              text-decoration:none; border-radius:6px; font-weight:bold;">
                        {button_text}
                    </a>
                </div>

                <hr>
                <p style="font-size:12px; color:#888;">
                    TicketSys – Sistema di gestione ticket<br>
                    Questa email è generata automaticamente.
                </p>
            </div>
        </body>
    </html>
    """
