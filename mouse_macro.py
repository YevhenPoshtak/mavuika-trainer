"""
Genshin Mouse Macro
"""

import tkinter as tk
import threading
import time
import random
import ctypes
import ctypes.wintypes

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ─── Правильні типи для 64-bit ────────────────────────────────────────────────
user32.SetWindowsHookExW.restype  = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.wintypes.DWORD]

user32.CallNextHookEx.restype  = ctypes.c_long
user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]

user32.UnhookWindowsHookEx.restype  = ctypes.wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]

user32.GetMessageW.restype  = ctypes.wintypes.BOOL
user32.PostThreadMessageW.restype  = ctypes.wintypes.BOOL

kernel32.GetCurrentThreadId.restype = ctypes.wintypes.DWORD

# HOOKPROC з правильними типами для 64-bit
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM)

WH_KEYBOARD_LL  = 13
WH_MOUSE_LL     = 14
WM_KEYDOWN      = 0x0100
WM_SYSKEYDOWN   = 0x0104
WM_MBUTTONDOWN  = 0x0207
WM_XBUTTONDOWN  = 0x020B
LLMHF_INJECTED  = 0x00000001


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",      ctypes.wintypes.DWORD),
        ("scanCode",    ctypes.wintypes.DWORD),
        ("flags",       ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt",          ctypes.wintypes.POINT),
        ("mouseData",   ctypes.wintypes.DWORD),
        ("flags",       ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# ─── SendInput ────────────────────────────────────────────────────────────────
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   ctypes.wintypes.DWORD),
        ("dwFlags",     ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_u", _U)]

MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010

BTN_FLAGS = {
    ("press",   "left"):  MOUSEEVENTF_LEFTDOWN,
    ("release", "left"):  MOUSEEVENTF_LEFTUP,
    ("press",   "right"): MOUSEEVENTF_RIGHTDOWN,
    ("release", "right"): MOUSEEVENTF_RIGHTUP,
}

def send_mouse(flags):
    i = INPUT(type=0)
    i._u.mi.dwFlags = flags
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))


SEQUENCE = [
    ("press",   "left",   200, 15),
    ("press",   "right",   50, 5),
    ("release", "right",   70, 10),
    ("release", "left",    50, 10),
    ("press",   "left",   200, 15),
    ("press",   "right",   50, 5),
    ("release", "right", 1020, 20),
    ("release", "left",   520, 20),
]


def vk_to_name(vk):
    buf = ctypes.create_unicode_buffer(64)
    scan = user32.MapVirtualKeyW(vk, 0)
    if user32.GetKeyNameTextW(scan << 16, buf, 64):
        return buf.value
    return f"VK {vk}"


class MacroApp:
    BG = "#0d1117"; CARD = "#161b22"; BORDER = "#30363d"
    GREEN = "#3fb950"; RED = "#f85149"; FG = "#e6edf3"
    GREY = "#8b949e"; CYAN = "#79c0ff"

    def __init__(self, root):
        self.root = root
        root.title("Genshin Macro")
        root.resizable(False, False)
        root.configure(bg=self.BG)
        root.wm_attributes("-topmost", True)

        self._enabled      = False
        self._binding      = False
        self._hotkey       = None
        self._count        = 0
        self._macro_thread = None
        self._kb_proc      = None
        self._ms_proc      = None
        self._hook_tid     = None
        self._playing      = False

        self._build_ui()
        threading.Thread(target=self._hook_loop, daemon=True).start()

    def _build_ui(self):
        P = dict(padx=14, pady=5)
        hdr = tk.Frame(self.root, bg=self.BG)
        hdr.pack(fill="x", padx=14, pady=(14,2))
        tk.Label(hdr, text="⚔  Genshin Macro", bg=self.BG, fg=self.FG,
                 font=("Segoe UI",13,"bold")).pack(side="left")
        tk.Label(hdr, text="always on top", bg=self.BG, fg=self.GREY,
                 font=("Segoe UI",8)).pack(side="right", pady=4)
        tk.Frame(self.root, bg=self.BORDER, height=1).pack(fill="x", padx=14, pady=(2,8))

        cb = tk.Frame(self.root, bg=self.CARD,
                      highlightbackground=self.BORDER, highlightthickness=1)
        cb.pack(fill="x", **P)
        tk.Label(cb, text="Гаряча клавіша", bg=self.CARD, fg=self.GREY,
                 font=("Segoe UI",8)).pack(anchor="w", padx=10, pady=(8,0))
        row = tk.Frame(cb, bg=self.CARD)
        row.pack(fill="x", padx=10, pady=(2,10))
        self._hk_lbl = tk.Label(row, text="— не задано —", bg=self.CARD,
                                 fg=self.CYAN, font=("Consolas",11,"bold"),
                                 width=18, anchor="w")
        self._hk_lbl.pack(side="left")
        self._bind_btn = tk.Button(row, text="Призначити", bg="#21262d",
                                   fg=self.FG, relief="flat",
                                   font=("Segoe UI",9), padx=10, pady=4,
                                   cursor="hand2", activebackground="#30363d",
                                   activeforeground=self.FG,
                                   command=self._start_bind)
        self._bind_btn.pack(side="right")

        cs = tk.Frame(self.root, bg=self.CARD,
                      highlightbackground=self.BORDER, highlightthickness=1)
        cs.pack(fill="x", **P)
        tk.Label(cs, text="Послідовність  (±25 мс рандом)", bg=self.CARD,
                 fg=self.GREY, font=("Segoe UI",8)).pack(anchor="w", padx=10, pady=(8,2))
        tk.Label(cs, text="▼L 200  ▼R 50  ▲R 70  ▲L 50\n▼L 200  ▼R 50  ▲R 1020  ▲L 520",
                 bg=self.CARD, fg=self.CYAN, font=("Consolas",9),
                 justify="left").pack(anchor="w", padx=10, pady=(0,10))

        self._tog_btn = tk.Button(self.root, text="▶  Увімкнути",
                                  bg=self.GREEN, fg="#0d1117", relief="flat",
                                  cursor="hand2", font=("Segoe UI",11,"bold"),
                                  pady=8, activebackground="#2ea043",
                                  activeforeground="#0d1117", command=self._toggle)
        self._tog_btn.pack(fill="x", padx=14, pady=(6,4))

        self._sv = tk.StringVar(value="Вимкнено")
        tk.Label(self.root, textvariable=self._sv, bg=self.BG, fg=self.GREY,
                 font=("Segoe UI",9)).pack(pady=(0,2))
        self._cv = tk.StringVar(value="Циклів: 0")
        tk.Label(self.root, textvariable=self._cv, bg=self.BG, fg=self.GREY,
                 font=("Segoe UI",9)).pack(pady=(0,12))

    def _start_bind(self):
        self._binding = True
        self._bind_btn.configure(text="Натисни кнопку...", bg="#388bfd", fg="white")
        self._hk_lbl.configure(text="очікую...", fg=self.GREY)

    def _save_bind(self, hk, name):
        self._hotkey  = hk
        self._binding = False
        self.root.after(0, lambda: self._hk_lbl.configure(text=name, fg=self.CYAN))
        self.root.after(0, lambda: self._bind_btn.configure(
            text="Призначити", bg="#21262d", fg=self.FG))

    def _hook_loop(self):
        self._hook_tid = kernel32.GetCurrentThreadId()

        def kb_proc(nCode, wParam, lParam):
            try:
                if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if not (kb.flags & LLMHF_INJECTED):
                        vk = kb.vkCode
                        if self._binding:
                            self._save_bind({"type":"key","vk":vk}, vk_to_name(vk))
                        elif (self._enabled and self._hotkey and
                              self._hotkey.get("type") == "key" and
                              self._hotkey["vk"] == vk):
                            self._fire_macro()
            except Exception:
                pass
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        def ms_proc(nCode, wParam, lParam):
            try:
                if nCode >= 0 and wParam in (WM_MBUTTONDOWN, WM_XBUTTONDOWN):
                    ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    if ms.flags & LLMHF_INJECTED:
                        return user32.CallNextHookEx(None, nCode, wParam, lParam)

                    xbtn = 0
                    if wParam == WM_XBUTTONDOWN:
                        xbtn = (ms.mouseData >> 16) & 0xFFFF

                    if self._binding:
                        name = "Mouse Middle" if wParam == WM_MBUTTONDOWN else (
                               "Mouse 4" if xbtn == 1 else "Mouse 5")
                        self._save_bind({"type":"mouse","msg":wParam,"xbtn":xbtn}, name)
                        return 1
                    elif (self._enabled and self._hotkey and
                          self._hotkey.get("type") == "mouse" and
                          self._hotkey["msg"] == wParam and
                          self._hotkey.get("xbtn", 0) == xbtn):
                        self._fire_macro()
            except Exception:
                pass
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        self._kb_proc = HOOKPROC(kb_proc)
        self._ms_proc = HOOKPROC(ms_proc)

        kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, None, 0)
        ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL,    self._ms_proc, None, 0)

        if not kb_hook or not ms_hook:
            err = kernel32.GetLastError()
            self.root.after(0, lambda: self._sv.set(f"❌ Помилка хуку: {err}"))
            return

        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnhookWindowsHookEx(kb_hook)
        user32.UnhookWindowsHookEx(ms_hook)

    def _fire_macro(self):
        if self._playing:
            self._playing = False
            return
        self._playing = True
        if self._macro_thread and self._macro_thread.is_alive():
            return
        self._macro_thread = threading.Thread(target=self._run_macro, daemon=True)
        self._macro_thread.start()

    def _run_macro(self):
        self.root.after(0, lambda: self._sv.set("▶ Виконується (Зациклено)..."))
        
        # Absolute rigid timeline starting now
        target_time = time.perf_counter()
        
        while self._playing and self._enabled:
            for action, btn, delay, rand in SEQUENCE:
                if not self._playing or not self._enabled:
                    break
                f = BTN_FLAGS.get((action, btn))
                if f:
                    send_mouse(f)
                
                # Advance rigid target time by exact base delay to prevent baseline drift
                target_time += delay / 1000.0
                
                # Add jitter to the actual sleep target, keeping the baseline intact
                jitter = random.randint(-rand, rand) / 1000.0
                actual_target = target_time + jitter
                
                while True:
                    now = time.perf_counter()
                    if now >= actual_target or not self._playing or not self._enabled:
                        break
                    if actual_target - now > 0.015:
                        time.sleep(0.01)
                    else:
                        time.sleep(0) # CPU-friendly busy wait for microsecond precision

            if self._playing and self._enabled:
                self._count += 1
                n = self._count
                self.root.after(0, lambda: self._cv.set(f"Циклів: {n}"))
                
        self._playing = False
        send_mouse(MOUSEEVENTF_LEFTUP)
        send_mouse(MOUSEEVENTF_RIGHTUP)
        if self._enabled:
            self.root.after(0, lambda: self._sv.set("Очікує натискання"))

    def _toggle(self):
        if not self._hotkey:
            self._sv.set("Спочатку призначте кнопку!")
            return
        self._enabled = not self._enabled
        if self._enabled:
            self._tog_btn.configure(text="⏹  Вимкнути", bg=self.RED,
                                    fg="white", activebackground="#da3633")
            self._sv.set("Очікує натискання")
        else:
            self._playing = False
            self._tog_btn.configure(text="▶  Увімкнути", bg=self.GREEN,
                                    fg="#0d1117", activebackground="#2ea043")
            self._sv.set("Вимкнено")

    def on_close(self):
        self._enabled = False
        if self._hook_tid:
            user32.PostThreadMessageW(self._hook_tid, 0x0012, 0, 0)
        self.root.destroy()


def main():
    root = tk.Tk()
    app  = MacroApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()