#!/usr/bin/env python3
"""English Lens - drag a box over English text on screen, get a Chinese learning panel.

Zero installs: stdlib + tkinter + the OCR already on this machine (ocr_rect.ps1).

  python lens.py                 run: wait for the hotkey
  python lens.py --selftest      show a known sentence, OCR it back, PASS/FAIL
  python lens.py --check         config + credential + API round trip
  python lens.py --ocr X Y W H   OCR a screen rect, print raw text
  python lens.py --ask "text"    run the learning prompt on text, print the panel
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOTKEY = ("ctrl", "alt", "S")            # the only line to change for a different shortcut
MODEL = os.environ.get("LENS_MODEL", "deepseek-v4-flash")
CONFIG = Path(os.environ.get("LENS_CONFIG", r"D:\Program Files\Hermes\config.yaml"))
TIMEOUT = 25                              # seconds per OCR / HTTP step
MIN_BOX = 8                               # px: anything smaller is treated as a stray click

PROMPT = """你正在帮我学英语。下面是我从屏幕上框选、经 OCR 识别出来的文字（可能有识别噪声）。

请在保持简洁的前提下输出三部分，不要任何客套话：
1. 语境翻译：一段通顺的中文。如果原文是多行、菜单、标题或碎片，就按它的实际意思顺译，不要逐词硬译。
2. 生词/词组：挑 3-5 个最值得学的，每行一个，格式 `英文 | 词性 | 在这句话里的意思`。不要选 he/is/the 这类词。
3. 一句话说明：这句话的语法点或地道用法。如果原文不是完整句子，就说明它通常出现在什么场景。

如果文字明显不是有效英文（只有符号、乱码、OCR 噪声），只回复：没识别到有效英文。不要编造。"""


def dpi_aware():
    """Native pixels, or a 150%-scaled screen is captured downscaled and OCR halves."""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def creds():
    """(base_url, api_key): env vars win, else the Hermes config's custom_providers entry."""
    if os.environ.get("LENS_API_KEY"):
        base = os.environ.get("LENS_BASE_URL", "https://api.deepseek.com")
        return base.rstrip("/"), os.environ["LENS_API_KEY"]
    txt = CONFIG.read_text(encoding="utf-8", errors="replace")
    wanted = re.search(r"^\s*provider:\s*custom:([\w.-]+)", txt, re.M)
    block = re.search(r"^custom_providers:\s*$(.*?)(?=^\S)", txt, re.M | re.S)
    if not (wanted and block):
        raise RuntimeError(f"no custom_providers entry in {CONFIG} - set LENS_BASE_URL and LENS_API_KEY instead")
    for part in re.split(r"^\s*-\s*name:\s*", block.group(1), flags=re.M)[1:]:
        if part.splitlines()[0].strip() != wanted.group(1):
            continue
        base = re.search(r"base_url:\s*(\S+)", part).group(1).strip("'\"")
        key = re.search(r"api_key:\s*(\S+)", part).group(1).strip("'\"")
        if key.startswith("${"):
            raise RuntimeError("config stores an env reference for api_key - set LENS_API_KEY instead")
        return base.rstrip("/"), key
    raise RuntimeError(f"provider '{wanted.group(1)}' not found in {CONFIG}")


THINK_OFF = {"thinking": {"type": "disabled"}}   # DeepSeek-style switch: without it AND temperature 0 a
                                                 # thinking model spends the whole budget on reasoning and
                                                 # returns an empty message. Non-DeepSeek providers reject the
                                                 # field, so translate() retries without it after a 400.


def _chat(url, key, text, extra):
    payload = {"model": MODEL, "temperature": 0, "max_tokens": 800,
               "messages": [{"role": "system", "content": PROMPT},
                            {"role": "user", "content": text}]}
    payload.update(extra)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def translate(text):
    base, key = creds()
    last = None
    # base may or may not end in /v1; a non-DeepSeek provider may reject the thinking field
    for path, extra in (("/v1/chat/completions", THINK_OFF), ("/chat/completions", THINK_OFF),
                        ("/v1/chat/completions", {}), ("/chat/completions", {})):
        try:
            return _chat(base + path, key, text, extra)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 404, 405):
                raise
            last = e
    raise last


def ocr(x, y, w, h):
    p = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "ocr_rect.ps1"),
         "-X", str(int(x)), "-Y", str(int(y)), "-W", str(int(w)), "-H", str(int(h))],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=0x08000000)          # no console flash
    if p.returncode and p.returncode != 3:        # 3 = capture + OCR worked, the region just had no text
        why = (p.stderr or p.stdout or "OCR failed").strip().splitlines()[0].strip()[:200]
        if "handle is invalid" in why or "句柄无效" in why:      # locked desktop: no rendered surface to copy
            why += " (屏幕被锁定时无法截屏，解锁后再试)"
        raise RuntimeError(why)
    return p.stdout.strip()


WM_HOTKEY = 0x0312
MOD = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("message", wt.UINT), ("wParam", wt.WPARAM),
                ("lParam", wt.LPARAM), ("time", wt.DWORD), ("pt", wt.POINT)]


def hotkey_mods():
    mods = 0
    for m in HOTKEY[:-1]:
        mods |= MOD[m.lower()]
    return mods


def hotkey_free():
    """Is the combo still ours to take? Register and release at once."""
    u = ctypes.windll.user32
    ok = bool(u.RegisterHotKey(None, 99, hotkey_mods(), ord(HOTKEY[-1].upper())))
    if ok:
        u.UnregisterHotKey(None, 99)
    return ok


def hotkey_loop(out):
    """RegisterHotKey + GetMessageW must share one thread nobody else drains: Tk's own pump eats
    WM_HOTKEY (posted with hwnd=NULL) before any polling of ours can see it. Measured, not guessed:
    a plain process sees the message, the Tk app does not."""
    u = ctypes.windll.user32
    ok = bool(u.RegisterHotKey(None, 1, hotkey_mods(), ord(HOTKEY[-1].upper())))
    out.put(("hotkey", ok))
    if not ok:
        return
    msg = MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            out.put(("select", None))


def already_running():
    """Named mutex = single instance. Without it a second copy only says 'hotkey busy', which
    reads as a conflict with another app - and the tool is invisible, so users do re-launch it."""
    global _MUTEX
    _MUTEX = ctypes.WinDLL("kernel32", use_last_error=True).CreateMutexW(None, False, "EnglishLens_single")
    return ctypes.get_last_error() == 183          # ERROR_ALREADY_EXISTS


def content_lines(text, width=46):
    """Rough wrapped-line count, CJK counted double: without it Tk reserves 24 empty rows and every
    panel is 670px tall (measured) with the text lost at the top."""
    return sum(max(1, -(-sum(2 if ord(c) > 0x2E80 else 1 for c in line) // width))
               for line in text.splitlines()) + 1


def panel(root, text, x=40, y=40, w=0, h=0):
    """The floating box: results, warnings and start-up hints all use this one."""
    p = tk.Toplevel(root)
    p.overrideredirect(True)
    p.attributes("-topmost", True)
    body = tk.Text(p, wrap="word", width=48, height=min(28, content_lines(text)), relief="flat", cursor="arrow",
                   bg="#1f1f1f", fg="#f2f2f2", padx=12, pady=10, font=("Microsoft YaHei UI", 10))
    body.insert("1.0", text)
    body.config(state="disabled")
    body.pack()
    p.update_idletasks()
    sw, sh = p.winfo_screenwidth(), p.winfo_screenheight()
    pw = p.winfo_reqwidth()
    ph = min(p.winfo_reqheight(), int(sh * 0.7))
    px = min(max(x, 4), max(4, sw - pw - 4))
    py = y + h + 10
    if py + ph > sh - 4:
        py = max(4, y - ph - 10)
    p.geometry(f"{pw}x{ph}+{px}+{py}")
    p.bind("<Escape>", lambda e: p.destroy())
    p.bind("<Button-3>", lambda e: p.destroy())
    p.focus_force()
    return p


def say(text, seconds=4.0):
    """Self-closing hint panel: the tool waits invisibly, so it has to speak at least once."""
    root = tk.Tk()
    root.withdraw()
    panel(root, text, max(40, root.winfo_screenwidth() // 2 - 260), 80)
    root.after(int(seconds * 1000), root.destroy)
    root.mainloop()


class Lens:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.results = queue.Queue()
        self.panel = None
        self.panel_at = 0.0
        self.lbtn = False
        self.overlay = None
        self.root.after(40, self.tick)
        threading.Thread(target=hotkey_loop, args=(self.results,), daemon=True).start()
        threading.Thread(target=self.smoke, daemon=True).start()   # silent unless the pixels are broken

    def tick(self):
        while not self.results.empty():
            kind, payload = self.results.get()
            if kind == "select":
                self.select()
            elif kind == "hotkey" and not payload:
                self.note(f"快捷键 {'+'.join(HOTKEY)} 被别的程序占用了。\n改 scripts/lens.py 顶部那一行 HOTKEY 后重启。")
                self.root.after(9000, self.root.destroy)   # no hotkey = useless instance, do not lurk
            elif kind == "panel":
                self.show(*payload)
        # Click anywhere outside the panel = close it. Two details make this work:
        # * GetAsyncKeyState's low bit is the *latched* press bit since our last poll, so a fast click
        #   (down+up inside one 40ms tick) is not missed. show() clears the stale latch.
        # * it needs no focus and no hook, unlike focus-based dismissal, which fails whenever Windows
        #   refuses to hand us the foreground (measured: the panel was killed 0.4s after appearing).
        p = self.panel
        if p is not None:
            pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x0001)
            if pressed and time.time() - self.panel_at > 0.4:          # grace: the click that opened it
                try:
                    cur = wt.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(cur))
                    x, y = p.winfo_rootx(), p.winfo_rooty()
                    w, h = p.winfo_width(), p.winfo_height()
                    if not (x <= cur.x < x + w and y <= cur.y < y + h):
                        self.close_panel()
                except tk.TclError:                    # panel already gone
                    self.close_panel()
        self.root.after(40, self.tick)

    def select(self):
        if self.overlay:
            return
        self.close_panel()
        r = self.root
        vx, vy = r.winfo_vrootx(), r.winfo_vrooty()
        ov = tk.Toplevel(r)
        ov.overrideredirect(True)
        ov.geometry(f"{r.winfo_vrootwidth()}x{r.winfo_vrootheight()}+{vx}+{vy}")
        ov.attributes("-topmost", True, "-alpha", 0.25)
        cv = tk.Canvas(ov, bg="black", highlightthickness=0, cursor="crosshair")
        cv.pack(fill="both", expand=True)
        start = {}

        def drag(e):
            if "x" in start:
                cv.delete("band")
                cv.create_rectangle(start["x"], start["y"], e.x, e.y, outline="#e33", width=2, tags="band")

        def release(e):
            box = (start.get("x", e.x), start.get("y", e.y), e.x, e.y)
            self.overlay = None
            ov.destroy()
            x, y = min(box[0], box[2]), min(box[1], box[3])
            w, h = abs(box[2] - box[0]), abs(box[3] - box[1])
            if w >= MIN_BOX and h >= MIN_BOX:      # OCR runs off-thread: a hung request never freezes the UI
                threading.Thread(target=self.work, args=(vx + x, vy + y, w, h), daemon=True).start()

        cv.bind("<Button-1>", lambda e: start.update(x=e.x, y=e.y))
        cv.bind("<B1-Motion>", drag)
        cv.bind("<ButtonRelease-1>", release)
        ov.bind("<Escape>", lambda e: (setattr(self, "overlay", None), ov.destroy()))
        self.overlay = ov
        ov.focus_force()
        ov.grab_set()

    def work(self, x, y, w, h):
        try:
            text = ocr(x, y, w, h)
            if len(re.sub(r"[^A-Za-z]", "", text)) < 2:
                panel = "这一段里没识别到英文。\n\n换一段纯文字的英文，框大一点再试。"
            else:
                panel = translate(text) or "模型这次返回了空内容，再框一次试试。"
        except Exception as e:
            panel = f"出错了：{type(e).__name__}: {e}"
        self.results.put(("panel", (panel, x, y, w, h)))

    def show(self, text, x=40, y=40, w=0, h=0):
        self.close_panel()
        self.panel = panel(self.root, text, x, y, w, h)
        self.panel_at = time.time()
        ctypes.windll.user32.GetAsyncKeyState(0x01)     # clear the latched press bit from before the panel
        self.panel.bind("<Escape>", lambda e: self.close_panel())        # override panel()'s own bindings so
        self.panel.bind("<Button-3>", lambda e: self.close_panel())      # self.panel never dangles
        return self.panel

    def smoke(self):
        """Start-up self-check: empty text is fine (exit 3), an exception means capture is dead."""
        try:
            ocr(0, 0, 240, 60)
        except Exception as e:
            self.results.put(("panel", (f"截屏/OCR 不可用：{e}\n\n解锁屏幕后重新启动。", 40, 40, 0, 0)))

    def note(self, text):
        self.show(text)

    def close_panel(self):
        p, self.panel = self.panel, None
        if p is not None:
            try:
                p.destroy()
            except tk.TclError:        # already closed by Esc / right-click
                pass


def selftest():
    """Show a known sentence, OCR the same pixels back, report PASS/FAIL."""
    dpi_aware()
    want = "The quick brown fox jumps over the lazy dog 42"
    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry("1300x150+260+620")
    root.attributes("-topmost", True)
    tk.Label(root, text=want, font=("Consolas", 26), bg="white", fg="black").pack(fill="both", expand=True)
    got = {}

    def grab():
        try:
            got["text"] = ocr(290, 660, 1240, 70)
        except Exception as e:
            got["text"] = f"<{type(e).__name__}: {e}>"
        root.destroy()

    root.after(800, grab)
    root.mainloop()
    hit = sum(word in got.get("text", "").lower() for word in want.lower().split()[:9])
    print(f"ocr_selftest: {'PASS' if hit >= 8 else 'FAIL'} ({hit}/9 words)")
    print(f"expected: {want}")
    print(f"got     : {got.get('text')!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ocr", nargs=4, type=int, metavar=("X", "Y", "W", "H"))
    ap.add_argument("--ask")
    a = ap.parse_args()
    if a.ocr:
        print(ocr(*a.ocr))
        return
    if a.ask:
        print(translate(a.ask))
        return
    if a.selftest:
        selftest()
        return
    if a.check:
        base, key = creds()
        print(f"config   : {CONFIG}")
        print(f"base_url : {base}")
        print(f"api_key  : <{len(key)} chars>")
        print(f"hotkey   : {'+'.join(HOTKEY)} -> {'OK' if hotkey_free() else 'FAILED (busy?)'}")
        print("api      : " + translate("Hello world, this is a smoke test.").splitlines()[0])
        return
    dpi_aware()
    if already_running():
        say("English Lens 已经在运行了。\n\n直接按 Ctrl+Alt+S 圈选英文即可，不用重复启动。", 5)
        return
    app = Lens()
    sw = app.root.winfo_screenwidth()
    toast = app.show(f"English Lens 已就绪：按 {'+'.join(HOTKEY)} 圈选英文。\n（这条 4 秒后自动消失，工具在后台待命）",
                     max(40, sw // 2 - 260), 80)
    app.root.after(4000, lambda: app.panel is toast and app.close_panel())
    app.root.mainloop()


if __name__ == "__main__":
    main()
