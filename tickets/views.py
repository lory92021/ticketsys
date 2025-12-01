from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.db.models import Q 
from .models import Ticket, Message, AdminLog, TicketAttachment
from django.http import FileResponse, Http404
from django.conf import settings
from .forms import TicketForm, MessageForm, CustomRegisterForm
from django.utils.timezone import now
from django.db.models import Count


import logging, mimetypes, os, json, datetime    

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Logger per scrivere nel file admin_actions.log
admin_logger = logging.getLogger("admin_actions")

# Funzione per i filtri

def apply_ticket_filters(request, queryset):
    priority = request.GET.getlist("priority")
    status = request.GET.getlist("status")
    user = request.GET.get("user")
    title = request.GET.get("title")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if priority:
        queryset = queryset.filter(priority__in=priority)

    if status:
        queryset = queryset.filter(status__in=status)

    if user:
        queryset = queryset.filter(created_by__id=user)

    if title:
        queryset = queryset.filter(title__icontains=title)

    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    return queryset


# =========================================================
#                   HELPER PER I RUOLI
# =========================================================

def is_operator_or_admin(user):
    return is_operator(user) or is_admin(user)


def is_operator(user):
    return user.groups.filter(name="operator").exists()

def is_admin(user):
    return user.is_superuser or user.is_staff or user.groups.filter(name="admin").exists()


# =========================================================
#                     AUTENTICAZIONE
# =========================================================

def register(request):
    user_group, _ = Group.objects.get_or_create(name="user")

    if request.method == "POST":
        form = CustomRegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password1"]

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.groups.add(user_group)
            user.save()

            login(request, user)
            return redirect("ticket_list")

    else:
        form = CustomRegisterForm()

    return render(request, "register.html", {"form": form})


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("ticket_list")
        else:
            return render(request, "login.html", {"error": "Credenziali non valide"})

    return render(request, "login.html")


@login_required
def user_logout(request):
    logout(request)
    return redirect("login")


# =========================================================
#                    LISTA TICKET
# =========================================================

@login_required
def ticket_list(request):
    if is_operator(request.user) or is_admin(request.user):
        tickets = Ticket.objects.all().order_by("-created_at")
    else:
        tickets = Ticket.objects.filter(created_by=request.user).order_by("-created_at")

    tickets = apply_ticket_filters(request, tickets)

    users = User.objects.all()

    return render(request, "tickets/ticket_list.html", {
        "tickets": tickets,
        "page_title": "Tutti i ticket",
        "users": users,
        "filters": request.GET
    })


@login_required
def my_tickets(request):
    tickets = Ticket.objects.filter(created_by=request.user).order_by("-created_at")
    return render(request, "tickets/ticket_list.html", {
        "tickets": tickets,
        "page_title": "I miei ticket"
    })


# =========================================================
#                     OPERATOR
# =========================================================

@login_required
@user_passes_test(is_operator)
def operator_open(request):
    tickets = Ticket.objects.filter(status="open", assigned_to__isnull=True).order_by("-created_at")
    tickets = apply_ticket_filters(request, tickets)

    users = User.objects.all()

    return render(request, "tickets/operator_open.html", {
        "tickets": tickets,
        "active_tab": "open",
        "users": users,
        "filters": request.GET
    })


@login_required
@user_passes_test(is_operator)
def operator_assigned(request):
    tickets = Ticket.objects.filter(assigned_to=request.user).order_by("-created_at")
    tickets = apply_ticket_filters(request, tickets)

    users = User.objects.all()

    return render(request, "tickets/operator_assigned.html", {
        "tickets": tickets,
        "active_tab": "assigned",
        "users": users,
        "filters": request.GET
    })


@login_required
@user_passes_test(is_operator)
def operator_dashboard(request):
    tickets = Ticket.objects.filter(assigned_to=request.user).order_by("-created_at")
    tickets = apply_ticket_filters(request, tickets)

    users = User.objects.all()

    return render(request, "tickets/operator_dashboard.html", {
        "tickets": tickets,
        "active_tab": "assigned",
        "users": users,
        "filters": request.GET
    })

# =========================================================
#                 ADMIN DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    tickets = Ticket.objects.all().order_by("-created_at")
    tickets = apply_ticket_filters(request, tickets)

    users = User.objects.all()

    return render(request, "tickets/admin_dashboard.html", {
        "tickets": tickets,
        "users": users,
        "filters": request.GET,
        "total_open": tickets.filter(status="open").count(),
        "total_in_progress": tickets.filter(status="in_progress").count(),
        "total_closed": tickets.filter(status="closed").count(),
    })


# =========================================================
#                TICKET DETTAGLIO + MESSAGGI
# =========================================================

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # permessi di accesso al ticket
    if not (
        ticket.created_by == request.user or
        is_operator(request.user) or
        is_admin(request.user)
    ):
        return redirect("ticket_list")

    operators = User.objects.filter(groups__name="operator")
    selected_operator_id = ticket.assigned_to.id if ticket.assigned_to else None

    # =========================================================
    # ✅ INVIO MESSAGGIO + UPLOAD ALLEGATO SICURO
    # =========================================================
    if request.method == "POST":

        text = request.POST.get("text", "").strip()

        # ✅ invio messaggio
        if text:
            Message.objects.create(
                ticket=ticket,
                sender=request.user,
                text=text
            )

        # ✅ gestione upload allegato
        if request.FILES.get("attachment"):
            f = request.FILES["attachment"]
            import os

            ext = os.path.splitext(f.name)[1].lower()

            # --- WHITELIST ESTENSIONI ---
            ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

            if ext not in ALLOWED_EXTENSIONS:
                messages.error(
                    request,
                    "Formato non consentito. Sono ammessi solo PDF, JPG e PNG."
                )
                return redirect("ticket_detail", ticket_id=ticket.id)

            if f.size > MAX_FILE_SIZE:
                messages.error(
                    request,
                    "File troppo grande. Dimensione massima: 10MB."
                )
                return redirect("ticket_detail", ticket_id=ticket.id)

            # ✅ cartella RELATIVA per ticket
            relative_dir = f"ticket_{ticket.id}"
            absolute_dir = os.path.join(settings.SECURE_UPLOAD_ROOT, relative_dir)
            os.makedirs(absolute_dir, exist_ok=True)

            relative_path = os.path.join(relative_dir, f.name)
            absolute_path = os.path.join(settings.SECURE_UPLOAD_ROOT, relative_path)

            with open(absolute_path, "wb+") as dest:
                for chunk in f.chunks():
                    dest.write(chunk)

            TicketAttachment.objects.create(
                ticket=ticket,
                uploaded_by=request.user,
                file_name=f.name,
                file_path=relative_path,   # ✅ SOLO RELATIVO NEL DB
                file_size=f.size,
                mime_type=f.content_type
            )


            messages.success(request, "Allegato caricato correttamente.")

        return redirect("ticket_detail", ticket_id=ticket.id)

    # =========================================================
    # ✅ VISUALIZZAZIONE TICKET
    # =========================================================
    return render(request, "tickets/ticket_detail.html", {
        "ticket": ticket,
        "operators": operators,
        "selected_operator_id": selected_operator_id,
        "is_operator": is_operator(request.user),
        "is_admin": is_admin(request.user),
        "messages": ticket.messages.order_by("created_at"),
        "attachments": ticket.attachments.all()
    })

# =========================================================
#               WORKFLOW TICKET (OPERATOR)
# =========================================================

@login_required
@user_passes_test(is_operator)
def ticket_assign(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.status == "open":
        ticket.assigned_to = request.user
        ticket.status = "in_progress"
        ticket.save()

        from django.urls import reverse
        from django.conf import settings
        from .utils.mailer import send_ticket_email, build_ticket_email_html

        ticket_url = f"{settings.SITE_URL}{reverse('ticket_detail', args=[ticket.id])}"

        subject = f"[TICKET ASSEGNATO] #{ticket.id}"

        text_message = (
            f"Ti è stato assegnato un ticket.\n\n"
            f"Titolo: {ticket.title}\n\n"
            f"Apri il ticket: {ticket_url}"
        )

        html_message = build_ticket_email_html(
            title="Nuovo Ticket Assegnato",
            message=f"""
                Ti è stato assegnato un nuovo ticket.<br><br>
                <b>Titolo:</b> {ticket.title}<br>
                <b>Creato da:</b> {ticket.created_by.username}<br>
            """,
            ticket_url=ticket_url,
            button_text="Gestisci Ticket"
        )

        send_ticket_email(
            subject=subject,
            text_content=text_message,
            html_content=html_message,
            recipient_list=[request.user.email],
            actor=request.user,          # ✅ chi assegna
            target_user=request.user,   # ✅ destinatario
            ticket=ticket
        )


    return redirect("ticket_detail", ticket_id=ticket.id)


@login_required
@user_passes_test(is_admin)
def ticket_reassign(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method == "POST":
        new_operator_id = request.POST.get("operator_id")
        new_operator = get_object_or_404(User, id=new_operator_id)

        # ✅ === STATO PRIMA ===
        old_operator = ticket.assigned_to

        # ✅ ASSEGNA NUOVO OPERATORE
        ticket.assigned_to = new_operator
        ticket.status = "in_progress"
        ticket.save()

        # ✅ === LOG PRIMA → DOPO ===
        AdminLog.objects.create(
            actor=request.user,
            target_user=new_operator,
            ticket=ticket,
            action="TICKET REASSIGNED",
            details=(
                f"Assegnazione modificata: "
                f"PRIMA = {old_operator.username if old_operator else 'Nessuno'} → "
                f"DOPO = {new_operator.username}"
            )
        )

        messages.success(
            request,
            f"Ticket riassegnato da "
            f"{old_operator.username if old_operator else 'Nessuno'} "
            f"a {new_operator.username}"
        )

        return redirect("ticket_detail", ticket_id=ticket.id)

    operators = User.objects.filter(groups__name="operator")

    return render(request, "tickets/ticket_reassign.html", {
        "ticket": ticket,
        "operators": operators
    })


@login_required
@user_passes_test(is_admin)
def ticket_reassign_view(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    operators = User.objects.filter(groups__name="operator")
    AdminLog.objects.create(
    actor=request.user,
    ticket=ticket,
    action="TICKET REASSIGNED",
    details="Riassegnazione manuale"
)

    return render(request, "tickets/ticket_reassign.html", {
        "ticket": ticket,
        "operators": operators
    })


@login_required
@user_passes_test(is_operator_or_admin)
def ticket_close(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.status != "closed":
        ticket.status = "closed"
        ticket.save()

        from django.urls import reverse
        from django.conf import settings
        from .utils.mailer import send_ticket_email, build_ticket_email_html

        ticket_url = f"{settings.SITE_URL}{reverse('ticket_detail', args=[ticket.id])}"

        subject = f"[TICKET CHIUSO] #{ticket.id}"

        text_message = (
            f"Il tuo ticket è stato chiuso.\n\n"
            f"Titolo: {ticket.title}\n\n"
            f"Visualizza il ticket: {ticket_url}"
        )

        html_message = build_ticket_email_html(
            title="Ticket Chiuso",
            message=f"""
                Il tuo ticket è stato chiuso.<br><br>
                <b>Titolo:</b> {ticket.title}<br>
                <b>Operatore:</b> {request.user.username}<br>
            """,
            ticket_url=ticket_url,
            button_text="Visualizza Ticket"
        )

        send_ticket_email(
            subject=subject,
            text_content=text_message,
            html_content=html_message,
            recipient_list=[ticket.created_by.email],
            actor=request.user,               # ✅ chi chiude
            target_user=ticket.created_by,    # ✅ chi riceve
            ticket=ticket
        )

    return redirect("ticket_detail", ticket_id=ticket.id)



# =========================================================
#                      CREAZIONE TICKET
# =========================================================

@login_required
def ticket_create(request):

    if is_operator(request.user):
        return redirect("ticket_list")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        priority = request.POST.get("priority", "medium")

        if not title or not description:
            return render(request, "tickets/ticket_create.html", {
                "error": "Compila tutti i campi."
            })

        ticket = Ticket.objects.create(
            title=title,
            description=description,
            priority=priority,
            created_by=request.user
        )
        # Il log di creazione lo fa il signal post_save (TICKET CREATE)

        return redirect("ticket_detail", ticket_id=ticket.id)

    return render(request, "tickets/ticket_create.html")


# =========================================================
#                     ADMIN → RUOLI UTENTI
# =========================================================

@login_required
@user_passes_test(is_admin)
def admin_users(request):
    users = User.objects.all().order_by("username")
    return render(request, "tickets/admin_users.html", {"users": users})


@login_required
@user_passes_test(is_admin)
def make_operator(request, user_id):
    if request.user.id == user_id:
        return redirect("admin_users")

    user = get_object_or_404(User, id=user_id)

    group, _ = Group.objects.get_or_create(name="operator")
    user.groups.clear()
    user.groups.add(group)
    user.is_staff = False
    user.save()

    # LOG DB
    AdminLog.objects.create(
        user=request.user,
        action="Assegnato ruolo OPERATOR",
        target_user=user
    )

    # LOG FILE
    admin_logger.info(f"[OPERATOR] {request.user.username} → {user.username}")

    return redirect("admin_users")


@login_required
@user_passes_test(is_admin)
def make_admin(request, user_id):
    user = get_object_or_404(User, id=user_id)

    group, _ = Group.objects.get_or_create(name="admin")
    user.groups.clear()
    user.groups.add(group)
    user.is_staff = True
    user.save()

    AdminLog.objects.create(
        user=request.user,
        action="Assegnato ruolo ADMIN",
        target_user=user
    )

    admin_logger.info(f"[ADMIN] {request.user.username} → {user.username}")

    return redirect("admin_users")


@login_required
@user_passes_test(is_admin)
def make_user(request, user_id):
    if request.user.id == user_id:
        return redirect("admin_users")

    user = get_object_or_404(User, id=user_id)
    user.groups.clear()
    user.is_staff = False

    group, _ = Group.objects.get_or_create(name="user")
    user.groups.add(group)
    user.save()

    AdminLog.objects.create(
        user=request.user,
        action="Assegnato ruolo USER",
        target_user=user
    )

    admin_logger.info(f"[USER] {request.user.username} → {user.username}")

    return redirect("admin_users")


# =========================================================
#                   ADMIN → UTENTI
# =========================================================

@login_required
@user_passes_test(is_admin)
def admin_user_detail(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    return render(request, "tickets/admin_user_detail.html", {"u": user_obj})


@login_required
@user_passes_test(is_admin)
def admin_user_edit(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    groups = Group.objects.all()
    current_group = user_obj.groups.first()

    if request.method == "POST":
        old_username = user_obj.username
        old_email = user_obj.email
        old_group = user_obj.groups.first().name if user_obj.groups.first() else None

        username = request.POST.get("username").strip()
        email = request.POST.get("email").strip()
        group_id = request.POST.get("group")

        change_password = request.POST.get("change_password") == "on"
        new_password = request.POST.get("password1")
        confirm_password = request.POST.get("password2")

        changes = []  # <--- lista modifiche

        # username
        if username != old_username:
            changes.append(f"username: {old_username} → {username}")
            user_obj.username = username

        # email
        if email != old_email:
            changes.append(f"email: {old_email} → {email}")
            user_obj.email = email

        # group
        if group_id:
            new_group = Group.objects.get(id=group_id)
            new_group_name = new_group.name
            if new_group_name != old_group:
                changes.append(f"gruppo: {old_group} → {new_group_name}")
                user_obj.groups.clear()
                user_obj.groups.add(new_group)

        # password
        if change_password:
            if new_password == confirm_password:
                changes.append("password: (modificata)")
                user_obj.set_password(new_password)
            else:
                messages.error(request, "Le password non coincidono.")
                return redirect("admin_user_edit", user_id=user_id)

        # Salva tutto
        user_obj.save()

        # LOG nel DB + FILE
        details = "\n".join(changes) if changes else "Nessuna modifica rilevata"

        AdminLog.objects.create(
            actor=request.user,          # ✅ chi compie l’azione
            target_user=user_obj,       # ✅ chi subisce l’azione
            action="Modifica dati utente",
            details=details,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )


        admin_logger.info(f"[EDIT USER] {request.user.username} -> {user_obj.username}\n{details}")

        messages.success(request, "Utente aggiornato correttamente.")
        return redirect("admin_user_detail", user_id=user_id)

    return render(request, "tickets/admin_user_edit.html", {
        "user_obj": user_obj,
        "groups": groups,
        "current_group": current_group,
    })

@login_required
@user_passes_test(is_admin)
def admin_user_delete(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)

    if request.user.id == user_obj.id:
        return redirect("admin_users")

    AdminLog.objects.create(
        user=request.user,
        action="Cancellazione utente",
        target_user=user_obj
    )
    admin_logger.info(f"[DELETE] {request.user.username} ha eliminato {user_obj.username}")

    user_obj.delete()
    return redirect("admin_users")


# =========================================================
#                   ADMIN → LOG VIEW
# =========================================================



@login_required
@user_passes_test(is_admin)
def admin_logs(request):

    logs = AdminLog.objects.select_related(
        "actor", "target_user", "ticket"
    ).order_by("-timestamp")

    # ==========================
    # ✅ FILTRI
    # ==========================

    admin_username = request.GET.get("admin", "").strip()
    target_username = request.GET.get("target", "").strip()
    action_text = request.GET.get("action", "").strip()
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    if admin_username:
        logs = logs.filter(actor__username__icontains=admin_username)

    if target_username:
        logs = logs.filter(target_user__username__icontains=target_username)

    if action_text:
        logs = logs.filter(action__icontains=action_text)

    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)

    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    return render(request, "tickets/admin_logs.html", {
        "logs": logs,
        "filters": request.GET
    })


@login_required
def secure_download(request, attachment_id):
    attachment = get_object_or_404(TicketAttachment, id=attachment_id)

    # ✅ permessi
    if not (
        is_admin(request.user) or
        is_operator(request.user) or
        attachment.ticket.created_by == request.user
    ):
        raise Http404()

    # ✅ ricostruzione path assoluto
    absolute_path = os.path.join(settings.SECURE_UPLOAD_ROOT, attachment.file_path)

    if not os.path.exists(absolute_path):
        raise Http404("File non trovato")

    AdminLog.objects.create(
    actor=request.user,
    ticket=attachment.ticket,
    action="ATTACHMENT DOWNLOAD",
    details=attachment.file_name
)


    return FileResponse(
        open(absolute_path, "rb"),
        as_attachment=True,
        filename=attachment.file_name
    )

@login_required
@user_passes_test(is_admin)
def attachment_delete(request, attachment_id):
    attachment = get_object_or_404(TicketAttachment, id=attachment_id)

    # Ricostruzione path assoluto dal relativo
    absolute_path = os.path.join(settings.SECURE_UPLOAD_ROOT, attachment.file_path)

    # Cancellazione file fisico (se esiste)
    if os.path.exists(absolute_path):
        try:
            os.remove(absolute_path)
        except Exception as e:
            messages.error(
                request,
                "Errore durante la cancellazione del file fisico."
            )
            return redirect("ticket_detail", ticket_id=attachment.ticket.id)

    # Cancellazione record DB
    attachment.delete()

    messages.success(request, "Allegato eliminato correttamente.")
    return redirect("ticket_detail", ticket_id=attachment.ticket.id)

@login_required
def attachment_preview(request, attachment_id):
    attachment = get_object_or_404(TicketAttachment, id=attachment_id)

    # ✅ permessi: admin, operator, creatore ticket
    if not (
        is_admin(request.user) or
        is_operator(request.user) or
        attachment.ticket.created_by == request.user
    ):
        raise Http404()

    # ✅ ricostruzione path assoluto dal relativo
    absolute_path = os.path.join(settings.SECURE_UPLOAD_ROOT, attachment.file_path)

    if not os.path.exists(absolute_path):
        raise Http404("File non trovato")

    # ✅ apertura inline (preview)
    response = FileResponse(open(absolute_path, "rb"))
    response["Content-Type"] = attachment.mime_type or "application/octet-stream"
    response["Content-Disposition"] = f'inline; filename="{attachment.file_name}"'

    return response

def log_action(request, action, *, target_user=None, ticket=None, details=""):
    ip = request.META.get("REMOTE_ADDR")
    ua = request.META.get("HTTP_USER_AGENT", "")

    AdminLog.objects.create(
        actor=request.user,
        target_user=target_user,
        ticket=ticket,
        action=action,
        details=details,
        ip_address=ip,
        user_agent=ua
    )

@login_required
def report_dashboard(request):
    # Meglio usare il tuo helper is_admin invece del semplice is_staff
    if not is_admin(request.user):
        return redirect("dashboard")

    from django.db.models import Count
    from .models import AdminLog, User

    month = request.GET.get("month")
    year = request.GET.get("year")
    operator_id = request.GET.get("operator")
    action_filter = request.GET.get("action")

    # ✅ SOLO LOG DI LAVORO OPERATIVO DEGLI OPERATORI
    logs = AdminLog.objects.filter(
        actor__groups__name="operator",
        action__in=[
            "TICKET ASSIGNED CHANGE",
            "TICKET STATUS CHANGE",
            "TICKET CLOSED"
        ]
    )

    # ✅ FILTRI TEMPORALI
    if month:
        logs = logs.filter(timestamp__month=int(month))

    if year:
        logs = logs.filter(timestamp__year=int(year))

    # ✅ FILTRO OPERATORE
    if operator_id:
        logs = logs.filter(actor_id=operator_id)

    # ✅ FILTRO PER TESTO AZIONE (opzionale)
    if action_filter:
        logs = logs.filter(action__icontains=action_filter)

    # ✅ SOLO UTENTI DEL GRUPPO OPERATOR PER LA SELECT
    operators = User.objects.filter(groups__name="operator")

    # ✅ GRAFICO ATTIVITÀ PER OPERATORE
    operator_stats_qs = (
        logs.values("actor__username")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    operator_labels = [x["actor__username"] for x in operator_stats_qs]
    operator_values = [x["total"] for x in operator_stats_qs]

    # ✅ GRAFICO DISTRIBUZIONE AZIONI
    action_stats_qs = (
        logs.values("action")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    action_labels = [x["action"] for x in action_stats_qs]
    action_values = [x["total"] for x in action_stats_qs]

    context = {
        "operators": operators,
        "operator_labels": operator_labels,
        "operator_values": operator_values,
        "action_labels": action_labels,
        "action_values": action_values,
        "selected_month": month,
        "selected_year": year,
        "selected_operator": operator_id,
        "selected_action": action_filter,
    }

    return render(request, "tickets/report_dashboard.html", context)
