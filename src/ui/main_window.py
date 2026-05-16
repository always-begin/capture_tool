import sys
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk

# 作成した外部モジュールをインポート
from src.ui.overlay import CaptureOverlay  # オーバーレイ画面のパスに合わせて調整してください
from src.core.utils import copy_image_to_clipboard

class CapToolStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("CapTool")
        self.geometry("800x500")
        self.minsize(700, 450)
        self.protocol("WM_DELETE_WINDOW", self.quit)

        self.current_img = None
        self.zoom_level  = 1.0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 左: プレビューエリア ---
        self.preview_frame = ctk.CTkFrame(self, fg_color="#000000", corner_radius=10)
        self.preview_frame.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")

        self.canvas = tk.Canvas(self.preview_frame, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # ズーム・パン用の状態
        self._pan_start  = None   # ドラッグ開始座標 (x, y)
        self._offset     = [0, 0] # 画像の中心からのオフセット (px)

        self.canvas.bind("<MouseWheel>",      self._on_zoom)
        self.canvas.bind("<ButtonPress-1>",   self._on_pan_start)
        self.canvas.bind("<B1-Motion>",       self._on_pan_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_pan_end)
        self.canvas.bind("<Button-3>",        self._on_reset_view)
        self.canvas.bind("<Configure>",       lambda e: self._render_preview())

        # --- 右: コントロールパネル ---
        self.side_panel = ctk.CTkFrame(self, width=280, corner_radius=15)
        self.side_panel.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="ns")
        self.side_panel.pack_propagate(False)

        ctk.CTkLabel(
            self.side_panel, text="MODE",
            font=("Impact", 20), text_color="gray"
        ).pack(pady=(20, 10))

        self.mode_var = ctk.StringVar(value="通常モード")
        self.mode_selector = ctk.CTkSegmentedButton(
            self.side_panel,
            values=["通常モード", "連続保存"],
            variable=self.mode_var,
            font=("Yu Gothic UI", 12, "bold"),
            selected_color="#2fa572",
            selected_hover_color="#2fa572",
            unselected_hover_color="#3d3d3d",
            command=self._update_ui
        )
        self.mode_selector.pack(pady=10, padx=20, fill="x")

        ctk.CTkFrame(self.side_panel, height=2, fg_color="gray30").pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            self.side_panel, text="ACTION",
            font=("Impact", 20), text_color="gray"
        ).pack(pady=(10, 5))

        self.start_btn = ctk.CTkButton(
            self.side_panel, text="CAPTURE START",
            font=("Impact", 22),
            fg_color="#2fa572", hover_color="#107a4b",
            height=50, command=self._start_capture
        )
        self.start_btn.pack(pady=15, padx=20, fill="x")

        self.copy_btn = ctk.CTkButton(
            self.side_panel, text="コピー",
            font=("Yu Gothic UI", 14, "bold"),
            height=40, fg_color="gray30", hover_color="#3d3d3d",
            command=self._copy_to_clip
        )
        self.copy_btn.pack(pady=5, padx=20, fill="x")

        self.save_btn = ctk.CTkButton(
            self.side_panel, text="画像を保存",
            font=("Yu Gothic UI", 14, "bold"),
            height=40, fg_color="gray30", hover_color="#3d3d3d",
            command=self._save_image
        )
        self.save_btn.pack(pady=5, padx=20, fill="x")

        self._update_ui()
        self._render_preview()

    # ------------------------------------------------------------------ UI

    def _update_ui(self, *args):
        is_normal = self.mode_var.get() == "通常モード"
        has_img   = self.current_img is not None
        is_win    = sys.platform.startswith("win")

        if is_normal and has_img:
            copy_state = "normal" if is_win else "disabled"
            copy_fg    = "gray30" if is_win else "gray20"
            copy_tc    = "white"  if is_win else "gray40"
            self.copy_btn.configure(state=copy_state, fg_color=copy_fg, text_color=copy_tc)
            self.save_btn.configure(state="normal", fg_color="gray30", text_color="white")
        else:
            self.copy_btn.configure(state="disabled", fg_color="gray20", text_color="gray40")
            self.save_btn.configure(state="disabled", fg_color="gray20", text_color="gray40")

    # ------------------------------------------------------------------ capture

    def _start_capture(self):
        mode     = "normal" if self.mode_var.get() == "通常モード" else "continuous"
        save_dir = None

        if mode == "continuous":
            save_dir = filedialog.askdirectory(title="保存先フォルダを選択")
            if not save_dir:
                return

        self._disable_canvas_events()  # ← 追加
        self.withdraw()
        CaptureOverlay(
            self,
            mode,
            save_dir,
            on_complete=self._on_capture_complete,
            on_cancel=self._enable_canvas_events
        )

    def _on_capture_complete(self, img):
        self._enable_canvas_events()   # ← 復元
        self._set_preview_image(img)

    # ------------------------------------------------------------------ preview

    def _set_preview_image(self, img):
        self.current_img = img
        self.zoom_level  = 1.0
        self._offset     = [0, 0]
        self._render_preview()
        self._update_ui()

    def _render_preview(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10:
            cw, ch = 580, 400

        self.canvas.delete("all")

        if not self.current_img:
            self.canvas.create_text(
                cw // 2, ch // 2,
                text="No Image",
                fill="#444444",
                font=("Impact", 28)
            )
            return

        img      = self.current_img
        ratio    = min(cw / img.width, ch / img.height) * self.zoom_level
        new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))

        res_img     = img.resize(new_size, Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(res_img)

        cx = cw // 2 + self._offset[0]
        cy = ch // 2 + self._offset[1]
        self.canvas.create_image(cx, cy, image=self.tk_img, anchor="center")

    def _on_zoom(self, event):
        if not self.current_img:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        factor = 1.1 if event.delta > 0 else 0.9
        old_zoom = self.zoom_level
        self.zoom_level = max(0.1, min(self.zoom_level * factor, 10.0))
        scale = self.zoom_level / old_zoom

        mouse_dx = event.x - (cw // 2 + self._offset[0])
        mouse_dy = event.y - (ch // 2 + self._offset[1])
        self._offset[0] -= int(mouse_dx * (scale - 1))
        self._offset[1] -= int(mouse_dy * (scale - 1))

        self._render_preview()

    def _on_pan_start(self, event):
        if not self.current_img:
            return
        self._pan_start = (event.x, event.y)
        self._offset_at_start = list(self._offset)

    def _on_pan_move(self, event):
        if not self.current_img or self._pan_start is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._offset[0] = self._offset_at_start[0] + dx
        self._offset[1] = self._offset_at_start[1] + dy
        self._render_preview()

    def _on_pan_end(self, event):
        self._pan_start = None

    def _on_reset_view(self, event):
        if not self.current_img:
            return
        self.zoom_level = 1.0
        self._offset    = [0, 0]
        self._render_preview()

    # ------------------------------------------------------------------ actions

    def _copy_to_clip(self):
        # 外部ファイルに切り出した関数を呼び出すだけ！
        copy_image_to_clipboard(self.current_img)

    def _save_image(self):
        if not self.current_img:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All files", "*.*")]
        )
        if path:
            self.current_img.save(path)

    # ------------------------------------------------------------------ events

    def _disable_canvas_events(self):
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Button-3>")
        self.canvas.unbind("<MouseWheel>")

    def _enable_canvas_events(self):
        self.canvas.bind("<MouseWheel>",      self._on_zoom)
        self.canvas.bind("<ButtonPress-1>",   self._on_pan_start)
        self.canvas.bind("<B1-Motion>",       self._on_pan_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_pan_end)
        self.canvas.bind("<Button-3>",        self._on_reset_view)