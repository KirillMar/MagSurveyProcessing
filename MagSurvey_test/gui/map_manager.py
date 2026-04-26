import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from gui.polygon_tool import PolygonTool

class MapManager:
    @staticmethod
    def draw_survey_track(ax, survey_data):
        if not survey_data:
            ax.text(0.5, 0.5, 'Нет данных съёмки', ha='center', va='center', transform=ax.transAxes)
            return
        all_lon, all_lat = [], []
        for df in survey_data.values():
            if 'lon' in df.columns and 'lat' in df.columns:
                lon = pd.to_numeric(df['lon'], errors='coerce').dropna()
                lat = pd.to_numeric(df['lat'], errors='coerce').dropna()
                if len(lon) > 0:
                    all_lon.extend(lon)
                    all_lat.extend(lat)
        if all_lon:
            ax.plot(all_lon, all_lat, 'b.', markersize=1, linestyle='None')
            ax.set_xlabel('Долгота', fontsize=8)
            ax.set_ylabel('Широта', fontsize=8)
            ax.set_title(f'Трек съёмки (точек: {len(all_lon)})', fontsize=9)
            ax.tick_params(axis='both', labelsize=7)
            ax.ticklabel_format(useOffset=False, style='plain')   # ← отключаем смещение
            ax.grid(True)
        else:
            ax.text(0.5, 0.5, 'В данных нет координат', ha='center', va='center', transform=ax.transAxes)

    @staticmethod
    def draw_nav_track(ax, nav_coords_cache):
        if not nav_coords_cache:
            ax.text(0.5, 0.5, 'Нет данных навигации', ha='center', va='center', transform=ax.transAxes)
            return
        all_lon, all_lat = [], []
        for points in nav_coords_cache.values():
            for x, y in points:
                all_lon.append(x)
                all_lat.append(y)
        if all_lon:
            ax.plot(all_lon, all_lat, 'r.', markersize=1, linestyle='None')
            ax.set_xlabel('Долгота', fontsize=8)
            ax.set_ylabel('Широта', fontsize=8)
            ax.set_title(f'Навигация (точек: {len(all_lon)})', fontsize=9)
            ax.tick_params(axis='both', labelsize=7)
            ax.ticklabel_format(useOffset=False, style='plain')   # ← отключаем смещение
            ax.grid(True)
        else:
            ax.text(0.5, 0.5, 'Не удалось извлечь координаты', ha='center', va='center', transform=ax.transAxes)

    @staticmethod
    def draw_assigned_track(ax, survey_data):
        """Рисует трек по присвоенным координатам X/Y."""
        if not survey_data:
            ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', transform=ax.transAxes)
            return
        all_x, all_y = [], []
        for df in survey_data.values():
            if 'X' in df.columns and 'Y' in df.columns:
                x_vals = pd.to_numeric(df['X'], errors='coerce').dropna()
                y_vals = pd.to_numeric(df['Y'], errors='coerce').dropna()
                all_x.extend(x_vals)
                all_y.extend(y_vals)
        if all_x:
            ax.plot(all_x, all_y, 'g.', markersize=1, linestyle='None')
            ax.set_xlabel('X', fontsize=8)
            ax.set_ylabel('Y', fontsize=8)
            ax.set_title(f'Присвоенные координаты (точек: {len(all_x)})', fontsize=9)
            ax.tick_params(axis='both', labelsize=7)
            ax.ticklabel_format(useOffset=False, style='plain')
            ax.grid(True)
            ax.figure.tight_layout()
        else:
            ax.text(0.5, 0.5, 'Нет координат', ha='center', va='center', transform=ax.transAxes)

    @staticmethod
    def create_interactive_survey_map(parent, survey_data, output_dir):
        MapManager._create_window(parent, "Карта съёмки", MapManager.draw_survey_track,
                                  survey_data, output_dir, enable_polygon=True)

    @staticmethod
    def create_interactive_nav_map(parent, nav_coords_cache):
        MapManager._create_window(parent, "Карта навигации", MapManager.draw_nav_track,
                                  nav_coords_cache, None, enable_polygon=False)

    @staticmethod
    def _create_window(parent, title, draw_func, data, output_dir, enable_polygon):
        win = tk.Toplevel(parent)
        win.title(title)
        win.geometry("900x700")

        fig = Figure(figsize=(9, 7), dpi=100)
        ax = fig.add_subplot(111)
        draw_func(ax, data)
        ax.ticklabel_format(useOffset=False, style='plain')

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()

        # Верхняя панель
        top_frame = ttk.Frame(win)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        if enable_polygon:
            hint_label = ttk.Label(top_frame, text="Замкните полигон и нажмите Enter для сохранения", foreground='gray')
            hint_label.pack(side=tk.TOP, anchor='e', padx=10, pady=(5,0))

        toolbar = NavigationToolbar2Tk(canvas, top_frame)
        toolbar.update()
        toolbar.pack(side=tk.LEFT)


        # В _create_window после toolbar.pack(side=tk.LEFT) добавьте разделитель и кнопку справа
        polygon_tool = None
        if enable_polygon:
            # Гибкий spacer, чтобы прижать кнопку вправо
            ttk.Frame(top_frame).pack(side=tk.LEFT, fill=tk.X, expand=True)

            polygon_tool = PolygonTool(ax, canvas, data, output_dir, main_window=parent if hasattr(parent, "_add_statistics") else None)
            btn_text = tk.StringVar(value="Выделить полигон")

            def toggle_polygon():
                if polygon_tool.active:
                    polygon_tool.deactivate()
                    btn_text.set("Выделить полигон")
                else:
                    polygon_tool.activate()
                    btn_text.set("Не выделять полигон")

            btn = ttk.Button(top_frame, textvariable=btn_text, command=toggle_polygon)
            btn.pack(side=tk.RIGHT, padx=10)

        # Холст
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Pan & Zoom
        pan = {'pressed': False, 'x': None, 'y': None}

        def on_press(event):
            if event.inaxes != ax:
                return
            if polygon_tool and polygon_tool.active:
                return
            pan['pressed'] = True
            pan['x'] = event.xdata
            pan['y'] = event.ydata

        def on_motion(event):
            if not pan['pressed'] or event.inaxes != ax:
                return
            if polygon_tool and polygon_tool.active:
                return
            dx = event.xdata - pan['x']
            dy = event.ydata - pan['y']
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            ax.set_xlim([xlim[0]-dx, xlim[1]-dx])
            ax.set_ylim([ylim[0]-dy, ylim[1]-dy])
            canvas.draw()

        def on_release(event):
            pan['pressed'] = False

        def on_scroll(event):
            if polygon_tool and polygon_tool.active:
                return
            scale = 1.1 if event.button == 'down' else 0.9
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            w, h = xlim[1]-xlim[0], ylim[1]-ylim[0]
            cx = event.xdata if event.xdata else (xlim[0]+xlim[1])/2
            cy = event.ydata if event.ydata else (ylim[0]+ylim[1])/2
            nw, nh = w*scale, h*scale
            ax.set_xlim([cx - nw*(cx-xlim[0])/w, cx + nw*(xlim[1]-cx)/w])
            ax.set_ylim([cy - nh*(cy-ylim[0])/h, cy + nh*(ylim[1]-cy)/h])
            canvas.draw()

        canvas.mpl_connect('button_press_event', on_press)
        canvas.mpl_connect('motion_notify_event', on_motion)
        canvas.mpl_connect('button_release_event', on_release)
        canvas.mpl_connect('scroll_event', on_scroll)