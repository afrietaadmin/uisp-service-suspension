import os
import json
import logging
import requests

log = logging.getLogger(__name__)

# Hardcoded WhatsApp template globals (these rarely change)
WHATSAPP_API_VERSION = "v24.0"
WHATSAPP_TEMPLATE = "suspension_notice"
WHATSAPP_LANG = "en_GB"
WHATSAPP_IMAGE_URL = "https://uisp-ros1.afrieta.com/crm/suspension_notice.png"

def send_whatsapp_notification(phone_id: str, token: str, phone_number: str, message_text: str, amount: float, client_id: int) -> tuple[bool, str]:
    """
    Send a suspension WhatsApp notification to a customer.
    Returns (ok, detail_message).

    Args:
        phone_id: WhatsApp phone number ID
        token: WhatsApp API token
        phone_number: Customer's phone number
        message_text: The message text to send
        amount: Reconnection fee amount
        client_id: Customer ID for payment reference
    """

    if not phone_id or not token:
        msg = "Missing WhatsApp credentials (phone_id or token)"
        log.error(msg)
        return False, msg

    # --- Build URL & headers ---
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Format button text as /afrieta/{amount}/CID{client_id}
    button_text = f"/afrieta/{int(amount)}/CID{client_id}"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE,
            "language": {"code": WHATSAPP_LANG, "policy": "deterministic"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {"type": "image", "image": {"link": WHATSAPP_IMAGE_URL}}
                    ],
                },
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": message_text}],
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "1",
                    "parameters": [
                        {
                            "type": "text",
                            "text": button_text,
                        }
                    ],
                },
            ],
        },
    }

    # --- Log full request for debug visibility ---
    log.info("[WhatsApp] Sending payload:\n%s", json.dumps(payload, indent=2))

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        log.info("[WhatsApp] Response: %s %s", response.status_code, response.text)

        if response.status_code == 200:
            return True, "WhatsApp notification sent successfully."
        else:
            return False, f"WhatsApp API error {response.status_code}: {response.text}"

    except requests.exceptions.RequestException as e:
        log.error("[WhatsApp] Exception: %s", e)
        return False, str(e)
