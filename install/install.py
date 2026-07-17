"""
Cross-platform autostart installer.

Run this ONCE, from the project root, after your .env and Google
credentials are set up:

    python install/install.py

It detects your OS and registers the agent to run in the background:
  - Windows: a Scheduled Task that runs at logon.
  - macOS:   a launchd user agent.
  - Linux:   a systemd user service.

Run "python install/install.py --uninstall" to remove it again.
"""
import os
import platform
import subprocess
import sys
import textwrap

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_EXE = sys.executable
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "main.py")


def _pythonw_path():
    """Prefer pythonw.exe (runs with no console window) if it's sitting
    next to the regular interpreter, which is normal for python.org installs."""
    candidate = os.path.join(os.path.dirname(PYTHON_EXE), "pythonw.exe")
    return candidate if os.path.exists(candidate) else PYTHON_EXE


def _startup_folder():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("Couldn't locate your Windows Startup folder (APPDATA not set).")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def install_windows():
    """
    Uses your personal Startup folder rather than Task Scheduler.
    schtasks /create can fail with 'Access is denied' depending on local
    security policy even for per-user tasks - a launcher in your own
    Startup folder needs no special permissions at all.
    """
    startup_dir = _startup_folder()
    os.makedirs(startup_dir, exist_ok=True)
    launcher_path = os.path.join(startup_dir, "task-agent-launcher.bat")
    interpreter = _pythonw_path()

    contents = (
        "@echo off\r\n"
        f'cd /d "{PROJECT_ROOT}"\r\n'
        f'start "" "{interpreter}" "{MAIN_SCRIPT}"\r\n'
    )
    with open(launcher_path, "w") as f:
        f.write(contents)

    print(f"[windows] Startup launcher created: {launcher_path}")
    print("[windows] It'll start automatically next time you log in (you may see a brief flash - that's normal).")
    print(f"[windows] To start it right now without logging out, double-click that file, or run:")
    print(f'  "{interpreter}" "{MAIN_SCRIPT}"')


def uninstall_windows():
    launcher_path = os.path.join(_startup_folder(), "task-agent-launcher.bat")
    if os.path.exists(launcher_path):
        os.remove(launcher_path)
        print(f"[windows] Removed {launcher_path}")
    else:
        print("[windows] No startup launcher found - nothing to remove.")


def install_macos():
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.personal.taskagent.plist")
    plist_contents = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key><string>com.personal.taskagent</string>
            <key>ProgramArguments</key>
            <array>
                <string>{PYTHON_EXE}</string>
                <string>{MAIN_SCRIPT}</string>
            </array>
            <key>WorkingDirectory</key><string>{PROJECT_ROOT}</string>
            <key>RunAtLoad</key><true/>
            <key>KeepAlive</key><true/>
            <key>StandardOutPath</key><string>{PROJECT_ROOT}/agent.log</string>
            <key>StandardErrorPath</key><string>{PROJECT_ROOT}/agent.err.log</string>
        </dict>
        </plist>
    """)
    with open(plist_path, "w") as f:
        f.write(plist_contents)
    subprocess.run(["launchctl", "unload", plist_path], check=False)
    subprocess.run(["launchctl", "load", plist_path], check=True)
    print(f"[macos] launchd agent installed at {plist_path} and started.")


def uninstall_macos():
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.personal.taskagent.plist")
    subprocess.run(["launchctl", "unload", plist_path], check=False)
    if os.path.exists(plist_path):
        os.remove(plist_path)
    print("[macos] launchd agent removed.")


def install_linux():
    unit_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(unit_dir, exist_ok=True)
    unit_path = os.path.join(unit_dir, "task-agent.service")
    unit_contents = textwrap.dedent(f"""\
        [Unit]
        Description=Personal Task Agent

        [Service]
        ExecStart={PYTHON_EXE} {MAIN_SCRIPT}
        WorkingDirectory={PROJECT_ROOT}
        Restart=on-failure

        [Install]
        WantedBy=default.target
    """)
    with open(unit_path, "w") as f:
        f.write(unit_contents)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "task-agent.service"], check=True)
    print("[linux] systemd user service installed and started: task-agent.service")
    print("[linux] Tip: run 'loginctl enable-linger $USER' so it keeps running after you log out.")


def uninstall_linux():
    subprocess.run(["systemctl", "--user", "disable", "--now", "task-agent.service"], check=False)
    unit_path = os.path.expanduser("~/.config/systemd/user/task-agent.service")
    if os.path.exists(unit_path):
        os.remove(unit_path)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("[linux] systemd user service removed.")


def main():
    os_name = platform.system()
    uninstall = "--uninstall" in sys.argv

    print(f"Detected OS: {os_name}")
    if os_name == "Windows":
        uninstall_windows() if uninstall else install_windows()
    elif os_name == "Darwin":
        uninstall_macos() if uninstall else install_macos()
    elif os_name == "Linux":
        uninstall_linux() if uninstall else install_linux()
    else:
        print(f"Unsupported OS: {os_name}. Run 'python main.py' manually instead.")


if __name__ == "__main__":
    main()
