import logging
import hmac
import hashlib
from flask import Blueprint, request, jsonify
from app.services.suspensions import perform_action
from app.core.config import load_config

suspend_unsuspend_blueprint = Blueprint("suspend_unsuspend", __name__)


def verify_webhook_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Verify UISP webhook signature using HMAC-SHA256."""
    if not signature or not secret:
        logging.warning("Webhook signature verification skipped: missing signature or secret")
        return True

    expected_signature = hmac.new(
        secret.encode(),
        payload_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@suspend_unsuspend_blueprint.route("/", methods=["POST"])
def handle_suspend_unsuspend():
    """Main webhook endpoint for UISP service suspension/unsuspension."""

    # Verify webhook signature
    config = load_config()
    signature = request.headers.get("X-UISP-Signature", "")
    if not verify_webhook_signature(request.data, signature, config.uisp_app_key):
        logging.error("Webhook signature verification failed")
        return jsonify({"error": "Invalid webhook signature"}), 401

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    try:
        change_type = data.get("changeType")
        entity = data.get("extraData", {}).get("entity", {})
        client_id = int(entity.get("clientId", 0))
        attributes = entity.get("attributes", [])

        ip_attr = next((a for a in attributes if a.get("key") == "ipAddress"), None)
        ip = ip_attr["value"] if ip_attr else None

        if not (change_type and client_id is not None and ip):
            return jsonify({"error": "Missing required fields (changeType, clientId, ipAddress)"}), 400

        logging.info(f"Webhook received: change={change_type} client={client_id} ip={ip}")

        result = perform_action(change_type, ip, client_id)
        response = {
            "action": change_type,
            "clientId": str(client_id),
            "ipAddress": ip,
            "message": result.get("message"),
            "ok": result.get("ok", False),
        }

        if "notification_error" in result:
            response["notification_error"] = result["notification_error"]

        status_code = 200 if result.get("ok") else 202
        return jsonify(response), status_code

    except Exception as e:
        logging.exception("Error handling suspension webhook:")
        return jsonify({
            "detail": str(e),
            "note": "suspension service error",
            "status": "accepted"
        }), 202
