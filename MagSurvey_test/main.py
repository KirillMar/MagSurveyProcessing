import tkinter as tk
import sv_ttk
from gui.main_window import MainWindow
import sys
import os

if __name__ == "__main__":
    root = tk.Tk()
    
    if getattr(sys, 'frozen', False):
        # Запущено как .exe
        base_path = sys._MEIPASS
    else:
        # Запущено как скрипт
        base_path = os.path.dirname(__file__)

    icon_path = os.path.join(base_path, 'src/fish.ico')
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)

    app = MainWindow(root)
    root.mainloop()
