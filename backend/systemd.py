"""systemd user service management for AgentStatus."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "agent-foreman-local"

SERVICE_TEMPLATE = """\
[Unit]
Description=AgentStatus — Local Coding Agent Supervisor Dashboard
After=network.target

[Service]
Type=simple
ExecStart={exec_path} serve --host {host} --port {port}
WorkingDirectory={working_dir}
Restart=on-failure
RestartSec=5
Environment=PATH={path}

[Install]
WantedBy=default.target
"""


def get_service_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def get_service_path() -> Path:
    return get_service_dir() / f"{SERVICE_NAME}.service"


def generate_service(
    host: str = "127.0.0.1",
    port: int = 8787,
) -> str:
    """Generate the systemd service file content."""
    exec_path = _find_executable()
    working_dir = str(Path.home())
    path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")

    return SERVICE_TEMPLATE.format(
        exec_path=exec_path,
        host=host,
        port=port,
        working_dir=working_dir,
        path=path,
    )


def install_service(
    host: str = "127.0.0.1",
    port: int = 8787,
    enable: bool = False,
) -> tuple[bool, str]:
    """Install the systemd user service.

    Returns (success, message).
    """
    service_dir = get_service_dir()
    service_dir.mkdir(parents=True, exist_ok=True)

    content = generate_service(host=host, port=port)
    service_path = get_service_path()
    service_path.write_text(content)

    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        return False, f"Failed to reload systemd: {e.stderr.decode()}"

    if enable:
        try:
            subprocess.run(
                ["systemctl", "--user", "enable", SERVICE_NAME],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            return False, f"Failed to enable service: {e.stderr.decode()}"

    return True, str(service_path)


def uninstall_service() -> tuple[bool, str]:
    """Remove the systemd user service."""
    service_path = get_service_path()
    if not service_path.exists():
        return False, "Service not installed"

    for action in ("disable", "stop"):
        try:
            subprocess.run(
                ["systemctl", "--user", action, SERVICE_NAME],
                capture_output=True,
            )
        except Exception:
            pass

    service_path.unlink()

    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
        )
    except Exception:
        pass

    return True, "Service removed"


def _find_executable() -> str:
    """Find the agent-foreman-local executable path."""
    path = shutil.which("agent-foreman-local")
    if path:
        return path
    path = shutil.which("agentctl")
    if path:
        return path
    return str(Path(sys.executable).parent / "agent-foreman-local")
