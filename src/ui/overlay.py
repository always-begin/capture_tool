import os
import tkinter as tk
from datetime import datetime
import screeninfo

# 自作モジュールからインポート
from src.core.utils import capture_screen_area, save_settings, load_settings

class CaptureOverlay:
    def __init__(self, parent, mode, save_dir=None, on_complete=None, on_cancel=None):
        self.parent      = parent
        self.mode        = mode
        self.save_dir    = save_dir
        self.on_complete = on_complete
        self.on_cancel   = on_cancel

        # Toplevel で親の mainloop を共有し、キーイベントが正常に届くようにする
        self.top = tk.Toplevel(parent)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.attributes("-alpha", 0.7)
        self.top.config(bg="black", cursor="cross")

        # マルチモニター対応：全モニターを包含する矩形
        monitors   = screeninfo.get_monitors()
        self.min_x = min(m.x for m in monitors)
        self.min_y = min(m.y for m in monitors)
        self.max_x = max(m.x + m.width  for m in monitors)
        self.max_y = max(m.y + m.height for m in monitors)
        total_w    = self.max_x - self.min_x
        total_h    = self.max_y - self.min_y
        self.top.geometry(f"{total_w}x{total_h}+{self.min_x}+{self.min_y}")

        self.canvas = tk.Canvas(self.top, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 状態
        self.rect              = None  # 枠線
        self.start_x           = None
        self.start_y           = None
        self.drag_mode         = None
        self.rect_start_coords = None
        self._dragged          = False

        # 前回の選択範囲を復元（画面絶対座標 → キャンバス相対座標）
        sx, sy, sw, sh = load_settings()
        cx1 = sx - self.min_x
        cy1 = sy - self.min_y
        self._draw_rect(cx1, cy1, cx1 + sw, cy1 + sh)

        self.top.focus_force()

        # イベントバインド
        self.canvas.bind("<ButtonPress-1>",   self._on_click)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>",        lambda e: self._clear_rect())
        self.canvas.bind("<Button-2>",        lambda e: self._exit_overlay())
        self.top.bind("<Escape>",             lambda e: self._exit_overlay())
        self.top.bind("<space>",              lambda e: self._execute_capture())
        self.top.bind("<Up>",    lambda e: self._key_adjust(e, "Up"))
        self.top.bind("<Down>",  lambda e: self._key_adjust(e, "Down"))
        self.top.bind("<Left>",  lambda e: self._key_adjust(e, "Left"))
        self.top.bind("<Right>", lambda e: self._key_adjust(e, "Right"))
        self.top.bind("<MouseWheel>", self._on_wheel_adjust)

        # self.top.update_idletasks() # 画面の配置を確定させる
        # self.top.grab_set()         # ★重要：すべてのマウス・キー操作をこの画面に強制する
        # self.top.focus_force()      # キーボード入力を確実に受け付ける

    # ------------------------------------------------------------------ helpers

    def _draw_rect(self, x1, y1, x2, y2):
        cw = self.max_x - self.min_x
        ch = self.max_y - self.min_y

        self.canvas.delete("all")

        # 外側を4分割で暗く覆う
        self.canvas.create_rectangle(0,  0,  cw, y1, fill="black", outline="")  # 上
        self.canvas.create_rectangle(0,  y2, cw, ch, fill="black", outline="")  # 下
        self.canvas.create_rectangle(0,  y1, x1, y2, fill="black", outline="")  # 左
        self.canvas.create_rectangle(x2, y1, cw, y2, fill="black", outline="")  # 右

        # 枠線
        self.rect = self.canvas.create_rectangle(
            x1, y1, x2, y2, outline="cyan", width=2, dash=(4, 4)
        )

    def _get_normalized_coords(self):
        """x1<x2, y1<y2 を保証して返す"""
        c = self.canvas.coords(self.rect)
        return (
            min(c[0], c[2]), min(c[1], c[3]),
            max(c[0], c[2]), max(c[1], c[3])
        )

    def _clamp_rect(self, x1, y1, x2, y2):
        """矩形をキャンバス範囲内に収める。幅・高さは維持する（移動用）"""
        cw = self.max_x - self.min_x
        ch = self.max_y - self.min_y
        w  = x2 - x1
        h  = y2 - y1
        w  = min(w, cw)
        h  = min(h, ch)
        x1 = max(0, min(x1, cw - w))
        y1 = max(0, min(y1, ch - h))
        return x1, y1, x1 + w, y1 + h

    def _clamp_resize(self, x1, y1, x2, y2):
        """右下隅を動かすサイズ変更用。x1/y1 は固定し x2/y2 だけを丸める"""
        cw = self.max_x - self.min_x
        ch = self.max_y - self.min_y
        x2 = max(x1 + 1, min(x2, cw))
        y2 = max(y1 + 1, min(y2, ch))
        return x1, y1, x2, y2

    def _save_current_rect(self):
        if not self.rect:
            return
        x1, y1, x2, y2 = self._get_normalized_coords()
        save_settings(self.min_x + x1, self.min_y + y1, x2 - x1, y2 - y1)

    # ------------------------------------------------------------------ events

    def _on_click(self, event):
        self._dragged = False
        self.top.focus_force()

        if self.rect:
            c = self.canvas.coords(self.rect)
            inside = (
                min(c[0], c[2]) <= event.x <= max(c[0], c[2]) and
                min(c[1], c[3]) <= event.y <= max(c[1], c[3])
            )
            if inside:
                self.drag_mode = "move"
                self.start_x, self.start_y = event.x, event.y
                self.rect_start_coords = list(c)
                return

        self.drag_mode = "create"
        self.start_x, self.start_y = event.x, event.y

    def _on_drag(self, event):
        if not self.rect and self.drag_mode != "create":
            return
        self._dragged = True

        if self.drag_mode == "create":
            self._draw_rect(self.start_x, self.start_y, event.x, event.y)
        elif self.drag_mode == "move":
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            x1, y1, x2, y2 = self.rect_start_coords
            nx1, ny1, nx2, ny2 = self._clamp_rect(x1 + dx, y1 + dy, x2 + dx, y2 + dy)
            self._draw_rect(nx1, ny1, nx2, ny2)

    def _on_release(self, event):
        if not self._dragged:
            if self.drag_mode == "move":  # ← rect内クリックのときだけ
                self._execute_capture()
            return
        self._save_current_rect()

    def _clear_rect(self):
        self.canvas.delete("all")
        self.rect = None

    def _key_adjust(self, event, direction):
        """矢印キーで右下隅を移動（Ctrl: 1px / 通常: 10px）"""
        if not self.rect:
            return
        step = 1 if (event.state & 0x0004) else 10
        x1, y1, x2, y2 = self._get_normalized_coords()
        if   direction == "Up":    y2 -= step
        elif direction == "Down":  y2 += step
        elif direction == "Left":  x2 -= step
        elif direction == "Right": x2 += step
        x2 = max(x1 + 1, x2)
        y2 = max(y1 + 1, y2)
        nx1, ny1, nx2, ny2 = self._clamp_resize(x1, y1, x2, y2)
        self._draw_rect(nx1, ny1, nx2, ny2)
        self._save_current_rect()

    def _on_wheel_adjust(self, event):
        """スクロールで高さ調整（Shift: 幅調整 / Ctrl: 1px単位）"""
        if not self.rect:
            return
        step = (1 if (event.state & 0x0004) else 10) * (1 if event.delta > 0 else -1)
        x1, y1, x2, y2 = self._get_normalized_coords()
        if event.state & 0x0001:  # Shift → 幅
            x2 += step
        else:                     # 通常   → 高さ
            y2 += step
        x2 = max(x1 + 1, x2)
        y2 = max(y1 + 1, y2)
        nx1, ny1, nx2, ny2 = self._clamp_resize(x1, y1, x2, y2)
        self._draw_rect(nx1, ny1, nx2, ny2)
        self._save_current_rect()

    # ------------------------------------------------------------------ actions

    def _execute_capture(self):
        """キャプチャ処理の実行（座標を計算して core へ渡す）"""
        if not self.rect:
            return
        x1, y1, x2, y2 = self._get_normalized_coords()
        
        monitor = {
            "left":   int(self.min_x + x1),
            "top":    int(self.min_y + y1),
            "width":  int(x2 - x1),
            "height": int(y2 - y1),
        }
        if monitor["width"] <= 0 or monitor["height"] <= 0:
            return

        # utils.py に切り出したキャプチャ関数を呼び出す
        img = capture_screen_area(monitor)

        if self.mode == "normal":
            self._exit_overlay()
            if self.on_complete:
                self.on_complete(img)
        else:
            # 連続保存：ファイルに書き出してエフェクト
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(self.save_dir, f"capture_{timestamp}.png")
            img.save(path)

            # 枠線を白く光らせるエフェクト
            self.canvas.itemconfig(self.rect, outline="white", width=5, dash=())
            self.top.focus_force()
            self.top.after(120, self._reset_rect_style)

    def _reset_rect_style(self):
        """連続保存エフェクト後に枠線を元に戻す"""
        if self.rect:
            self.canvas.itemconfig(self.rect, outline="cyan", width=2, dash=(4, 4))

    def _exit_overlay(self):
        """オーバーレイを閉じてメインウィンドウを復元する"""
        self.top.destroy()
        self.parent.deiconify()
        self.parent.lift()
        self.parent.focus_force()
        if self.on_cancel:
            self.on_cancel()