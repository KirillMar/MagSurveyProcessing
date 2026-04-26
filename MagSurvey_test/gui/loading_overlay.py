import tkinter as tk
from tkinter import ttk
import threading

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
        self._shown = False  # флаг, что оверлей должен быть виден

        # гифка...
        self.gif_frames = []
        self.gif_label = None
        self._gif_running = False
        self._gif_index = 0
        self._gif_after_id = None

        if gif_path and PIL_AVAILABLE:
            self._load_gif(gif_path)

    def _load_gif(self, path):
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

    def show(self, text=None):
        with self._lock:
            if self.overlay is not None:
                if text is not None:
                    self.label.config(text=text)
                return
            if text is not None:
                self.text = text

            self._shown = True
            self.overlay = tk.Toplevel(self.parent)
            self.overlay.attributes('-alpha', self.alpha)
            self.overlay.overrideredirect(True)
            self.overlay.configure(bg='black')
            self._place_overlay()

            # Подписываемся на изменение размеров родителя
            self.parent.bind("<Configure>", self._on_parent_configure, add='+')
            # Подписываемся на фокус родителя
            self.parent.bind("<FocusOut>", self._on_focus_out, add='+')
            self.parent.bind("<FocusIn>", self._on_focus_in, add='+')

            center_frame = tk.Frame(self.overlay, bg='black')
            center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

            if self.gif_frames:
                self.gif_label = tk.Label(center_frame, bg='black')
                self.gif_label.pack(pady=(0, 10))
                self._start_gif_animation()

            self.label = tk.Label(center_frame, text=self.text, fg='white', bg='black',
                                  font=('TkDefaultFont', 14, 'bold'))
            self.label.pack()

    def hide(self):
        with self._lock:
            if self.overlay is None:
                return
            self._shown = False
            self._stop_gif_animation()
            self.parent.unbind("<Configure>")
            self.parent.unbind("<FocusOut>")
            self.parent.unbind("<FocusIn>")
            self.overlay.destroy()
            self.overlay = None
            self.gif_label = None

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

    def _on_focus_out(self, event):
        """Прячем оверлей при потере фокуса."""
        if self.overlay is not None:
            self.overlay.withdraw()

    def _on_focus_in(self, event):
        """Показываем оверлей снова, если он должен быть виден."""
        if self._shown and self.overlay is not None:
            self.overlay.deiconify()
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