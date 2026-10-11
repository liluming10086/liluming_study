# English Lens

**Box English text on screen with the mouse → a floating panel gives you a contextual Chinese
translation, 3–5 vocabulary items and one grammar note.** Made for *reading* English (papers,
docs, news, subtitles) and learning from it, not for translating a sentence once.

**用鼠标在屏幕上框选一段英文 → 弹出面板给出按语境的中文翻译、3–5 个生词/词组和一句语法说明。**
为“边读边学”设计，不是一次性句子翻译。

- **No installs.** Standard-library Python + tkinter + the OCR that already ships with Windows.
- **No OCR app and no copy-paste** — it reads the pixels you boxed, over any application:
  browser, PDF reader, Word, video, image.
- **Learning-shaped output**, not word-for-word: context translation + vocabulary with the meaning
  *in that sentence* + one grammar point.

## Requirements

| | |
|---|---|
| OS | Windows 10/11 **with the English OCR language pack** (usually already installed). Check in PowerShell: `[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]::AvailableRecognizerLanguages` |
| Python | 3.8+ with `tkinter` (included in the python.org installer). Nothing to `pip install`. |
| Shell | Windows PowerShell 5.1 (`powershell.exe`, ships with Windows — not pwsh 7) |
| API | any OpenAI-compatible `/chat/completions` endpoint + key. Tested against DeepSeek. |

## Install

Same four files, two ways.

### A. Standalone (no agent framework involved)

```bat
git clone https://github.com/<you>/english-lens
setx LENS_API_KEY  sk-...                                  :: your key
setx LENS_BASE_URL https://api.deepseek.com                :: optional; this is the default
pythonw english-lens\scripts\lens.py                       :: start it (no console window)
powershell -ExecutionPolicy Bypass -File english-lens\scripts\install_shortcut.ps1   :: optional desktop icon
```

`pythonw` matters: with `python.exe` you get a console window you cannot close independently.
To stop it, end the `pythonw.exe` process — or add `Ctrl+Alt+Q` yourself, it is four lines in `tick()`.

### B. As a skill (Hermes Agent, or anything using the SKILL.md format)

```bash
cp -r english-lens  <your skills dir>/
```

Then ask the agent for "screen-region translation" and it will find this skill; `SKILL.md` holds the
agent-facing instructions and the self-check commands.

## Configure

| Variable | Meaning | Default |
|---|---|---|
| `LENS_API_KEY` | bearer token for the endpoint | read from `config.yaml` (Hermes) |
| `LENS_BASE_URL` | OpenAI-compatible base URL | `https://api.deepseek.com` |
| `LENS_MODEL` | model name | `deepseek-v4-flash` |
| `LENS_CONFIG` | path to a Hermes `config.yaml` to read credentials from | `D:\Program Files\Hermes\config.yaml` |

The env vars win. With `LENS_API_KEY` set, `config.yaml` is never opened — that is the standalone path.

## Use

1. Start it. A 4-second "ready" toast appears; the tool then waits invisibly.
2. Press **`Ctrl+Alt+S`** (change the one `HOTKEY` line in `lens.py`).
3. The screen dims with a crosshair; **drag a box over the English text**.
4. The panel appears under the box: translation, vocabulary, grammar note.
5. Dismiss it by **clicking anywhere outside**, pressing `Esc`, or right-clicking the panel.

Starting it twice is harmless — a named mutex makes the second copy say "already running" and exit.

## How it works

```
hotkey ─▶ fullscreen 25%-opaque overlay ─▶ drag rectangle
       ─▶ PowerShell captures that rectangle at native DPI and upscales it 2x
       ─▶ Windows.Media.Ocr (en-US) ─▶ OpenAI-compatible chat call with one fixed learning prompt
       ─▶ tkinter panel next to the box
```

Everything else in the file — single-instance guard, hotkey thread, click-away dismissal — exists
only to make those five steps feel like one gesture.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Panel says the hotkey is taken | another program owns `Ctrl+Alt+S`. Change the `HOTKEY` line in `lens.py`. |
| Panel says 屏幕被锁定时无法截屏 / `The handle is invalid` | the workstation is locked; nothing is rendered to copy. Unlock and retry. |
| Second launch says "already running" | by design, single instance. Use the running one. |
| Panel says the model returned empty | the provider returned no content. On DeepSeek thinking models this happens when thinking is on; the request already sends `temperature: 0` + `thinking: disabled` and retries without the field for other providers. |
| OCR misreads letters (`The` → `rhe`) | OCR noise. Box tighter around the text; there is no pixel-free path in this version. |
| Nothing happens at all | run `python scripts/lens.py --check` and `--selftest`; they print which half is broken. |

## Known limits (deliberate)

- OCR, not UI Automation — pixels can be misread, and secure desktops (password boxes, the lock
  screen) are not capturable by design.
- No history, no cache, no tray icon, no settings UI, no autostart.
- Multi-monitor works for a single box; a box spanning two monitors is untested.
- Windows only (Windows.Media.Ocr + GDI capture).

## Layout

```
english-lens/
├── SKILL.md                      agent-facing instructions, pitfalls, self-checks
├── README.md                     this file
└── scripts/
    ├── lens.py                   hotkey, overlay, panel, HTTP call — the whole tool
    ├── ocr_rect.ps1              capture a rectangle + Windows OCR
    └── install_shortcut.ps1      one desktop icon
```

---

# 中文说明

**在屏幕上用鼠标框选一段英文 → 浮出面板给出「按语境的中文翻译 + 3~5 个生词/词组 + 一句语法说明」**，
为边读英文边学设计（论文、文档、新闻、字幕都行），不是一次性句子翻译。

- **零安装**：Python 标准库 + tkinter + Windows 自带的 OCR。不用 pip，不用装 OCR 软件。
- **不用复制粘贴**：它读你框住的那块像素，任何软件上都可用（浏览器、PDF、Word、视频、图片）。
- **输出是按学习的格式**：语境翻译、生词表（含在该句中的意思）、一个语法点。

## 环境要求

| | |
|---|---|
| 系统 | Windows 10/11，且装了**英文 OCR 语言包**（一般自带）。检查：PowerShell 里跑 `[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]::AvailableRecognizerLanguages` |
| Python | 3.8+ 且带 `tkinter`（官方安装包自带）。**不需要任何 pip 安装**。 |
| 命令行 | Windows PowerShell 5.1（系统自带；不是 pwsh 7） |
| 接口 | 任何 OpenAI 兼容的 `/chat/completions` 接口 + key（本工具在 DeepSeek 上验证） |

## 安装

**A. 独立使用（不依赖任何 agent 框架）**

```bat
git clone https://github.com/<you>/english-lens
setx LENS_API_KEY  sk-...                                  :: 你的 key
setx LENS_BASE_URL https://api.deepseek.com                :: 可选，这是默认值
pythonw english-lens\scripts\lens.py                       :: 启动（无黑窗口）
powershell -ExecutionPolicy Bypass -File english-lens\scripts\install_shortcut.ps1   :: 可选，桌面图标
```

必须用 `pythonw`：用 `python.exe` 会多一个你自己关不掉的命令行窗口。关闭就是结束 `pythonw.exe` 进程
（想加个 `Ctrl+Alt+Q` 退出键的话，`tick()` 里四行就够）。

**B. 作为 skill 使用（Hermes Agent，或任何用 SKILL.md 格式的工具）**

把整个文件夹放进 skills 目录即可，之后对 agent 说"屏幕划词翻译"就会命中，`SKILL.md` 里是给 agent 看的
说明和自检命令。

## 配置

| 变量 | 作用 | 默认 |
|---|---|---|
| `LENS_API_KEY` | 接口的 bearer token | 从 `config.yaml`（Hermes）读取 |
| `LENS_BASE_URL` | OpenAI 兼容的 base URL | `https://api.deepseek.com` |
| `LENS_MODEL` | 模型名 | `deepseek-v4-flash` |
| `LENS_CONFIG` | 要从哪个 Hermes `config.yaml` 读凭据 | `D:\Program Files\Hermes\config.yaml` |

环境变量优先。只要设了 `LENS_API_KEY`，`config.yaml` 根本不会被打开——这就是独立用法。

## 使用

1. 启动，屏幕中间会闪一条 4 秒的"已就绪"提示，之后工具在后台静默待命。
2. 按 **`Ctrl+Alt+S`**（改快捷键就改 `lens.py` 里那一行 `HOTKEY`）。
3. 屏幕变暗、光标变十字，**左键拖一个框住英文的方框**。
4. 面板出现在方框下方：翻译 + 生词 + 语法。
5. 关闭：**点面板外面任意位置**，或按 `Esc`，或右键点面板。重复启动不会出问题（单一实例）。

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 面板说快捷键被占用 | 别的程序占着 `Ctrl+Alt+S`，改 `lens.py` 里那一行 `HOTKEY` |
| 面板说"屏幕被锁定时无法截屏" | 锁屏状态下 Windows 不渲染桌面，截不到图；解锁重试 |
| 第二次启动说"已经在运行" | 正常，单一实例；直接用已在跑的那个 |
| 面板说模型返回了空内容 | 接口没给正文。DeepSeek 思考模型开了思考就会这样（本工具已强制 `temperature 0` + `thinking: disabled`，并对其他厂商自动重试不带该字段） |
| OCR 认错字母（`The` → `rhe`） | OCR 固有噪声；框紧一点。本版本没有"绕过像素直接取文本"的路径 |
| 完全没反应 | 跑 `python scripts/lens.py --check` 和 `--selftest`，它会告诉你哪一半坏了 |

## 已知边界（有意为之）

- 走 OCR，不走 UI Automation：会认错个别字形；安全桌面（密码框、锁屏）按 Windows 设计截不到。
- 没有历史记录、缓存、托盘图标、设置界面、开机自启。
- 多显示器单框可用；跨屏框选未测试。
- 仅 Windows（依赖 Windows.Media.Ocr 和 GDI 截屏）。
