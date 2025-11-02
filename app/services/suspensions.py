import logging
from app.core.config import load_config, find_router_by_ip
from app.infra.mikrotik import MikroTikClient
from app.infra.notifier import notify_client_suspension
from app.infra.telegram import TelegramNotifier


def perform_action(change_type: str, ip: str, client_id: int):
    """
    Handle suspend or unsuspend event:
    - Locate router from IP.
    - Execute DHCP lease toggle.
    - Notify via Telegram and WhatsApp.
    """

    cfg = load_config()
    tg = TelegramNotifier(cfg.telegram_token, cfg.telegram_chat_id)

    site, router = find_router_by_ip(cfg, ip)
    if not router:
        msg = f"Router not found for IP {ip}"
        logging.error(msg)
        tg.send(f"❌ {msg}", level="error")
        return {"ok": False, "message": msg}

    try:
        mt = MikroTikClient(router.api_url, router.username, router.password, verify=cfg.tls_verify)
        leases = mt.list_leases()
        lease = next((l for l in leases if l.get("address") == ip), None)

        if not lease:
            msg = f"No DHCP lease found for IP {ip} on {router.name}"
            logging.warning(msg)
            tg.send(f"⚠️ {msg}", level="warn")
            return {"ok": False, "message": msg}

        lease_id = lease.get(".id")
        if change_type.lower() == "suspend":
            mt.toggle_block_access(lease_id, True)
            msg = f"Successfully suspended IP {ip} on {router.name} ({site})."
        elif change_type.lower() in ("unsuspend", "end"):
            mt.toggle_block_access(lease_id, False)
            msg = f"Successfully unsuspended IP {ip} on {router.name} ({site})."
        else:
            msg = f"Unknown changeType '{change_type}'"
            logging.warning(msg)
            tg.send(f"⚠️ {msg}", level="warn")
            return {"ok": False, "message": msg}

        tg.send(f"✅ {msg}", level="info")

        # Notify client via WhatsApp only on suspend
        if change_type.lower() == "suspend":
            ok, detail = notify_client_suspension(cfg, client_id)
            if not ok:
                msg = f"{msg} Notification failed: {detail}"
                logging.warning(msg)
                return {"ok": True, "message": msg, "notification_error": detail}

        return {"ok": True, "message": msg}

    except Exception as e:
        msg = f"Router operation failed: {e}"
        logging.exception(msg)
        tg.send(f"❌ {msg}", level="error")
        return {"ok": False, "message": msg}
