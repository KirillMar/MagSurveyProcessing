import tkinter as tk
from tkinter import ttk
import threading
import time

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class LoadingOverlay:
    def __init__(self, parent, text="Загрузка...", alpha=0.4, gif_path=None):
        self.parent = parent
        self.text = text
        self.alpha = alpha
        self.overlay = None
        self._lock = threading.Lock()

        # Гифка
        self.gif_frames = []
        self.gif_label = None
        self._gif_running = False
        self._gif_index = 0
        self._gif_after_id = None

        if gif_path and PIL_AVAILABLE:
            self._load_gif(gif_path)

    def _load_gif(self, path):
        """Загружает кадры из GIF-файла."""
        try:
            img = Image.open(path)
            self.gif_frames = []
            while True:
                frame = ImageTk.PhotoImage(img.copy())
                self.gif_frames.append(frame)
                try:
                    img.seek(img.tell() + 1)
                except EOFError:
                    break
        except Exception as e:
            print(f"Ошибка загрузки GIF: {e}")

    # ----------------------------------------------------------------
    # Публичные методы
    # ----------------------------------------------------------------
    def show(self, text=None):
        """Показать затемнение с гифкой и текстом."""
        with self._lock:
            if self.overlay is not None:
                if text is not None:
                    self.label.config(text=text)
                return

            if text is not None:
                self.text = text

            self.overlay = tk.Toplevel(self.parent)
            self.overlay.attributes('-alpha', self.alpha)
            self.overlay.attributes('-topmost', True)
            self.overlay.overrideredirect(True)
            self.overlay.configure(bg='black')
            self._place_overlay()
            self.parent.bind("<Configure>", self._on_parent_configure)

            center_frame = tk.Frame(self.overlay, bg='black')
            center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

            # Гифка (если есть кадры)
            if self.gif_frames:
                self.gif_label = tk.Label(center_frame, bg='black')
                self.gif_label.pack(pady=(0, 10))
                self._start_gif_animation()

            # Текст (теперь полностью непрозрачный, т.к. на чёрном фоне)
            self.label = tk.Label(center_frame, text=self.text, fg='white', bg='black',
                                  font=('TkDefaultFont', 14, 'bold'))
            self.label.pack()

    def hide(self):
        """Скрыть оверлей и остановить анимации."""
        with self._lock:
            if self.overlay is None:
                return
            self._stop_gif_animation()
            self.parent.unbind("<Configure>")
            self.overlay.destroy()
            self.overlay = None
            self.gif_label = None

    def update_progress(self, percent: float):
        # Метод оставлен для обратной совместимости, но ничего не делает.
        pass

    # ----------------------------------------------------------------
    # Внутренние методы
    # ----------------------------------------------------------------
    def _place_overlay(self):
        if self.overlay is None:
            return
        x = self.parent.winfo_rootx()
        y = self.parent.winfo_rooty()
        w = self.parent.winfo_width()
        h = self.parent.winfo_height()
        self.overlay.geometry(f"{w}x{h}+{x}+{y}")

    def _on_parent_configure(self, event):
        self._place_overlay()

    def _start_gif_animation(self):
        if self._gif_running or not self.gif_frames:
            return
        self._gif_running = True
        self._gif_index = 0
        self._animate_gif()

    def _animate_gif(self):
        if not self._gif_running or self.overlay is None:
            return
        frame = self.gif_frames[self._gif_index]
        self.gif_label.config(image=frame)
        self._gif_index = (self._gif_index + 1) % len(self.gif_frames)
        self._gif_after_id = self.overlay.after(100, self._animate_gif)

    def _stop_gif_animation(self):
        self._gif_running = False
        if self._gif_after_id:
            self.overlay.after_cancel(self._gif_after_id)
            self._gif_after_id = None