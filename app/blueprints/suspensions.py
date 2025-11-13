import logging
import hmac
import hashlib
import json
from flask import Blueprint, request, jsonify
from app.services.suspensions import perform_action
from app.core.config import load_config
from app.models.idempotency import IdempotencyStore

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
        webhook_uuid = data.get("uuid")
        entity = data.get("extraData", {}).get("entity", {})
        entity_id = entity.get("id")
        client_id = int(entity.get("clientId", 0))
        attributes = entity.get("attributes", [])

        ip_attr = next((a for a in attributes if a.get("key") == "ipAddress"), None)
        ip = ip_attr["value"] if ip_attr else None

        if not (change_type and client_id is not None and ip):
            return jsonify({"error": "Missing required fields (changeType, clientId, ipAddress)"}), 400

        logging.info(f"Webhook received: change={change_type} client={client_id} ip={ip} uuid={webhook_uuid}")

        # Check for duplicate webhook using idempotency store
        if webhook_uuid:
            idempotency_store = IdempotencyStore()
            if idempotency_store.is_duplicate(webhook_uuid):
                logging.warning(f"Duplicate webhook detected: {webhook_uuid} - returning 200 OK without processing")
                return jsonify({
                    "ok": True,
                    "message": "Webhook already processed",
                    "uuid": webhook_uuid,
                    "duplicate": True,
                    "action": change_type,
                    "clientId": str(client_id),
                    "ipAddress": ip
                }), 200
        else:
            logging.warning("Webhook received without UUID - proceeding with caution (idempotency not guaranteed)")

        # Perform the suspension/unsuspension action
        result = perform_action(change_type, ip, client_id)

        # Mark webhook as processed in idempotency store
        if webhook_uuid:
            try:
                response_data = {
                    "action": change_type,
                    "clientId": str(client_id),
                    "ipAddress": ip,
                    "message": result.get("message"),
                    "ok": result.get("ok", False),
                }
                if "notification_error" in result:
                    response_data["notification_error"] = result["notification_error"]

                idempotency_store.mark_processed(
                    webhook_uuid,
                    "service",
                    str(entity_id),
                    change_type,
                    json.dumps(response_data)
                )
            except Exception as e:
                logging.error(f"Failed to mark webhook as processed: {e}")
                # Continue processing even if idempotency tracking fails

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
