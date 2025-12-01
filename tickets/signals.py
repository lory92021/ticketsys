from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import Ticket, TicketAttachment, AdminLog
from .utils.audit import log_change
from .utils.mailer import send_ticket_email



# ============================================================
# ==================== TICKET: PRE SAVE ======================
# ============================================================

@receiver(pre_save, sender=Ticket)
def ticket_pre_save(sender, instance, **kwargs):
    """
    Salva lo stato precedente del ticket per il confronto PRIMA → DOPO
    """
    if not instance.pk:
        return

    try:
        old = Ticket.objects.get(pk=instance.pk)

        instance._old_status = old.status
        instance._old_priority = old.priority
        instance._old_assigned_to = old.assigned_to
        instance._old_title = old.title
        instance._old_description = old.description

    except Ticket.DoesNotExist:
        pass


# ============================================================
# ==================== TICKET: POST SAVE =====================
# ============================================================

@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):

    # ✅ CREAZIONE TICKET
    if created:
        log_change(
            actor=instance.created_by,
            action="TICKET CREATE",
            ticket=instance,
            extra=f"Titolo: {instance.title}",
        )
        return

    # ✅ CAMBIO STATO
    if hasattr(instance, "_old_status") and instance._old_status != instance.status:
        log_change(
            actor=instance.created_by,
            action="TICKET STATUS CHANGE",
            ticket=instance,
            field_name="status",
            old_value=instance._old_status,
            new_value=instance.status,
        )

    # ✅ CAMBIO PRIORITÀ
    if hasattr(instance, "_old_priority") and instance._old_priority != instance.priority:
        log_change(
            actor=instance.created_by,
            action="TICKET PRIORITY CHANGE",
            ticket=instance,
            field_name="priority",
            old_value=instance._old_priority,
            new_value=instance.priority,
        )

    # ✅ CAMBIO ASSEGNAZIONE
    if hasattr(instance, "_old_assigned_to") and instance._old_assigned_to != instance.assigned_to:
        log_change(
            actor=instance.created_by,
            action="TICKET ASSIGNED CHANGE",
            ticket=instance,
            target_user=instance.assigned_to,
            field_name="assigned_to",
            old_value=(
                instance._old_assigned_to.username
                if instance._old_assigned_to else "Nessuno"
            ),
            new_value=(
                instance.assigned_to.username
                if instance.assigned_to else "Nessuno"
            ),
        )

    # ✅ CAMBIO TITOLO
    if hasattr(instance, "_old_title") and instance._old_title != instance.title:
        log_change(
            actor=instance.created_by,
            action="TICKET TITLE CHANGE",
            ticket=instance,
            field_name="title",
            old_value=instance._old_title,
            new_value=instance.title,
        )

    # ✅ CAMBIO DESCRIZIONE
    if hasattr(instance, "_old_description") and instance._old_description != instance.description:
        log_change(
            actor=instance.created_by,
            action="TICKET DESCRIPTION CHANGE",
            ticket=instance,
            field_name="description",
            old_value="(testo precedente)",
            new_value="(testo aggiornato)",
        )


# ============================================================
# ==================== TICKET: DELETE ========================
# ============================================================

@receiver(post_delete, sender=Ticket)
def ticket_post_delete(sender, instance, **kwargs):
    log_change(
        actor=instance.created_by,
        target_user=instance.created_by,
        action="TICKET DELETE",
        ticket=None,
        extra=f"Titolo: {instance.title}",
    )


# ============================================================
# ==================== USER: PRE SAVE ========================
# ============================================================

@receiver(pre_save, sender=User)
def user_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old = User.objects.get(pk=instance.pk)

        instance._old_username = old.username
        instance._old_email = old.email
        instance._old_is_staff = old.is_staff

    except User.DoesNotExist:
        pass


# ============================================================
# ==================== USER: POST SAVE =======================
# ============================================================

@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):

    from django.urls import reverse
    from django.conf import settings
    from django.contrib.auth.models import User
    from .utils.mailer import send_ticket_email, build_ticket_email_html
    from .utils.audit import log_change

    # =========================================================
    # ✅ 1. CREAZIONE TICKET → LOG + MAIL A OPERATORI + ADMIN
    # =========================================================
    if created:
        # -------- LOG CREAZIONE --------
        log_change(
            actor=instance.created_by,
            action="TICKET CREATE",
            ticket=instance,
            extra=f"Titolo: {instance.title}",
        )

        # -------- EMAIL --------
        recipients = list(
            User.objects.filter(groups__name__in=["operator", "admin"])
            .exclude(email="")
            .values_list("email", flat=True)
        )

        if recipients:
            ticket_url = f"{settings.SITE_URL}{reverse('ticket_detail', args=[instance.id])}"

            subject = f"[NUOVO TICKET] #{instance.id} - {instance.title}"

            text_message = (
                f"È stato creato un nuovo ticket.\n\n"
                f"Titolo: {instance.title}\n"
                f"Creato da: {instance.created_by.username}\n\n"
                f"Apri il ticket: {ticket_url}"
            )

            html_message = build_ticket_email_html(
                title="Nuovo Ticket Creato",
                message=f"""
                    È stato creato un nuovo ticket.<br><br>
                    <b>Titolo:</b> {instance.title}<br>
                    <b>Creato da:</b> {instance.created_by.username}<br>
                """,
                ticket_url=ticket_url,
                button_text="Apri Ticket"
            )

            send_ticket_email(
                subject=subject,
                text_content=text_message,
                html_content=html_message,
                recipient_list=recipients,
                actor=instance.created_by,   # ✅ chi ha causato l’invio
                ticket=instance              # ✅ ticket collegato
            )

        return   # ⛔ IMPORTANTE: impedisce che entri negli altri controlli

    # =========================================================
    # ✅ 2. CAMBIO STATO
    # =========================================================
    if hasattr(instance, "_old_status") and instance._old_status != instance.status:
        log_change(
            actor=instance.assigned_to or instance.created_by,
            action="TICKET STATUS CHANGE",
            ticket=instance,
            field_name="status",
            old_value=instance._old_status,
            new_value=instance.status,
        )

    # =========================================================
    # ✅ 3. CAMBIO PRIORITÀ
    # =========================================================
    if hasattr(instance, "_old_priority") and instance._old_priority != instance.priority:
        log_change(
            actor=instance.assigned_to or instance.created_by,
            action="TICKET PRIORITY CHANGE",
            ticket=instance,
            field_name="priority",
            old_value=instance._old_priority,
            new_value=instance.priority,
        )

    # =========================================================
    # ✅ 4. CAMBIO ASSEGNAZIONE → SOLO LOG (EMAIL LA GESTISCE LA VIEW)
    # =========================================================
    if hasattr(instance, "_old_assigned_to") and instance._old_assigned_to != instance.assigned_to:
        log_change(
            actor=instance.assigned_to,
            target_user=instance.assigned_to,
            action="TICKET ASSIGNED CHANGE",
            ticket=instance,
            field_name="assigned_to",
            old_value=(
                instance._old_assigned_to.username
                if instance._old_assigned_to else "Nessuno"
            ),
            new_value=(
                instance.assigned_to.username
                if instance.assigned_to else "Nessuno"
            ),
        )

    # =========================================================
    # ✅ 5. CAMBIO TITOLO
    # =========================================================
    if hasattr(instance, "_old_title") and instance._old_title != instance.title:
        log_change(
            actor=instance.assigned_to or instance.created_by,
            action="TICKET TITLE CHANGE",
            ticket=instance,
            field_name="title",
            old_value=instance._old_title,
            new_value=instance.title,
        )

    # =========================================================
    # ✅ 6. CAMBIO DESCRIZIONE
    # =========================================================
    if hasattr(instance, "_old_description") and instance._old_description != instance.description:
        log_change(
            actor=instance.assigned_to or instance.created_by,
            action="TICKET DESCRIPTION CHANGE",
            ticket=instance,
            field_name="description",
            old_value="(testo precedente)",
            new_value="(testo aggiornato)",
        )


# ============================================================
# ==================== USER: DELETE ==========================
# ============================================================

@receiver(post_delete, sender=User)
def user_post_delete(sender, instance, **kwargs):
    log_change(
        actor=instance,
        target_user=instance,
        action="USER DELETE",
        extra=f"Username: {instance.username}",
    )


# ============================================================
# ==================== ATTACHMENT: SAVE ======================
# ============================================================

@receiver(post_save, sender=TicketAttachment)
def attachment_post_save(sender, instance, created, **kwargs):
    if created:
        log_change(
            actor=instance.uploaded_by,
            target_user=instance.uploaded_by,
            action="ATTACHMENT UPLOAD",
            ticket=instance.ticket,
            extra=f"File: {instance.file_name}",
        )


# ============================================================
# ==================== ATTACHMENT: DELETE ====================
# ============================================================

@receiver(post_delete, sender=TicketAttachment)
def attachment_post_delete(sender, instance, **kwargs):
    log_change(
        actor=instance.uploaded_by,
        target_user=instance.uploaded_by,
        action="ATTACHMENT DELETE",
        ticket=instance.ticket,
        extra=f"File: {instance.file_name}",
    )
