"""
Serviço central de notificações.
Centraliza envio de alertas via WhatsApp, email, SMS, etc.
"""
import requests
import os

WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")


def enviar_whatsapp(numero: str, mensagem: str):
    """
    Envia mensagem via WhatsApp.

    Args:
        numero: Número no formato internacional (ex: +5591999999999)
        mensagem: Texto da mensagem

    Returns:
        dict: {"status": "sent", "code": int} ou {"status": "error", "error": str}
    """
    payload = {
        "phone": numero,
        "message": mensagem
    }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(WHATSAPP_API_URL, json=payload, headers=headers)
        return {"status": "sent", "code": response.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}
