import tkinter as tk
from tkinter import ttk, messagebox

class StatisticsManager:
    def __init__(self, main_window):
        self.mw = main_window

    def add(self, message):
        self.mw.statistics_history.append(message)

    def show_all(self):
        if not self.mw.statistics_history:
            messagebox.showinfo("Статистика", "Статистика пока не собрана.")
            return
        win = tk.Toplevel(self.mw.master)
        win.title("Вся статистика")
        win.geometry("700x400")
        text = tk.Text(win, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(text, command=text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text['yscrollcommand'] = scroll.set
        for i, msg in enumerate(self.mw.statistics_history, 1):
            text.insert(tk.END, f"{i}. {msg}\n\n")
        text.config(state=tk.DISABLED)

    def show_errors(self):
        if not self.mw.errors:
            messagebox.showinfo("Ошибки", "Ошибок нет")
            return
        win = tk.Toplevel(self.mw.master)
        win.title("Список ошибок")
        win.geometry("700x400")
        text = tk.Text(win, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(text, command=text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text['yscrollcommand'] = scroll.set
        for err in self.mw.errors:
            text.insert(tk.END, err + "\n")
        text.config(state=tk.DISABLED)