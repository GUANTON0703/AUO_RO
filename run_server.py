"""
ROtxt 啟動包裝腳本
讓 launcher.py 可以用 python run_server.py 等效執行 python -m server
"""
import os
import sys
import runpy

# 確保工作目錄是 ROtxt-main 資料夾
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 確保 ROtxt-main 在模組搜尋路徑內
base = os.path.dirname(os.path.abspath(__file__))
if base not in sys.path:
    sys.path.insert(0, base)

# 等效於 python -m server
runpy.run_module("server", run_name="__main__", alter_sys=True)
