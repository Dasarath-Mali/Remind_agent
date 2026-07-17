"""
Entry point. Run this with: python main.py

What it does:
1. Detects your OS (install/install.py handles OS-specific autostart).
2. Validates your .env config so misconfiguration fails loudly, up front.
3. Starts the Telegram listener in the background - handles YOUR
   commands and auto-replies/booking for anyone else who messages it
   (see core/bot_logic.py for all of that logic).
4. Runs the reminder check loop forever, on a timer.
"""
import time
import signal
import sys
import os

# When launched via pythonw.exe (no console window - used by the Windows
# Startup launcher), sys.stdout/stderr are None, and any print() call
# would crash immediately. Redirect to a log file in that case, which
# also gives you somewhere to check status when running headless.
if sys.stdout is None or sys.stderr is None:
    _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")
    _log_file = open(_log_path, "a", buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file

import schedule

from config import Config
from core import reminder_engine, bot_logic
from connectors.telegram_channel import TelegramCommandListener


def main():
    print(f"[main] Detected OS: {Config.OS_NAME}")
    Config.validate()

    listener = None
    if Config.ENABLE_TELEGRAM:
        listener = TelegramCommandListener(bot_logic.handle_message)
        listener.start()
        print("[main] Telegram listener started (long-polling, no public URL needed).")

    def graceful_exit(signum, frame):
        print("\n[main] Shutting down...")
        if listener:
            listener.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    # Run once immediately, then on the configured interval.
    reminder_engine.run_check_cycle()
    schedule.every(Config.CHECK_FREQUENCY_MINUTES).minutes.do(reminder_engine.run_check_cycle)

    print(f"[main] Agent running. Checking every {Config.CHECK_FREQUENCY_MINUTES} minute(s). Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
