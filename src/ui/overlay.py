import os
import tkinter as tk
from datetime import datetime
import screeninfo

from src.core.utils import capture_screen_area, save_settings, load_settings


class CaptureOverlay:

    MIN_SIZE = 50  # これ未満のドラッグはクリックとみなす

    def __init__(self, parent, mode, save_dir=None, on_complete=None, on_cancel=None):
        self.parent      = parent
        self.mode        = mode
        self.save_dir    = save_dir
        self.on_complete = on_complete
        self.on_cancel   = on_cancel

        self.top = tk.Toplevel(parent)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.attributes("-alpha", 0.7)
        self.top.config(bg="black", cursor="cross")

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
        self.rect                = None
        self.start_x             = None
        self.start_y             = None
        self.drag_mode           = None
        self.rect_start_coords   = None
        self._dragged            = False
        self._rect_before_create = None

        # 前回の選択範囲を復元
        sx, sy, sw, sh = load_settings()
        cx1 = sx - self.min_x
        cy1 = sy - self.min_y
        self._draw_rect(cx1, cy1, cx1 + sw, cy1 + sh)

        self.top.focus_force()

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

    # ------------------------------------------------------------------ helpers

    def _draw_rect(self, x1, y1, x2, y2):
        cw = self.max_x - self.min_x
        ch = self.max_y - self.min_y

        self.canvas.delete("all")

        self.canvas.create_rectangle(0,  0,  cw, y1, fill="black", outline="")
        self.canvas.create_rectangle(0,  y2, cw, ch, fill="black", outline="")
        self.canvas.create_rectangle(0,  y1, x1, y2, fill="black", outline="")
        self.canvas.create_rectangle(x2, y1, cw, y2, fill="black", outline="")

        self.rect = self.canvas.create_rectangle(
            x1, y1, x2, y2, outline="cyan", width=2, dash=(4, 4)
        )

    def _get_normalized_coords(self):
        c = self.canvas.coords(self.rect)
        return (
            min(c[0], c[2]), min(c[1], c[3]),
            max(c[0], c[2]), max(c[1], c[3])
        )

    def _clamp_rect(self, x1, y1, x2, y2):
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

    def _restore_rect_before_create(self):
        """create前の矩形に戻す"""
        if self._rect_before_create:
            c = self._rect_before_create
            bx1 = min(c[0], c[2])
            by1 = min(c[1], c[3])
            bx2 = max(c[0], c[2])
            by2 = max(c[1], c[3])
            self._draw_rect(bx1, by1, bx2, by2)
        else:
            self._clear_rect()

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
                self.drag_mode           = "move"
                self.start_x, self.start_y = event.x, event.y
                self.rect_start_coords   = list(c)
                self._rect_before_create = None
                return

        self.drag_mode           = "create"
        self.start_x, self.start_y = event.x, event.y
        self._rect_before_create = self.canvas.coords(self.rect) if self.rect else None

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
        if self.drag_mode == "create":
            if self._dragged:
                x1, y1, x2, y2 = self._get_normalized_coords()
                if (x2 - x1) >= self.MIN_SIZE and (y2 - y1) >= self.MIN_SIZE:
                    self._save_current_rect()
                else:
                    self._restore_rect_before_create()
            else:
                self._restore_rect_before_create()
                self._execute_capture()

        elif self.drag_mode == "move":
            if not self._dragged:
                self._execute_capture()
            else:
                self._save_current_rect()

    def _clear_rect(self):
        self.canvas.delete("all")
        self.rect = None

    def _key_adjust(self, event, direction):
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
        if not self.rect:
            return
        step = (1 if (event.state & 0x0004) else 10) * (1 if event.delta > 0 else -1)
        x1, y1, x2, y2 = self._get_normalized_coords()
        if event.state & 0x0001:
            x2 += step
        else:
            y2 += step
        x2 = max(x1 + 1, x2)
        y2 = max(y1 + 1, y2)
        nx1, ny1, nx2, ny2 = self._clamp_resize(x1, y1, x2, y2)
        self._draw_rect(nx1, ny1, nx2, ny2)
        self._save_current_rect()

    # ------------------------------------------------------------------ actions

    def _execute_capture(self):
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

        # 撮影前に非表示
        self.top.withdraw()
        self.top.update()  # 確実に消えるまで待つ

        img = capture_screen_area(monitor)

        if self.mode == "normal":
            self._exit_overlay()
            if self.on_complete:
                self.on_complete(img)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(self.save_dir, f"capture_{timestamp}.png")
            img.save(path)

            # 再表示してエフェクト
            self.top.deiconify()
            self.top.focus_force()
            self.canvas.itemconfig(self.rect, outline="white", width=5, dash=())
            self.top.after(120, self._reset_rect_style)

    def _reset_rect_style(self):
        if self.rect:
            self.canvas.itemconfig(self.rect, outline="cyan", width=2, dash=(4, 4))

    def _exit_overlay(self):
        self.top.destroy()
        self.parent.deiconify()
        self.parent.lift()
        self.parent.focus_force()
        if self.on_cancel:
            self.on_cancel()