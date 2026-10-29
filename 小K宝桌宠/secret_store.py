"""使用 Windows DPAPI 将密钥绑定到当前 Windows 用户加密保存。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


CRYPTPROTECT_UI_FORBIDDEN = 0x01


def _make_blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    return blob, buffer


def _crypt(data: bytes, protect: bool) -> bytes:
    if not data:
        return b""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    function.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    input_blob, input_buffer = _make_blob(data)
    output_blob = DATA_BLOB()
    description = "Xiao K Pet API key" if protect else None
    if not function(
        ctypes.byref(input_blob),
        description,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
        _ = input_buffer


def save_api_key(api_key: str, path: Path) -> None:
    key = api_key.strip()
    if not key:
        raise ValueError("API Key 不能为空。")
    encrypted = _crypt(key.encode("utf-8"), protect=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encrypted)
    temporary.replace(path)


def load_api_key(path: Path) -> str:
    if not path.exists():
        return ""
    encrypted = path.read_bytes()
    if not encrypted:
        return ""
    return _crypt(encrypted, protect=False).decode("utf-8")


def delete_api_key(path: Path) -> None:
    path.unlink(missing_ok=True)
