import os
import sys
import json
from io import BytesIO
from datetime import datetime
import mss
from PIL import Image

# Windows環境のみインポートを有効にする
if sys.platform.startswith("win"):
    import win32clipboard
else:
    win32clipboard = None

# ------------------------------------------------------------------ Settings
def get_settings_path():
    if sys.platform.startswith("win"): 
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform.startswith("darwin"):
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    app_dir = os.path.join(base, "CapTool")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "settings.json")

SETTINGS_FILE = get_settings_path()

def load_settings():
    """設定ファイルを読み込み、前回の座標とサイズを返す"""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d.get("x", 100), d.get("y", 100), d.get("w", 400), d.get("h", 300)
    except Exception:
        return 100, 100, 400, 300

def save_settings(x, y, w, h):
    """現在の座標とサイズを設定ファイルに保存する"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"x": int(x), "y": int(y), "w": int(w), "h": int(h)}, f)
    except Exception as e:
        print(f"Save settings error: {e}")

# ------------------------------------------------------------------ Actions
def copy_image_to_clipboard(pil_img):
    """PIL画像をWindowsのクリップボードにコピーする"""
    if not win32clipboard or pil_img is None:
        return
    output = BytesIO()
    pil_img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()

def capture_screen_area(monitor_dict):
    """指定された座標の画面をキャプチャしてPIL Imageで返す"""
    with mss.mss() as sct:
        sct_img = sct.grab(monitor_dict)
        return Image.frombytes("RGB", sct_img.size, sct_img.rgb)