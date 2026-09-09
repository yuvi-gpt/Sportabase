import json
import logging

from app.accounts.preferences import Preferences, delivery_time, effective_preferences


LOGGER = logging.getLogger(__name__)


def eligible_at(conn, owner, provider, registration_id, alert_id, now):
    if not owner.startswith("account:"):
        return now  # Pre-account delivery stays compatible until explicitly linked.
    account_id = owner.removeprefix("account:")
    account = conn.execute("SELECT * FROM product_accounts WHERE id=?", (account_id,)).fetchone()
    if not account or account["status"] != "active":
        return None
    binding = conn.execute("SELECT device_id FROM product_notification_bindings WHERE provider=? AND registration_id=? AND account_id=?", (provider, registration_id, account_id)).fetchone()
    if not binding:
        return None  # An unbound account registration must never receive push.
    device = conn.execute("SELECT * FROM product_installations WHERE account_id=? AND device_id=?", (account_id, binding[0])).fetchone()
    if not device:
        return None
    prefs = effective_preferences(json.loads(account["defaults_json"]), json.loads(device["overrides_json"]), bool(device["follows_defaults"]))
    alert = conn.execute("SELECT target_kind FROM product_alert_events WHERE id=? AND client_key=?", (alert_id, owner)).fetchone()
    return delivery_time(prefs, alert[0], now) if alert else None


def filter_claims(conn, ids, provider, now):
    """Apply fresh preferences before leasing, so quiet time consumes no attempt."""
    table, column = (("product_notification_deliveries", "device_id") if provider == "expo" else ("product_web_push_deliveries", "subscription_id"))
    eligible = []
    for delivery_id in ids:
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (delivery_id,)).fetchone()
        available = eligible_at(conn, row["client_key"], provider, row[column], row["alert_id"], now)
        if available is None:
            conn.execute(f"UPDATE {table} SET status='cancelled',lease_owner='',lease_expires_at_epoch=0 WHERE id=?", (delivery_id,))
        elif available > now:
            conn.execute(f"UPDATE {table} SET status='pending',available_at_epoch=?,lease_owner='',lease_expires_at_epoch=0 WHERE id=?", (available, delivery_id))
        else:
            eligible.append(delivery_id)
    return eligible


def bind_registration(factory, request, provider, registration_id):
    from app.accounts.store import transaction
    account = getattr(request.state, "account", None)
    if not account:
        return
    with transaction(factory) as conn:
        conn.execute("""INSERT INTO product_notification_bindings VALUES(?,?,?,?)
          ON CONFLICT(provider,registration_id) DO UPDATE SET device_id=excluded.device_id
          WHERE product_notification_bindings.account_id=excluded.account_id""",
          (provider, registration_id, account["id"], request.state.device_id))
        bound = conn.execute("""SELECT 1 FROM product_notification_bindings
          WHERE provider=? AND registration_id=? AND account_id=? AND device_id=?""",
          (provider, registration_id, account["id"], request.state.device_id)).fetchone()
        if not bound:
            raise RuntimeError("Notification registration binding conflict")


def unbind_registration(factory, request, provider, registration_id):
    from app.accounts.store import transaction
    account = getattr(request.state, "account", None)
    if not account:
        return
    with transaction(factory) as conn:
        conn.execute("DELETE FROM product_notification_bindings WHERE provider=? AND registration_id=? AND account_id=?",
                     (provider, registration_id, account["id"]))


def record_registration_event(factory, request, event):
    from app.accounts.store import record_event_best_effort
    account = getattr(request.state, "account", None)
    if account:
        record_event_best_effort(factory, account["id"], event,
                                 request.state.account_device["platform"])


def cleanup_binding_after_unregistration(factory, request, provider, registration_id):
    """A missing provider row cannot deliver; stale binding cleanup is observable."""
    try:
        unbind_registration(factory, request, provider, registration_id)
        return True
    except Exception:
        LOGGER.exception("Notification binding cleanup failed after registration removal",
                         extra={"provider": provider})
        return False
