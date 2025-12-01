

from tickets.models import AdminLog


def log_change(
    *,
    actor,
    action,
    ticket=None,
    target_user=None,
    field_name=None,
    old_value=None,
    new_value=None,
    extra=None,
    ip_address=None,
    user_agent="",
):
    """
    Helper centralizzato per scrivere nel modello AdminLog.

    - Se target_user non viene passato, per sicurezza assumiamo actor
      in modo da non avere MAI target_user_id = NULL.
    - Genera un testo PRIMA/DOPO standardizzato quando ci sono old/new.
    """

    # ✅ mai NULL in colonna target_user_id
    if target_user is None:
        target_user = actor

    parts = []

    if field_name:
        parts.append(f"Campo: {field_name}")

    if old_value is not None or new_value is not None:
        parts.append(f"PRIMA: {old_value}")
        parts.append(f"DOPO: {new_value}")

    if extra:
        parts.append(str(extra))

    details = "\n".join(parts) if parts else ""

    AdminLog.objects.create(
        actor=actor,
        target_user=target_user,
        ticket=ticket,
        action=action,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent or "",
    )
