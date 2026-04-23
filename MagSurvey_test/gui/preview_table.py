import tkinter as tk
from tkinter import ttk

class PreviewTable(ttk.Frame):
    def __init__(self, master, columns, **kwargs):
        super().__init__(master, **kwargs)
        self.tree = ttk.Treeview(self, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor='center')
        
        v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    
    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def insert_row(self, values):
        self.tree.insert('', tk.END, values=values)