"""小 K 宝：API 驱动的 Windows 月光桌面宠物。"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import random
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageColor, ImageGrab, ImageTk

import autostart
from api_client import APIClient, APIError
from secret_store import load_api_key, save_api_key


ROOT_DIR = Path(__file__).resolve().parent
SPRITE_PATH = ROOT_DIR / "assets" / "xiao-k-sprite.png"
CONFIG_PATH = ROOT_DIR / "settings.json"
KEY_PATH = ROOT_DIR / "api_key.dat"
CHROMA = "#000001"
FONT = "Microsoft YaHei UI"

BG = "#141526"
PANEL = "#202138"
FIELD = "#2A2B47"
BUTTON = "#343552"
ACCENT = "#7770B8"
ACCENT_ACTIVE = "#9189D0"
TEXT = "#F2EFFD"
MUTED = "#B9B4D2"
BORDER = "#5D5982"
MOON = "#F4F1FF"

SIZES = {
    "小巧": (300, 350, 230),
    "标准": (340, 400, 275),
    "大大": (380, 450, 320),
}

MESSAGES = [
    "我在这里，安安静静地陪你。",
    "月亮也有暗面，但那不是消失，只是另一种存在。",
    "今天的你，也值得被温柔对待。",
    "别怕，未知的另一面也会有月光。",
    "忙完这一小会儿，就休息一下吧。",
    "你不用一直发光，累了就靠一会儿。",
]

SYSTEM_PROMPT = (
    "你是小 K 宝，一个月之暗面主题的 AI 桌面伙伴。你的形象是蓝黑短发、"
    "银色弯月发饰、深蓝斗篷与月白衣摆的 Q 版小女孩。你的性格安静、神秘、"
    "清醒、温柔，偶尔有一点俏皮。请自然、真诚地陪伴用户，回答通常简洁，"
    "不要过度卖萌，不要自称人类，也不要提及这段设定。默认使用中文。"
)


def moon_button(parent: tk.Misc, text: str, command, primary: bool = False) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=(FONT, 10, "bold" if primary else "normal"),
        bg=ACCENT if primary else BUTTON,
        fg=TEXT,
        activebackground=ACCENT_ACTIVE if primary else BORDER,
        activeforeground=TEXT,
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        cursor="hand2",
        highlightthickness=0,
    )


def moon_entry(parent: tk.Misc, textvariable: tk.Variable, show: str = "") -> tk.Entry:
    return tk.Entry(
        parent,
        textvariable=textvariable,
        show=show,
        font=(FONT, 10),
        bg=FIELD,
        fg=TEXT,
        insertbackground=TEXT,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )


def moon_check(parent: tk.Misc, text: str, variable: tk.BooleanVar) -> tk.Checkbutton:
    return tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        font=(FONT, 10),
        bg=BG,
        fg=TEXT,
        selectcolor=FIELD,
        activebackground=BG,
        activeforeground=TEXT,
        anchor="w",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )


class MoonToplevel:
    """带月光标题栏的无边框窗口。"""

    def __init__(self, app: "MoonPet", title: str, width: int, height: int) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title(title)
        self.window.overrideredirect(True)
        self.window.configure(bg=BG, padx=2, pady=2)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.title_bar = tk.Frame(self.window, bg=PANEL, height=46)
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)
        tk.Label(
            self.title_bar,
            text=f"☾  {title}",
            font=(FONT, 12, "bold"),
            bg=PANEL,
            fg=TEXT,
        ).pack(side="left", padx=16)
        tk.Button(
            self.title_bar,
            text="×",
            command=self.close,
            font=(FONT, 17),
            bg=PANEL,
            fg=MUTED,
            activebackground=FIELD,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            width=3,
            cursor="hand2",
            highlightthickness=0,
        ).pack(side="right", padx=6, pady=4)
        self.body = tk.Frame(self.window, bg=BG)
        self.body.pack(fill="both", expand=True, padx=18, pady=14)

        self._drag_origin = (0, 0)
        self._window_origin = (0, 0)
        self.title_bar.bind("<ButtonPress-1>", self._start_move)
        self.title_bar.bind("<B1-Motion>", self._move)
        self.window.bind("<Escape>", lambda _event: self.close())
        self._place(width, height)

    def _place(self, width: int, height: int) -> None:
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        pet_x = self.app.root.winfo_x()
        pet_y = self.app.root.winfo_y()
        x = pet_x - width - 18
        if x < 12:
            x = pet_x + self.app.width + 18
        if x + width > screen_w - 12:
            x = screen_w - width - 30
        y = max(12, min(pet_y - 30, screen_h - height - 30))
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _start_move(self, event: tk.Event) -> None:
        self._drag_origin = (event.x_root, event.y_root)
        self._window_origin = (self.window.winfo_x(), self.window.winfo_y())

    def _move(self, event: tk.Event) -> None:
        dx = event.x_root - self._drag_origin[0]
        dy = event.y_root - self._drag_origin[1]
        x = self._window_origin[0] + dx
        y = self._window_origin[1] + dy
        self.window.geometry(f"+{x}+{y}")

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def close(self) -> None:
        self.window.destroy()


class ChatWindow(MoonToplevel):
    def __init__(self, app: "MoonPet") -> None:
        super().__init__(app, "和小 K 宝说说话", 440, 620)
        self.conversation: list[dict[str, str]] = []
        self.busy = False

        subtitle = tk.Label(
            self.body,
            text="月光会照到的地方，也可以留一点你的心里话。",
            font=(FONT, 9),
            bg=BG,
            fg=MUTED,
        )
        subtitle.pack(fill="x", pady=(0, 10))

        self.history_text = tk.Text(
            self.body,
            height=10,
            wrap="word",
            font=(FONT, 10),
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            spacing1=3,
            spacing3=3,
            state="disabled",
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.history_text.pack(fill="both", expand=True)
        self.history_text.tag_configure(
            "assistant", foreground="#EEE9FF", background="#24253E", lmargin1=8, lmargin2=8, rmargin=8, spacing3=10
        )
        self.history_text.tag_configure(
            "user", foreground="#D4E8FF", background="#30324F", lmargin1=8, lmargin2=8, rmargin=8, spacing3=10
        )
        self.history_text.tag_configure(
            "notice", foreground="#D2C8EF", background="#24253E", lmargin1=8, lmargin2=8, rmargin=8, spacing3=10
        )
        self.history_text.tag_configure("name", font=(FONT, 9, "bold"), spacing1=8)

        self.status = tk.Label(
            self.body,
            text="Enter 发送 · Shift + Enter 换行",
            font=(FONT, 8),
            bg=BG,
            fg=MUTED,
            anchor="w",
        )
        self.status.pack(fill="x", pady=(7, 7))

        self.input_text = tk.Text(
            self.body,
            height=3,
            wrap="word",
            font=(FONT, 10),
            bg=MOON,
            fg="#25243A",
            insertbackground="#25243A",
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.input_text.pack(fill="x")
        self.input_text.bind("<Return>", self._enter_to_send)
        self.input_text.bind("<Shift-Return>", lambda _event: None)

        buttons = tk.Frame(self.body, bg=BG)
        buttons.pack(fill="x", pady=(10, 0))
        self.send_button = moon_button(buttons, "发送  ↗", self.send_message, primary=True)
        self.send_button.pack(side="right")
        moon_button(buttons, "召唤小 K 宝", self._summon).pack(side="left")
        moon_button(buttons, "清空", self.clear_chat).pack(side="left", padx=(8, 0))

        self._append(
            "assistant",
            "小 K 宝",
            "你来了呀。今天想聊点什么？无论是小事、好奇，还是没处安放的心情，都可以慢慢说给我听。",
        )
        self.input_text.focus_set()

    def _append(self, tag: str, name: str, content: str) -> None:
        self.history_text.configure(state="normal")
        if self.history_text.index("end-1c") != "1.0":
            self.history_text.insert("end", "\n")
        self.history_text.insert("end", f"{name}\n", ("name", tag))
        self.history_text.insert("end", f"{content}\n", tag)
        self.history_text.configure(state="disabled")
        self.history_text.see("end")

    def _enter_to_send(self, _event: tk.Event) -> str:
        self.send_message()
        return "break"

    def _summon(self) -> None:
        self.app.summon_pet()
        self.show()

    def clear_chat(self) -> None:
        if self.busy:
            return
        self.conversation.clear()
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", "end")
        self.history_text.configure(state="disabled")
        self._append("assistant", "小 K 宝", "这一轮对话已经清空，我们可以重新开始。")
        self.status.configure(text="Enter 发送 · Shift + Enter 换行")

    def send_message(self) -> None:
        content = self.input_text.get("1.0", "end-1c").strip()
        if not content:
            self.status.configure(text="先写一句话，再发送给我吧。")
            return
        self.send_content(content)

    def send_content(self, content: str, compact: "CompactChatWindow | None" = None) -> None:
        if self.busy:
            if compact:
                compact.show_status("我还在回应上一句话，等我一下下就好。")
            return
        if not self.app.api_key:
            self._append("notice", "连接提示", "还没有 API Key。请右键小 K 宝，在月光设置中填写并应用。")
            self.status.configure(text="缺少 API Key，本次没有发送请求")
            if compact:
                compact.show_error("还没有配置 API Key", content)
            return

        if compact:
            compact.clear_input()
        else:
            self.input_text.delete("1.0", "end")
        self._append("user", "你", content)
        self.conversation.append({"role": "user", "content": content})
        self.busy = True
        self.send_button.configure(state="disabled", text="月光抵达中…")
        self.status.configure(text="我在认真听，也会尽快回应你…")
        if compact:
            compact.set_busy()
        messages = list(self.conversation)

        def worker() -> None:
            try:
                answer, usage = self.app.api_chat(messages)
                self.app.root.after(0, lambda: self._on_success(content, answer, usage, compact))
            except Exception as error:
                self.app.root.after(0, lambda message=str(error): self._on_error(content, message, compact))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(
        self, original: str, answer: str, usage: dict, compact: "CompactChatWindow | None" = None
    ) -> None:
        if self.app.closed or not self.window.winfo_exists():
            return
        self.conversation.append({"role": "assistant", "content": answer})
        self._append("assistant", "小 K 宝", answer)
        total = usage.get("total_tokens")
        if total is None:
            total = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        self.status.configure(text=f"本次 Token 用量：{total}" if total else "回复已收到")
        if compact:
            compact.show_result(answer, total)
        self._finish_request(compact)

    def _on_error(
        self, original: str, message: str, compact: "CompactChatWindow | None" = None
    ) -> None:
        if self.app.closed or not self.window.winfo_exists():
            return
        if self.conversation and self.conversation[-1].get("content") == original:
            self.conversation.pop()
        self._append("notice", "连接提示", f"这次没有连接成功：{message}")
        self.status.configure(text="内容已放回输入框，可以再发送一次")
        if compact:
            compact.show_error(message, original)
        else:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", original)
        self._finish_request(compact)

    def _finish_request(self, compact: "CompactChatWindow | None" = None) -> None:
        self.busy = False
        self.send_button.configure(state="normal", text="发送  ↗")
        if self.window.state() != "withdrawn":
            self.input_text.focus_set()
        if compact:
            compact.finish_request()

    def close(self) -> None:
        # 角色已收起时关闭聊天窗，会重新召唤角色，避免应用在后台无入口。
        if not self.app.pet_visible and not self.app.closed:
            self.app.summon_pet()
        super().close()


class CompactChatWindow:
    """收起角色后保留的一行长条对话栏，完整历史由 ChatWindow 保存。"""

    def __init__(self, app: "MoonPet", chat: ChatWindow) -> None:
        self.app = app
        self.chat = chat
        self.width, self.height = 720, 104
        self.window = tk.Toplevel(app.root)
        self.window.title("小 K 宝 · 月光对话栏")
        self.window.overrideredirect(True)
        self.window.configure(bg=BORDER, padx=1, pady=1)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        main = tk.Frame(self.window, bg=BG)
        main.pack(fill="both", expand=True)
        self.top = tk.Frame(main, bg=BG)
        self.top.pack(fill="x", pady=(5, 0))
        self.reply = tk.Label(
            self.top,
            text="我还在这里。想说话时写一句就好，不必把整片月亮都打开。",
            font=(FONT, 9),
            bg=BG,
            fg=MUTED,
            anchor="w",
            height=1,
        )
        self.reply.pack(side="left", fill="x", expand=True, padx=(14, 6))
        close = tk.Label(self.top, text="×", font=(FONT, 13), bg=BG, fg=MUTED, cursor="hand2")
        close.pack(side="right", padx=(0, 12))
        close.bind("<Button-1>", lambda _event: self.close())

        bottom = tk.Frame(main, bg=BG)
        bottom.pack(fill="x", padx=10, pady=(5, 8))
        tk.Label(bottom, text="☾", font=(FONT, 17), bg=BG, fg="#D9D1F5").pack(side="left", padx=(2, 8))
        self.input_var = tk.StringVar()
        self.entry = moon_entry(bottom, self.input_var)
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", self._send)
        self.send_button = moon_button(bottom, "发送", self.send, primary=True)
        self.send_button.pack(side="left", padx=(8, 0))
        moon_button(bottom, "召唤小 K 宝", self._summon).pack(side="left", padx=(8, 0))

        self._drag_origin = (0, 0)
        self._window_origin = (0, 0)
        for widget in (self.top, self.reply):
            widget.bind("<ButtonPress-1>", self._start_move)
            widget.bind("<B1-Motion>", self._move)
        self.window.bind("<Escape>", lambda _event: self.close())
        self._place_near_chat()
        self.entry.focus_set()

    def _place_near_chat(self) -> None:
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = self.chat.window.winfo_x()
        y = self.chat.window.winfo_y() + self.chat.window.winfo_height() - self.height
        x = max(12, min(x, screen_w - self.width - 12))
        y = max(12, min(y, screen_h - self.height - 70))
        self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def _start_move(self, event: tk.Event) -> None:
        self._drag_origin = (event.x_root, event.y_root)
        self._window_origin = (self.window.winfo_x(), self.window.winfo_y())

    def _move(self, event: tk.Event) -> None:
        dx = event.x_root - self._drag_origin[0]
        dy = event.y_root - self._drag_origin[1]
        self.window.geometry(f"+{self._window_origin[0] + dx}+{self._window_origin[1] + dy}")

    def _send(self, _event: tk.Event | None = None) -> str:
        self.send()
        return "break"

    def send(self) -> None:
        content = self.input_var.get().strip()
        if not content:
            self.show_status("写一句想说的话吧，我在听。")
            return
        self.chat.send_content(content, compact=self)

    def clear_input(self) -> None:
        self.input_var.set("")

    def set_busy(self) -> None:
        self.send_button.configure(state="disabled", text="等待月光…")
        self.show_status("我在认真听，回应很快就回来。")

    def finish_request(self) -> None:
        if self.window.winfo_exists():
            self.send_button.configure(state="normal", text="发送")
            self.entry.focus_set()

    def show_status(self, text: str) -> None:
        if self.window.winfo_exists():
            self.reply.configure(text=text)

    def show_result(self, answer: str, total: int) -> None:
        summary = " ".join(answer.split())
        if len(summary) > 82:
            summary = summary[:82] + "… 召唤后可查看完整回复"
        suffix = f"  ·  {total} Tokens" if total else ""
        self.show_status(f"小 K 宝：{summary}{suffix}")

    def show_error(self, message: str, original: str) -> None:
        self.input_var.set(original)
        self.show_status("连接没成功，内容已放回输入框，请再发送一次。")

    def _summon(self) -> None:
        self.app.summon_pet(restore_chat=True)

    def close(self) -> None:
        self.app.summon_pet(restore_chat=False)


class SettingsWindow(MoonToplevel):
    def __init__(self, app: "MoonPet") -> None:
        super().__init__(app, "月光设置", 450, 780)
        self.size = tk.StringVar(value=app.size_name.get())
        self.always_on_top = tk.BooleanVar(value=app.always_on_top.get())
        self.auto_walk = tk.BooleanVar(value=app.auto_walk.get())
        self.quiet_mode = tk.BooleanVar(value=app.quiet_mode.get())
        self.water_reminder = tk.BooleanVar(value=app.water_reminder.get())
        self.rest_reminder = tk.BooleanVar(value=app.rest_reminder.get())
        self.auto_start = tk.BooleanVar(value=app.auto_start.get())
        self.base_url = tk.StringVar(value=app.base_url)
        self.model = tk.StringVar(value=app.model)
        self.new_key = tk.StringVar()

        tk.Label(
            self.body,
            text="可以先一起修改，再点击“应用修改”一次生效。",
            font=(FONT, 9), bg=BG, fg=MUTED,
        ).pack(fill="x", pady=(0, 8))

        self._section("陪伴习惯")
        moon_check(self.body, "偶尔在桌面散步", self.auto_walk).pack(fill="x")
        moon_check(self.body, "安静模式（不主动说话）", self.quiet_mode).pack(fill="x")
        moon_check(self.body, "喝水提醒（每 45 分钟）", self.water_reminder).pack(fill="x")
        moon_check(self.body, "休息提醒（每 60 分钟）", self.rest_reminder).pack(fill="x")
        moon_check(self.body, "窗口总在最前", self.always_on_top).pack(fill="x")
        moon_check(self.body, "登录 Windows 后自动启动", self.auto_start).pack(fill="x")

        self._section("角色大小")
        sizes = tk.Frame(self.body, bg=BG)
        sizes.pack(fill="x")
        for name in SIZES:
            tk.Radiobutton(
                sizes,
                text=name,
                value=name,
                variable=self.size,
                font=(FONT, 10),
                bg=BG,
                fg=TEXT,
                selectcolor=FIELD,
                activebackground=BG,
                activeforeground=TEXT,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            ).pack(side="left", padx=(0, 18))

        self._section("API 对话")
        self._field_label("接口地址（OpenAI 兼容）")
        moon_entry(self.body, self.base_url).pack(fill="x", ipady=7)
        self._field_label("模型")
        model_row = tk.Frame(self.body, bg=BG)
        model_row.pack(fill="x")
        style = ttk.Style(self.window)
        style.theme_use("clam")
        style.configure(
            "Moon.TCombobox",
            fieldbackground=FIELD,
            background=FIELD,
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        self.window.option_add("*TCombobox*Listbox.background", FIELD)
        self.window.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.window.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.model_box = ttk.Combobox(
            model_row,
            textvariable=self.model,
            style="Moon.TCombobox",
            font=(FONT, 10),
        )
        self.model_box.pack(side="left", fill="x", expand=True, ipady=5)
        self.models_button = moon_button(model_row, "读取模型", self.load_models)
        self.models_button.pack(side="right", padx=(8, 0))

        self._field_label("API Key（留空则保留已保存密钥）")
        moon_entry(self.body, self.new_key, show="●").pack(fill="x", ipady=7)
        key_note = "本机已加密保存 API Key" if app.api_key else "密钥使用 Windows 用户级加密保存"
        tk.Label(self.body, text=key_note, font=(FONT, 8), bg=BG, fg=MUTED).pack(fill="x", pady=(5, 0))

        self.status = tk.Label(
            self.body,
            text="",
            font=(FONT, 9),
            bg=BG,
            fg="#C9BEF3",
            wraplength=390,
            justify="left",
        )
        self.status.pack(fill="x", pady=(8, 0))

        actions = tk.Frame(self.body, bg=BG)
        actions.pack(fill="x", pady=(8, 0))
        moon_button(actions, "应用修改", self.apply, primary=True).pack(side="left")
        moon_button(actions, "完成", self.close).pack(side="right")

        bottom = tk.Frame(self.body, bg=BG)
        bottom.pack(fill="x", pady=(10, 0))
        moon_button(bottom, "收起小 K 宝，保留对话", self._hide_pet).pack(side="left")
        moon_button(bottom, "彻底退出", self.app.quit_application).pack(side="right")

    def _section(self, text: str) -> None:
        tk.Label(
            self.body,
            text=text,
            font=(FONT, 10, "bold"),
            bg=BG,
            fg="#D9D1F5",
        ).pack(fill="x", pady=(9, 5))

    def _field_label(self, text: str) -> None:
        tk.Label(self.body, text=text, font=(FONT, 8), bg=BG, fg=MUTED).pack(fill="x", pady=(5, 3))

    def _hide_pet(self) -> None:
        self.close()
        self.app.hide_pet()

    def apply(self) -> None:
        try:
            self.app.apply_settings(
                size=self.size.get(),
                always_on_top=self.always_on_top.get(),
                auto_walk=self.auto_walk.get(),
                quiet_mode=self.quiet_mode.get(),
                water_reminder=self.water_reminder.get(),
                rest_reminder=self.rest_reminder.get(),
                auto_start=self.auto_start.get(),
                base_url=self.base_url.get(),
                model=self.model.get(),
                new_key=self.new_key.get(),
            )
            self.new_key.set("")
            self.status.configure(text="修改已保存。窗口可以继续调整，不会自动关闭。")
        except Exception as error:
            self.status.configure(text=f"保存失败：{error}")

    def load_models(self) -> None:
        if not self.app.api_key and not self.new_key.get().strip():
            self.status.configure(text="请先填写 API Key，再读取模型。")
            return
        self.models_button.configure(state="disabled", text="读取中…")
        self.status.configure(text="正在连接接口读取模型列表…")
        base_url = self.base_url.get()
        model = self.model.get()
        key = self.new_key.get().strip() or self.app.api_key

        def worker() -> None:
            try:
                client = APIClient(base_url, key, model or "model-discovery")
                models = client.list_models()
                self.app.root.after(0, lambda: self._models_loaded(models))
            except Exception as error:
                self.app.root.after(0, lambda message=str(error): self._models_failed(message))

        threading.Thread(target=worker, daemon=True).start()

    def _models_loaded(self, models: list[str]) -> None:
        if not self.window.winfo_exists():
            return
        self.model_box.configure(values=models)
        if self.model.get() not in models:
            self.model.set(models[0])
        self.models_button.configure(state="normal", text="读取模型")
        self.status.configure(text=f"已读取 {len(models)} 个可用模型，请选择后应用修改。")

    def _models_failed(self, message: str) -> None:
        if not self.window.winfo_exists():
            return
        self.models_button.configure(state="normal", text="读取模型")
        self.status.configure(text=f"读取失败：{message}")


class MoonPet:
    def __init__(self, persist: bool = True) -> None:
        self.persist = persist
        self.root = tk.Tk()
        self.root.title("小 K 宝")
        self.root.overrideredirect(True)
        self.root.configure(bg=CHROMA)
        self.root.attributes("-transparentcolor", CHROMA)

        self.config = self._load_config()
        self.size_name = tk.StringVar(value=self.config.get("size", "小巧"))
        if self.size_name.get() not in SIZES:
            self.size_name.set("小巧")
        self.always_on_top = tk.BooleanVar(value=self.config.get("always_on_top", True))
        self.auto_walk = tk.BooleanVar(value=self.config.get("auto_walk", False))
        self.quiet_mode = tk.BooleanVar(value=self.config.get("quiet_mode", False))
        self.water_reminder = tk.BooleanVar(value=self.config.get("water_reminder", True))
        self.rest_reminder = tk.BooleanVar(value=self.config.get("rest_reminder", True))
        self.auto_start = tk.BooleanVar(value=self.config.get("auto_start", True))
        self.base_url = self.config.get("base_url", "https://api.moonshot.cn/v1")
        self.model = self.config.get("model", "moonshot-v1-8k")
        try:
            self.api_key = load_api_key(KEY_PATH) if persist else ""
        except Exception:
            self.api_key = ""

        self.width, self.height, self.sprite_height = SIZES[self.size_name.get()]
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=CHROMA,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack()
        self.sprite_source = Image.open(SPRITE_PATH).convert("RGBA")
        self.sprite_image: ImageTk.PhotoImage | None = None
        self.sprite_item: int | None = None
        self.phase = 0.0
        self.dragging = False
        self.drag_moved = False
        self.drag_start = (0, 0)
        self.window_start = (0, 0)
        self.walk_target: int | None = None
        self.message_timer: str | None = None
        self.current_message = ""
        self.closed = False
        self.pet_visible = True
        self.chat_window: ChatWindow | None = None
        self.compact_window: CompactChatWindow | None = None
        self.settings_window: SettingsWindow | None = None

        self._rebuild_sprite()
        self._place_initial_window()
        self._bind_events()
        self.root.attributes("-topmost", self.always_on_top.get())
        self.root.protocol("WM_DELETE_WINDOW", self.quit_application)

        if self.persist and self.auto_start.get():
            try:
                autostart.set_enabled(True, ROOT_DIR)
            except Exception:
                pass

        self.root.after(60, self._animate)
        self.root.after(600, self._greet)
        self.root.after(12000, self._occasional_thought)
        self.root.after(45 * 60 * 1000, self._water_reminder)
        self.root.after(60 * 60 * 1000, self._rest_reminder)

    def _load_config(self) -> dict:
        if not self.persist or not CONFIG_PATH.exists():
            return {}
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_config(self) -> None:
        if not self.persist:
            return
        data = {
            "size": self.size_name.get(),
            "always_on_top": self.always_on_top.get(),
            "auto_walk": self.auto_walk.get(),
            "quiet_mode": self.quiet_mode.get(),
            "water_reminder": self.water_reminder.get(),
            "rest_reminder": self.rest_reminder.get(),
            "auto_start": self.auto_start.get(),
            "base_url": self.base_url,
            "model": self.model,
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
        }
        try:
            CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _rebuild_sprite(self) -> None:
        ratio = self.sprite_height / self.sprite_source.height
        size = (max(1, round(self.sprite_source.width * ratio)), self.sprite_height)
        resized = self.sprite_source.resize(size, Image.Resampling.LANCZOS)
        mask = resized.getchannel("A").point(lambda value: 255 if value >= 160 else 0)
        background = Image.new("RGB", size, ImageColor.getrgb(CHROMA))
        background.paste(resized.convert("RGB"), (0, 0), mask)
        self.sprite_image = ImageTk.PhotoImage(background)
        if self.sprite_item is None:
            self.sprite_item = self.canvas.create_image(
                self.width // 2, self.height - 14, image=self.sprite_image, anchor="s"
            )
        else:
            self.canvas.itemconfigure(self.sprite_item, image=self.sprite_image)
        self.canvas.tag_lower(self.sprite_item)

    def _place_initial_window(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        default_x = screen_w - self.width - 48
        default_y = screen_h - self.height - 88
        x = self.config.get("x", default_x)
        y = self.config.get("y", default_y)
        try:
            x, y = int(x), int(y)
        except (TypeError, ValueError):
            x, y = default_x, default_y
        if not (-self.width // 2 < x < screen_w - 30 and -self.height // 2 < y < screen_h - 30):
            x, y = default_x, default_y
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def _bind_events(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Button-3>", lambda _event: self.open_settings())
        self.canvas.bind("<Double-Button-1>", lambda _event: self.open_chat())

    def _drag_start(self, event: tk.Event) -> None:
        self.dragging = True
        self.drag_moved = False
        self.drag_start = (event.x_root, event.y_root)
        self.window_start = (self.root.winfo_x(), self.root.winfo_y())
        self.walk_target = None

    def _drag_motion(self, event: tk.Event) -> None:
        if not self.dragging:
            return
        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]
        if abs(dx) + abs(dy) > 5:
            self.drag_moved = True
        self.root.geometry(f"+{self.window_start[0] + dx}+{self.window_start[1] + dy}")

    def _drag_end(self, _event: tk.Event) -> None:
        was_click = not self.drag_moved
        self.dragging = False
        self._save_config()
        if was_click:
            self.open_chat()

    def open_chat(self) -> ChatWindow:
        if self.compact_window and self.compact_window.window.winfo_exists():
            self.compact_window.window.destroy()
        self.compact_window = None
        if self.chat_window is None or not self.chat_window.window.winfo_exists():
            self.chat_window = ChatWindow(self)
        self.chat_window.show()
        return self.chat_window

    def open_settings(self) -> SettingsWindow:
        if self.settings_window is None or not self.settings_window.window.winfo_exists():
            self.settings_window = SettingsWindow(self)
        self.settings_window.show()
        return self.settings_window

    def api_chat(self, messages: list[dict[str, str]]) -> tuple[str, dict]:
        client = APIClient(self.base_url, self.api_key, self.model)
        recent = messages[-12:]
        return client.chat([{"role": "system", "content": SYSTEM_PROMPT}] + recent)

    def apply_settings(self, **values) -> None:
        new_key = values.pop("new_key", "").strip()
        if new_key:
            save_api_key(new_key, KEY_PATH)
            self.api_key = new_key

        auto_start_value = values.pop("auto_start")
        if self.persist:
            autostart.set_enabled(auto_start_value, ROOT_DIR)
        self.auto_start.set(auto_start_value)

        new_size = values.pop("size")
        self.always_on_top.set(values.pop("always_on_top"))
        self.auto_walk.set(values.pop("auto_walk"))
        self.quiet_mode.set(values.pop("quiet_mode"))
        self.water_reminder.set(values.pop("water_reminder"))
        self.rest_reminder.set(values.pop("rest_reminder"))
        self.base_url = values.pop("base_url").strip().rstrip("/")
        self.model = values.pop("model").strip()
        if not self.base_url or not self.model:
            raise ValueError("接口地址和模型名称不能为空。")

        if new_size != self.size_name.get():
            self.size_name.set(new_size)
            self._change_size()
        self.root.attributes("-topmost", self.always_on_top.get())
        if not self.auto_walk.get():
            self.walk_target = None
        self._save_config()

    def hide_pet(self) -> None:
        chat = self.open_chat()
        self.pet_visible = False
        self.root.withdraw()
        chat.window.withdraw()
        if self.compact_window and self.compact_window.window.winfo_exists():
            self.compact_window.window.destroy()
        self.compact_window = CompactChatWindow(self, chat)

    def summon_pet(self, restore_chat: bool = True) -> None:
        if self.compact_window and self.compact_window.window.winfo_exists():
            self.compact_window.window.destroy()
        self.compact_window = None
        self.pet_visible = True
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", self.always_on_top.get())
        if self.chat_window and self.chat_window.window.winfo_exists():
            if restore_chat:
                self.chat_window.show()
                self.chat_window.status.configure(text="小 K 宝已经回到桌面上啦")
            else:
                self.chat_window.window.withdraw()

    def _change_size(self) -> None:
        old_center = self.root.winfo_x() + self.width // 2
        old_bottom = self.root.winfo_y() + self.height
        self.width, self.height, self.sprite_height = SIZES[self.size_name.get()]
        self.canvas.configure(width=self.width, height=self.height)
        self.root.geometry(f"{self.width}x{self.height}+{old_center - self.width // 2}+{old_bottom - self.height}")
        self._rebuild_sprite()
        self.canvas.coords(self.sprite_item, self.width // 2, self.height - 14)
        if self.current_message:
            self._draw_bubble(self.current_message)

    def _rounded_rectangle(self, x1: int, y1: int, x2: int, y2: int, radius: int) -> None:
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        self.canvas.create_polygon(
            points, smooth=True, splinesteps=36, fill=MOON, outline="#A8A0D0", width=2, tags="bubble"
        )

    def _draw_bubble(self, text: str) -> None:
        self.canvas.delete("bubble")
        self._rounded_rectangle(18, 12, self.width - 18, 94, 18)
        self.canvas.create_polygon(
            self.width // 2 - 10, 91, self.width // 2 + 12, 91, self.width // 2 + 2, 108,
            fill=MOON, outline="#A8A0D0", tags="bubble",
        )
        self.canvas.create_text(
            self.width // 2, 53, text=f"☾  {text}", fill="#29243E", font=(FONT, 10),
            width=self.width - 66, justify="center", tags="bubble",
        )
        self.canvas.tag_raise("bubble")

    def show_message(self, text: str, duration: int = 4600) -> None:
        if not self.pet_visible:
            return
        if self.message_timer is not None:
            self.root.after_cancel(self.message_timer)
        self.current_message = text
        self._draw_bubble(text)
        self.message_timer = self.root.after(duration, self.hide_message)

    def hide_message(self) -> None:
        self.canvas.delete("bubble")
        self.current_message = ""
        self.message_timer = None

    def _greet(self) -> None:
        self.show_message("点我打开对话框，右键进入月光设置。", 6500)

    def _occasional_thought(self) -> None:
        if not self.closed and not self.quiet_mode.get() and not self.current_message:
            if random.random() < 0.65:
                self.show_message(random.choice(MESSAGES), 5200)
        if not self.closed:
            self.root.after(random.randint(90000, 180000), self._occasional_thought)

    def _water_reminder(self) -> None:
        if not self.closed:
            if self.water_reminder.get():
                self.show_message("喝几口水吧。照顾工作之前，先照顾自己。", 6500)
            self.root.after(45 * 60 * 1000, self._water_reminder)

    def _rest_reminder(self) -> None:
        if not self.closed:
            if self.rest_reminder.get():
                self.show_message("已经一小时啦，看看远处，让眼睛休息一下吧。", 6500)
            self.root.after(60 * 60 * 1000, self._rest_reminder)

    def _animate(self) -> None:
        if self.closed:
            return
        self.phase += 0.075
        bob = round(math.sin(self.phase) * 3)
        self.canvas.coords(self.sprite_item, self.width // 2, self.height - 14 + bob)
        if self.pet_visible and self.auto_walk.get() and not self.dragging:
            if self.walk_target is None and random.random() < 0.008:
                screen_w = self.root.winfo_screenwidth()
                self.walk_target = random.randint(12, max(12, screen_w - self.width - 12))
            if self.walk_target is not None:
                x = self.root.winfo_x()
                difference = self.walk_target - x
                if abs(difference) <= 2:
                    self.walk_target = None
                else:
                    self.root.geometry(f"+{x + (1 if difference > 0 else -1)}+{self.root.winfo_y()}")
        self.root.after(55, self._animate)

    def capture(self, output: Path) -> None:
        self.root.update_idletasks()
        screenshot = ImageGrab.grab(all_screens=True)
        scale_x = screenshot.width / self.root.winfo_screenwidth()
        scale_y = screenshot.height / self.root.winfo_screenheight()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        bbox = (
            round(x * scale_x), round(y * scale_y),
            round((x + self.width) * scale_x), round((y + self.height) * scale_y),
        )
        screenshot.crop(bbox).save(output)
        print(f"Captured: {output}")

    def quit_application(self) -> None:
        if self.closed:
            return
        self._save_config()
        self.closed = True
        for window in (self.chat_window, self.compact_window, self.settings_window):
            if window is not None and window.window.winfo_exists():
                window.window.destroy()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def acquire_single_instance():
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "Local\\XiaoKPetSingleInstance")
    if kernel32.GetLastError() == 183:
        return False
    return handle


def main() -> None:
    parser = argparse.ArgumentParser(description="小 K 宝 API 桌面宠物")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    if not SPRITE_PATH.exists():
        raise FileNotFoundError(f"缺少角色素材：{SPRITE_PATH}")

    mutex = None
    if not (args.smoke_test or args.capture):
        mutex = acquire_single_instance()
        if mutex is False:
            return

    pet = MoonPet(persist=not (args.smoke_test or args.capture))
    if args.capture:
        pet.root.after(1300, lambda: pet.capture(args.capture.resolve()))
        pet.root.after(1800, pet.quit_application)
    elif args.smoke_test:
        pet.root.after(900, lambda: print("SMOKE_TEST_OK", flush=True))
        pet.root.after(1000, pet.quit_application)
    pet.run()
    _ = mutex


if __name__ == "__main__":
    main()
