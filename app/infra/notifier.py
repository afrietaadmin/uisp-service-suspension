import logging
import requests
from app.infra.telegram import TelegramNotifier
from app.infra.whatsapp import send_whatsapp_notification


def get_client_details(uisp_base_url: str, uisp_app_key: str, client_id: int):
    """Fetch client data from UISP."""
    url = f"{uisp_base_url.rstrip('/')}/crm/api/v1.0/clients/{client_id}"
    headers = {
        "X-Auth-App-Key": uisp_app_key,
        "Content-Type": "application/json",
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error(f"Failed to fetch client {client_id} details: {e}")
        return None


def extract_whatsapp_number(client_data: dict) -> str | None:
    """Extract correct WhatsApp number from client attributes."""
    dont_send = next((a for a in client_data.get("attributes", [])
                      if a.get("key") == "dontSendWhatsapp"), None)
    if dont_send and dont_send.get("value") == "1":
        logging.info("Client opted out of WhatsApp notifications.")
        return None

    notify_service = next((a for a in client_data.get("attributes", [])
                           if a.get("key") == "notificationService"), None)
    msg_number = next((a for a in client_data.get("attributes", [])
                       if a.get("key") == "messagingNumber"), None)

    if notify_service and notify_service.get("value", "").lower() == "whatsapp" and msg_number:
        return msg_number.get("value")

    # fallback: try contacts
    for contact in client_data.get("contacts", []):
        if contact.get("phone"):
            return contact["phone"]

    return None


def build_message_text(client_data: dict) -> str:
    """Compose WhatsApp message body."""
    from datetime import datetime
    
    outstanding = round(client_data.get("accountOutstanding", 0.0) + 50)
    client_id = client_data.get("id")
    current_month = datetime.now().strftime("%B %Y")
    
    return (
        f"Payment was due by the 2nd of {current_month}. "
        f"Pay R{outstanding} (includes R50 reconnection fee). "
        f"Your payment reference for EFTs is CID{client_id}."
    )


def notify_client_suspension(cfg, client_id: int):
    """
    Sends WhatsApp + Telegram notification to client.
    """
    tg = TelegramNotifier(cfg.telegram_token, cfg.telegram_chat_id)
    client_data = get_client_details(cfg.uisp_base_url, cfg.uisp_app_key, client_id)
    if not client_data:
        tg.send(f"❌ Failed to fetch client details for {client_id}", level="error")
        return False, "Failed to fetch client data"

    # Extract WhatsApp number
    phone_number = extract_whatsapp_number(client_data)
    if not phone_number:
        msg = f"No notification phone found for client {client_id} (checked: none)"
        logging.warning(msg)
        tg.send(f"⚠️ {msg}", level="warn")
        return False, msg

    message_text = build_message_text(client_data)
    amount = round(client_data.get("accountOutstanding", 0.0) + 50)

    ok, detail = send_whatsapp_notification(
        cfg.whatsapp_phone_id, cfg.whatsapp_token, phone_number, message_text, amount, client_id
    )

    if ok:
        tg.send(f"✅ WhatsApp sent to client {client_id} ({phone_number})", level="info")
    else:
        tg.send(f"⚠️ WhatsApp send failed for client {client_id}: {detail}", level="warn")

    return ok, detail
