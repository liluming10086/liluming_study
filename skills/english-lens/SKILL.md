---
name: english-lens
description: Use when translating on-screen English text to Chinese.
version: 1.0.0
author: liukeming
license: MIT
metadata:
  hermes:
    tags: [translation, ocr, english-learning, windows, productivity]
    related_skills: []
---

# English Lens

Select any English text on screen with the mouse -> a floating panel shows 中文翻译 +
生词 + 语法, for language learning. Works over any app (browser, PDF, video, image).

**Zero installs**: Python standard library + tkinter + the OCR already on the machine
(PowerShell 5.1 + WinRT `Windows.Media.Ocr`). No pip packages, no key file of its own —
it reuses the key already in `config.yaml`.

## When to use

- The user asks for 划词翻译 / screen-region translation / a learning popup, or wants this
  published as a repo.
- The user reports: no panel appears, OCR is garbage, the hotkey does nothing.

## Run it

The tool is one process that waits for a global hotkey. Default hotkey: **Ctrl+Alt+S**
(left hand only).

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_shortcut.ps1   # once: Desktop icon
pythonw "<skill dir>/scripts/lens.py"                                             # or start it here
```

Start-up runs a silent capture/OCR smoke test: if the pixels cannot be read (locked desktop,
no OCR engine) the panel says so immediately instead of failing later on the first drag.

Then drag a box with the **left mouse button** over English text -> panel appears near the
box. Click anywhere else (the panel holds focus when it appears, so any other foreground window
counts) or press `Esc` / right-click it to close it; the next drag replaces it.

Launching it twice is harmless: a named mutex makes the second copy exit with "已经在运行".
The process is invisible while it waits, so a 4-second start-up toast ("已就绪") is what tells the
user it is alive - keep it, or they will double-click the icon again and read "hotkey busy" as an
error from another program.

Do NOT add it to autostart unless the user asks — that is a system-config change, ask first.

## Self-checks (run these, do not guess)

```bash
python scripts/lens.py --selftest           # prints a known sentence, OCRs it back, PASS/FAIL
python scripts/lens.py --check              # config + credential + real API round trip
python scripts/lens.py --ocr X Y W H        # raw OCR of any screen rect
python scripts/lens.py --ask "some English" # the learning prompt only, no screen
```

## Change the hotkey / model

One line each at the top of `scripts/lens.py`: `HOTKEY = ("ctrl", "alt", "S")`, `MODEL`.

## Configuration

| What | Where |
|---|---|
| API base / key | `LENS_BASE_URL` / `LENS_API_KEY` env vars, else the `custom_providers` entry named by `model.provider` in `config.yaml` |
| config path | `LENS_CONFIG` env var, default `D:\Program Files\Hermes\config.yaml` |
| model | `LENS_MODEL` env var, default `deepseek-v4-flash` (fast; thinking is switched off in the request) |

The env vars also make the tool usable outside Hermes (publishable as a plain repo).

## Pitfalls already paid for

- **DPI awareness is mandatory.** Both `lens.py` and `ocr_rect.ps1` call
  `SetProcessDpiAwarenessContext(-4)` before touching pixels. Without it a 150%-scaled
  2560x1600 screen is captured as a downscaled image and OCR quality roughly halves
  (measured on this machine: 1372 -> 2692 chars on the same screen).
- **Do not shell out to `hermes -z`** for the translation: a full agent turn takes ~10 s and
  injects the plugin prompt. Use the plain OpenAI-compatible HTTP call (~1-2 s).
- The endpoint is tried as `<base>/v1/chat/completions` then `<base>/chat/completions`, so it
  works whether `base_url` includes `/v1` or not.
- **The model is a *thinking* model - measured, not guessed.** `deepseek-v4-flash` returns
  `content: ""` with `finish_reason=length` whenever it is allowed to think: the whole token
  budget goes into `reasoning_content`. `temperature=0` alone: 3.8-4.5 s and still empty.
  `thinking: {"type": "disabled"}` alone (temperature 0.3): 4.3 s and still empty.
  **Both together: 1.2-1.4 s, `reasoning_tokens=0`, full answer.** Do not "fix" an empty panel by
  raising `max_tokens` - that measured 10.7 s and is the wrong direction for a hover-style tool.
  `lens.py` keeps an empty-content fallback line in case the provider changes its mind.
- PowerShell must run with `CREATE_NO_WINDOW` (`creationflags=0x08000000`) or every lookup
  flashes a black console window.
- **Dismissing the panel**: focus-based dismissal (`<FocusOut>`, or "foreground window is no longer
  mine") is unusable here - Windows does not reliably let a hotkey-triggered process take the
  foreground, and the panel *did* get killed 0.4s after appearing when that rule was tried. What
  works is polling `GetAsyncKeyState(0x01) & 0x0001` (the latched "was pressed since last poll" bit,
  so quick clicks are not missed) in the existing 40ms `tick`, and comparing `GetCursorPos` with the
  panel rectangle. `show()` must read the key state once to clear the stale latch.
- PS 5.1 stdout is not UTF-8 by default -> `[Console]::OutputEncoding` is set in the script,
  and Python reads it as utf-8.
- Hotkey registration failure is silent under `pythonw`; the script shows an on-screen warning
  instead. A hotkey already taken by another app is the usual cause.
- **A locked desktop breaks capture**: `CopyFromScreen` throws `The handle is invalid` while the
  workstation is locked (nothing is rendered). Not a code bug - `lens.py` detects that message and
  tells the user to unlock. Do not "fix" it by retrying or swapping the capture API.
- **The hotkey must live in its own thread.** `RegisterHotKey(None, ...)` posts `WM_HOTKEY` to the
  calling thread's queue with `hwnd=NULL`, and Tk's own message pump drains that queue and drops
  the message before any `after()`-based `PeekMessage` poll can see it. Measured: a plain Python
  process receives the message, the Tk app never did. Hence `hotkey_loop` runs
  `RegisterHotKey` + `GetMessageW` in a daemon thread and hands events over a `queue.Queue`.

## Troubleshooting order

1. `--selftest` -> proves capture + DPI + OCR.
2. `--check` -> proves config + key + API.
3. Only then suspect the GUI (hotkey busy, panel focus).

Ask the user for the exact command plus the full error text; do not guess.

## Known limits (deliberate, do not "fix" without asking)

- OCR is OCR: similar glyphs get confused (`Get-CimInstance` -> `Get-Cimlnstance`). The crop
  is upscaled 2x before recognition to reduce it, not to eliminate it. If the user complains
  about noise, the real fix is reading text via UI Automation instead of pixels (v2).
- No history, no cache, no tray icon, no settings UI, no autostart.
- Multi-monitor works through the Tk virtual root; a box spanning two monitors is untested.
