from django.db import models
from django.contrib.auth.models import User


# ============================================================
# ========================== TICKET ==========================
# ============================================================

class Ticket(models.Model):

    PRIORITY_CHOICES = [
        ('low', 'Bassa'),
        ('medium', 'Media'),
        ('high', 'Alta'),
    ]

    STATUS_CHOICES = [
        ('open', 'Aperto'),
        ('in_progress', 'In lavorazione'),
        ('closed', 'Chiuso'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tickets_created'
    )

    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tickets_assigned'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.id}] {self.title}"


# ============================================================
# ========================= MESSAGE ==========================
# ============================================================

class Message(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Messaggio di {self.sender.username} - Ticket {self.ticket.id}"


# ============================================================
# ========================= ADMIN LOG ========================
# ============================================================

class AdminLog(models.Model):

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_actions"
    )

    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affected_by_logs"
    )

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    action = models.CharField(max_length=100)

    details = models.TextField(
        null=True,   # ✅ FONDAMENTALE
        blank=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.actor} - {self.action} - {self.timestamp}"


# ============================================================
# ====================== TICKET ATTACHMENT ===================
# ============================================================

class TicketAttachment(models.Model):

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="attachments"
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    file_name = models.CharField(max_length=255)

    # ✅ SALVIAMO SOLO IL PATH RELATIVO (COME AVEVAMO DECISO)
    file_path = models.TextField()

    file_size = models.IntegerField()
    mime_type = models.CharField(max_length=100)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name
