"""
WhatsApp channel via Meta's official Cloud API.

Important limitation (by design of WhatsApp, not this code): this
sends reminders OUT just fine from your local machine. But *receiving*
messages back would require Meta to call a public webhook URL, which
means exposing your machine (e.g. via ngrok) or hosting somewhere
reachable. So this channel is outbound-only, matching a "runs on my
own system" setup. Use Telegram for two-way interaction.

Two send modes (set WHATSAPP_SEND_MODE in .env):
  - "template": always works, but needs an approved message template
    in Meta Business Manager (required for business-initiated chats).
  - "text": only works if you messaged the business number within
    the last 24 hours (a WhatsApp platform rule, not ours).
"""
import requests
from config import Config

GRAPH_API_VERSION = "v19.0"


def send(message: str) -> bool:
    if not (Config.WHATSAPP_TOKEN and Config.WHATSAPP_PHONE_NUMBER_ID and Config.WHATSAPP_TO_NUMBER):
        return False

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {Config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    if Config.WHATSAPP_SEND_MODE == "template":
        payload = {
            "messaging_product": "whatsapp",
            "to": Config.WHATSAPP_TO_NUMBER,
            "type": "template",
            "template": {
                "name": Config.WHATSAPP_TEMPLATE_NAME,
                "language": {"code": Config.WHATSAPP_TEMPLATE_LANG},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": message}],
                }],
            },
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": Config.WHATSAPP_TO_NUMBER,
            "type": "text",
            "text": {"body": message},
        }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if not resp.ok:
            print(f"[whatsapp] send failed ({resp.status_code}): {resp.text}")
        return resp.ok
    except requests.RequestException as e:
        print(f"[whatsapp] send failed: {e}")
        return False
