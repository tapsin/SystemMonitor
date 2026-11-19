# System Monitor Widget for Windows 11

A lightweight desktop system monitor that lives on your Windows 11 desktop — behind all windows, survives "Show Desktop" (Win+D), and gives you real-time CPU, Memory, Network stats plus top process kill buttons.

## Features

- **Desktop-level widget**: Parents to `WorkerW` (desktop icons container) via Win32 `SetParent()` — stays behind all apps, survives Win+D
- **Real-time monitoring**: CPU %, Memory %, Network Upload/Download speed (KB/s)
- **Top 5 processes**: By CPU and Memory with KILL buttons
- **Draggable when unlocked**: Click 🔓 (red) → drag title bar → click 🔒 (green) to lock
- **Auto-start**: Registry `Run` key entry for Windows startup
- **Single file**: ~14MB standalone `.exe` (or run `SystemMonitor.py` directly)

## Screenshot

*(Add screenshot here)*

## Requirements

- Windows 11 (tested on 1920×1080)
- Python 3.10+ (for `.py` version)
- `psutil` (`pip install psutil`)

## Usage

### Run directly (Python)
```bash
python SystemMonitor.py
```

### Run standalone EXE
```bash
SystemMonitor.exe
```

### Auto-start
Already configured via `start_monitor.bat` → Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`

## Building EXE

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name SystemMonitor SystemMonitor.py
```

## Controls

| Button | Action |
|--------|--------|
| 🔒 / 🔓 | Lock / Unlock position (drag only when unlocked 🔓) |
| KILL | Terminates selected process (top 5 CPU / MEM) |
| Title bar | Drag to move (only when unlocked) |

## Architecture

- **Tkinter** GUI with `ctypes` Win32 API calls
- **WorkerW parenting**: `FindWindow("ProgMan")` → `SendMessage(0x052C)` → Find `WorkerW` with `SHELLDLL_DefView` child → `SetParent(hwnd, workerw)`
- **Styles**: `WS_CHILD | WS_VISIBLE | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW`
- **Drag**: `GetCursorPos()` → `ScreenToClient(parent)` → `SetWindowPos()` in parent client coordinates
- **Monitoring**: Background thread polls `psutil` every ~3 seconds

## License

MIT License

## Donate / Support

If you find this useful, consider supporting development:

- **Bitcoin (BTC)**: `bc1qxxxx...xxxx`
- **Ethereum (ETH)**: `0xXXXX...XXXX`
- **USDT (TRC20)**: `TXXXX...XXXX`
- **PayPal**: [paypal.me/yourname](https://paypal.me/yourname)
- **GitHub Sponsors**: [github.com/sponsors/tapsin](https://github.com/sponsors/tapsin)

---

*Built for Windows 11 desktop monitoring. Minimal, fast, no bloat.*