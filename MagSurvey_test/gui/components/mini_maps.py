import pandas as pd
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from gui.components.map_manager import MapManager

class MiniMaps:
    def __init__(self, main_window):
        self.mw = main_window  # ссылка на MainWindow

    def create_widgets(self, maps_container):
        # Настраиваем контейнер как grid с двумя равными колонками
        maps_container.grid_columnconfigure(0, weight=1, uniform='maps')
        maps_container.grid_columnconfigure(1, weight=1, uniform='maps')
        maps_container.grid_rowconfigure(0, weight=1)

        # Левая карта
        survey_map_frame = ttk.LabelFrame(maps_container, text="Трек съёмки (кликните для увеличения)", padding=5)
        survey_map_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 2))  # маленький отступ справа
        survey_map_frame.grid_propagate(False)

        self.mw.survey_map_figure = Figure(figsize=(5, 3), dpi=100)
        self.mw.survey_map_canvas = FigureCanvasTkAgg(self.mw.survey_map_figure, master=survey_map_frame)
        self.mw.survey_map_canvas.get_tk_widget().configure(bg='#2b2b2b', highlightthickness=0)
        self.mw.survey_map_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.mw.survey_map_canvas.mpl_connect('button_press_event', self.on_survey_map_click)
        survey_map_frame.bind("<Configure>", self._on_survey_map_resize)

        # Правая карта
        nav_map_frame = ttk.LabelFrame(maps_container, text="Присвоенные координаты (кликните для увеличения)", padding=5)
        nav_map_frame.grid(row=0, column=1, sticky='nsew', padx=(2, 0))  # маленький отступ слева
        nav_map_frame.grid_propagate(False)

        self.mw.nav_map_figure = Figure(figsize=(5, 3), dpi=100)
        self.mw.nav_map_canvas = FigureCanvasTkAgg(self.mw.nav_map_figure, master=nav_map_frame)
        self.mw.nav_map_canvas.get_tk_widget().configure(bg='#2b2b2b', highlightthickness=0)
        self.mw.nav_map_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.mw.nav_map_canvas.mpl_connect('button_press_event', self.on_nav_map_click)
        nav_map_frame.bind("<Configure>", self._on_nav_map_resize)

    def on_survey_map_click(self, event):
        if self.mw.survey_data_original:
            MapManager.create_interactive_survey_map(self.mw, self.mw.survey_data_original, self.mw.output_dir.get())

    def on_nav_map_click(self, event):
        if self.mw.coordinates_assigned and self.mw.survey_data:
            MapManager._create_window(
                self.mw,
                "Присвоенные координаты",
                MapManager.draw_assigned_track,
                self.mw.survey_data,
                self.mw.output_dir.get(),
                enable_polygon=False
            )
        elif self.mw.nav_coords_cache:
            MapManager.create_interactive_nav_map(self.mw, self.mw.nav_coords_cache)

    def _on_survey_map_resize(self, event):
        if not event.widget.winfo_exists():
            return
        w, h = event.width, event.height
        dpi = self.mw.survey_map_figure.get_dpi()
        self.mw.survey_map_figure.set_size_inches(max(w / dpi, 0.2), max(h / dpi, 0.2), forward=False)
        self.mw.survey_map_canvas.get_tk_widget().update_idletasks()
        self.mw.survey_map_canvas.draw_idle()

    def _on_nav_map_resize(self, event):
        if not event.widget.winfo_exists():
            return
        w, h = event.width, event.height
        dpi = self.mw.nav_map_figure.get_dpi()
        self.mw.nav_map_figure.set_size_inches(max(w / dpi, 0.2), max(h / dpi, 0.2), forward=False)
        self.mw.nav_map_canvas.get_tk_widget().update_idletasks()
        self.mw.nav_map_canvas.draw_idle()

    def update_nav_map(self):
        if not self.mw.nav_map_figure:
            return
        self.mw.nav_map_figure.clear()
        ax = self.mw.nav_map_figure.add_subplot(111)
        all_x, all_y = [], []
        data = self.mw.survey_data
        if data:
            for df in data.values():
                xcol = ycol = None
                for col in df.columns:
                    cl = col.lower()
                    if cl in ('x', 'lon'):
                        xcol = col
                    elif cl in ('y', 'lat'):
                        ycol = col
                if xcol and ycol:
                    x_vals = pd.to_numeric(df[xcol], errors='coerce').dropna()
                    y_vals = pd.to_numeric(df[ycol], errors='coerce').dropna()
                    all_x.extend(x_vals)
                    all_y.extend(y_vals)
        if all_x:
            ax.plot(all_x, all_y, 'g.', markersize=1, linestyle='None')
            ax.set_xlabel('X' if any('x' in c.lower() for df in data.values() for c in df.columns) else 'Долгота', fontsize=8)
            ax.set_ylabel('Y' if any('y' in c.lower() for df in data.values() for c in df.columns) else 'Широта', fontsize=8)
            ax.set_title(f'Координаты (точек: {len(all_x)})', fontsize=9)
            ax.ticklabel_format(useOffset=False, style='plain')
            ax.tick_params(axis='both', labelsize=7)
            ax.grid(True)
        else:
            ax.text(0.5, 0.5, 'В файле нет координат', ha='center', va='center',
                    transform=ax.transAxes, fontsize=12)
        ax.figure.tight_layout()
        self.mw.nav_map_canvas.draw_idle()