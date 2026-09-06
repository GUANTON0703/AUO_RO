"""終端機相容性處理——Windows 舊主控台 (cp950) 會因 rich 的方塊字元 crash。"""
import sys


def prepare_windows_console() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    # 開啟 Win10 的 ANSI 逃脫序列處理（讓 rich 走現代渲染而非 legacy_windows）
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):  # STDOUT, STDERR
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VT_PROCESSING
        kernel32.SetConsoleOutputCP(65001)  # UTF-8
    except Exception:
        pass


def make_console():
    from rich.console import Console

    return Console(legacy_windows=False) if sys.platform == "win32" else Console()
