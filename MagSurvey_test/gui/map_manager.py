import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk
import pandas as pd


class MapManager:
    """Управление картами: мини-карты в основном окне и интерактивные окна."""
    
    @staticmethod
    def draw_survey_track(ax, survey_data):
        """Рисует трек съёмки на переданной оси ax. survey_data = {sheet_name: DataFrame}"""
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
            ax.grid(True)
            ax.figure.tight_layout()
        else:
            ax.text(0.5, 0.5, 'В данных нет координат', ha='center', va='center', transform=ax.transAxes)

    @staticmethod
    def draw_nav_track(ax, nav_coords_cache):
        """Рисует навигационные точки."""
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
            ax.grid(True)
        else:
            ax.text(0.5, 0.5, 'Не удалось извлечь координаты', ha='center', va='center', transform=ax.transAxes)
        ax.figure.tight_layout()

    @staticmethod
    def create_interactive_map_window(parent, title, draw_func, *args):
        """Создаёт Toplevel окно с интерактивной картой (зум/пан)."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.geometry("900x700")
        
        fig = Figure(figsize=(9, 7), dpi=100)
        ax = fig.add_subplot(111)
        draw_func(ax, *args)   # функция отрисовки принимает ax и дополнительные аргументы
        
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # ---------- Pan (перетаскивание) ----------
        pan_data = {'pressed': False, 'x': None, 'y': None}
        def on_press(event):
            if event.inaxes != ax:
                return
            pan_data['pressed'] = True
            pan_data['x'] = event.xdata
            pan_data['y'] = event.ydata
        
        def on_motion(event):
            if not pan_data['pressed'] or event.inaxes != ax:
                return
            if pan_data['x'] is None or pan_data['y'] is None:
                return
            dx = event.xdata - pan_data['x']
            dy = event.ydata - pan_data['y']
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            ax.set_xlim([xlim[0] - dx, xlim[1] - dx])
            ax.set_ylim([ylim[0] - dy, ylim[1] - dy])
            canvas.draw()
        
        def on_release(event):
            pan_data['pressed'] = False
        
        canvas.mpl_connect('button_press_event', on_press)
        canvas.mpl_connect('motion_notify_event', on_motion)
        canvas.mpl_connect('button_release_event', on_release)
        
        # ---------- Зум колёсиком ----------
        def on_scroll(event):
            scale_factor = 1.1
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            xdata = event.xdata
            ydata = event.ydata
            if xdata is None or ydata is None:
                return
            if event.button == 'up':
                new_width = (xlim[1] - xlim[0]) / scale_factor
                new_height = (ylim[1] - ylim[0]) / scale_factor
            else:
                new_width = (xlim[1] - xlim[0]) * scale_factor
                new_height = (ylim[1] - ylim[0]) * scale_factor
            ax.set_xlim([xdata - new_width/2, xdata + new_width/2])
            ax.set_ylim([ydata - new_height/2, ydata + new_height/2])
            canvas.draw()
        
        canvas.mpl_connect('scroll_event', on_scroll)
