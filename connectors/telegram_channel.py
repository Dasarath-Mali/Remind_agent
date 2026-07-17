"""
Telegram channel. This is the agent's main two-way interface:
- Sends reminders and notifications.
- Polls (long-polling, not webhooks) for ALL incoming messages, from you
  or from anyone else, and hands them to core/bot_logic.py to decide
  what to do - so it works fully locally, no public URL or server
  required.
"""
import threading
import time
import requests

from config import Config

API_BASE = "https://api.telegram.org/bot{token}"


def send(message: str, chat_id=None) -> bool:
    """chat_id defaults to you (Config.TELEGRAM_CHAT_ID); pass a different
    one to message a guest instead."""
    if not Config.TELEGRAM_BOT_TOKEN:
        return False
    target = chat_id if chat_id is not None else Config.TELEGRAM_CHAT_ID
    if not target:
        return False
    url = f"{API_BASE.format(token=Config.TELEGRAM_BOT_TOKEN)}/sendMessage"
    try:
        resp = requests.post(url, data={
            "chat_id": target,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=15)
        return resp.ok
    except requests.RequestException as e:
        print(f"[telegram] send failed: {e}")
        return False


class TelegramCommandListener:
    """
    Runs in a background thread. `on_message(chat_id, text, from_user) -> str`
    is called for every incoming message from anyone; its return value is
    sent back as the reply. `from_user` is Telegram's raw sender dict
    (first_name, username, id, ...) - used to greet guests and to tell
    them apart from you.
    """

    def __init__(self, on_message):
        self.on_message = on_message
        self._offset = None
        self._stop = threading.Event()

    def start(self):
        thread = threading.Thread(target=self._poll_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._stop.set()

    def _poll_loop(self):
        if not Config.TELEGRAM_BOT_TOKEN:
            return
        url = f"{API_BASE.format(token=Config.TELEGRAM_BOT_TOKEN)}/getUpdates"
        while not self._stop.is_set():
            try:
                params = {"timeout": 25}
                if self._offset is not None:
                    params["offset"] = self._offset
                resp = requests.get(url, params=params, timeout=30)
                data = resp.json()
                for update in data.get("result", []):
                    self._offset = update["update_id"] + 1
                    self._handle_update(update)
            except requests.RequestException as e:
                print(f"[telegram] poll error: {e}")
                time.sleep(5)

    def _handle_update(self, update: dict):
        message = update.get("message", {})
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")
        from_user = message.get("from", {})
        if not text or chat_id is None:
            return

        try:
            reply = self.on_message(chat_id, text, from_user)
        except Exception as e:
            print(f"[telegram] handler error: {e}")
            reply = "Something went wrong on my end, sorry."

        if reply:
            send(reply, chat_id=chat_id)
