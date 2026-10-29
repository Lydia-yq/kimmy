"""Windows 登录启动项管理。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "XiaoKPet"


def startup_file() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("找不到 Windows 用户启动目录。")
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / f"{APP_NAME}.vbs"
    )


def is_enabled() -> bool:
    try:
        return startup_file().exists()
    except RuntimeError:
        return False


def set_enabled(enabled: bool, project_dir: Path) -> None:
    target = startup_file()
    if not enabled:
        target.unlink(missing_ok=True)
        return

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = str(pythonw if pythonw.exists() else Path(sys.executable))
    script = str(project_dir / "moon_pet.py")
    work_dir = str(project_dir)

    def vbs_quote(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    content = (
        "Option Explicit\n"
        "Dim shell\n"
        "Set shell = CreateObject(\"WScript.Shell\")\n"
        f"shell.CurrentDirectory = {vbs_quote(work_dir)}\n"
        f"shell.Run Chr(34) & {vbs_quote(interpreter)} & Chr(34) & \" \" & "
        f"Chr(34) & {vbs_quote(script)} & Chr(34), 0, False\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="ascii")
