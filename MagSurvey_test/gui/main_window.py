import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from matplotlib import style
import sv_ttk
import threading
import matplotlib as mpl
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.loading_overlay import LoadingOverlay
from gui.components.map_manager import MapManager
from gui.data_loaders import DataLoaders
from utils.helpers import open_folder
from gui.components.mini_maps import MiniMaps
from gui.path_selectors import PathSelectors
from logic.data_processor import DataProcessor
from utils.statistics import StatisticsManager

class MainWindow:
    def __init__(self, master):
        self.master = master
        master.title("Обработка данных магнитной съёмки")
        master.geometry("1000x700")

        self.survey_map_figure = None
        self.survey_map_canvas = None
        self.nav_map_figure = None
        self.nav_map_canvas = None
        self.nav_coords_cache = None
        self.var_df = None
        self.dark_theme = True
        self.survey_data_corrected = None

        self.survey_path = tk.StringVar()
        self.nav_path = tk.StringVar()
        self.correction_file = tk.StringVar()
        self.mode = tk.StringVar(value="with_v1")
        self.survey_data = None
        self.survey_data_original = None
        self.nav_data = None
        self.output_dir = tk.StringVar()
        self.coordinates_assigned = False

        gif_path = Path(__file__).parent.parent / "src" / "anima_fish.gif"
        self.loading_overlay = LoadingOverlay(self.master, alpha=0.5, gif_path=str(gif_path))
        self.loading_overlay_shown = False
        self.errors = []
        self.statistics_history = []

        # Менеджеры
        self.data_loaders = DataLoaders(self)
        self.path_selectors = PathSelectors(self)
        self.mini_maps = MiniMaps(self)
        self.data_processor = DataProcessor(self)
        self.statistics = StatisticsManager(self)

        self.create_widgets()
        self.master.bind("<Map>", self._on_window_map)
        self.toggle_theme()     # применит светлую тему и стили

    def create_widgets(self):
        # Выходная папка
        frame_output = ttk.Frame(self.master)
        frame_output.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(frame_output, text="Папка для сохранения:").pack(side=tk.LEFT)
        ttk.Entry(frame_output, textvariable=self.output_dir, width=60).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_output, text="Обзор...", command=self.path_selectors.browse_output).pack(side=tk.LEFT)
        ttk.Button(frame_output, text="📁", width=3,
                   command=lambda: open_folder(self.output_dir.get())).pack(side=tk.LEFT, padx=2)
        self.theme_btn = ttk.Button(frame_output, text="🌙", width=3,
                           command=self.toggle_theme)
        self.theme_btn.pack(side=tk.RIGHT, padx=2)

        # Источники данных
        frame_paths = ttk.LabelFrame(self.master, text="Источники данных", padding=10)
        frame_paths.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame_paths, text="Формат файла:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        fmt_subframe = ttk.Frame(frame_paths)
        fmt_subframe.grid(row=0, column=1, sticky='w')
        ttk.Radiobutton(fmt_subframe, text="CSV с V1", variable=self.mode, value="with_v1").pack(side=tk.LEFT)
        ttk.Radiobutton(fmt_subframe, text="CSV без V1", variable=self.mode, value="without_v1").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(fmt_subframe, text="Готовый Excel", variable=self.mode, value="excel").pack(side=tk.LEFT, padx=10)

        # Папка съёмки
        ttk.Label(frame_paths, text="Папка с данными съёмки:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame1 = ttk.Frame(frame_paths)
        entry_frame1.grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame1, textvariable=self.survey_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame1, text="Обзор...", command=self.path_selectors.browse_survey).pack(side=tk.LEFT)
        ttk.Button(entry_frame1, text="📁", width=3,
                   command=lambda: open_folder(self.survey_path.get())).pack(side=tk.LEFT, padx=2)

        # Папка навигации
        ttk.Label(frame_paths, text="Папка с данными навигации:").grid(row=2, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame2 = ttk.Frame(frame_paths)
        entry_frame2.grid(row=2, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame2, textvariable=self.nav_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame2, text="Обзор...", command=self.path_selectors.browse_navigation).pack(side=tk.LEFT)
        ttk.Button(entry_frame2, text="📁", width=3,
                   command=lambda: open_folder(self.nav_path.get())).pack(side=tk.LEFT, padx=2)

        # Файл вариаций
        ttk.Label(frame_paths, text="Файл вариаций (Excel):").grid(row=3, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame3 = ttk.Frame(frame_paths)
        entry_frame3.grid(row=3, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame3, textvariable=self.correction_file, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame3, text="Обзор...", command=self.path_selectors.browse_correction).pack(side=tk.LEFT)
        ttk.Button(entry_frame3, text="📁", width=3,
                   command=lambda: open_folder(str(Path(self.correction_file.get()).parent) if self.correction_file.get() else "")).pack(side=tk.LEFT, padx=2)
        self.var_graph_btn = ttk.Button(entry_frame3, text="📊 Вариации", command=self.show_var_graph, state=tk.DISABLED)
        self.var_graph_btn.pack(side=tk.LEFT, padx=5)
        frame_paths.columnconfigure(1, weight=1)

        # Мини-карты
        maps_container = ttk.Frame(self.master)
        maps_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.mini_maps.create_widgets(maps_container)

        # Нижние кнопки
        bottom_frame = ttk.Frame(self.master)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        actions_left = ttk.Frame(bottom_frame)
        actions_left.pack(side=tk.LEFT)
        self.assign_btn = ttk.Button(actions_left, text="Присвоить координаты",
                                     command=self.data_processor.process_with_coordinates, state=tk.DISABLED)
        self.assign_btn.pack(side=tk.LEFT, padx=5)
        self.correct_btn = ttk.Button(actions_left, text="Ввести поправку",
                                      command=self.data_processor.process_corrections, state=tk.DISABLED)
        self.correct_btn.pack(side=tk.LEFT, padx=5)

        actions_right = ttk.Frame(bottom_frame)
        actions_right.pack(side=tk.RIGHT)
        self.show_errors_btn = ttk.Button(actions_right, text="Показать ошибки",
                                          command=self.statistics.show_errors, state=tk.NORMAL)
        self.show_stats_btn = ttk.Button(actions_right, text="Показать статистику",
                                         command=self.statistics.show_all, state=tk.NORMAL)
        self.show_errors_btn.pack(side=tk.RIGHT, padx=5)
        self.show_stats_btn.pack(side=tk.RIGHT, padx=5)

    # Остались только оверлей, show_var_graph и пара методов
    def show_loading(self, text="Загрузка..."):
        if not self.loading_overlay_shown:
            self.loading_overlay_shown = True
            self.loading_overlay.show(text)

    def hide_loading(self):
        self.loading_overlay_shown = False
        self.loading_overlay.hide()
        self.master.update_idletasks()

    def _on_window_map(self, event):
        if self.loading_overlay_shown:
            self.loading_overlay.show()
            if self.loading_overlay.overlay:
                self.loading_overlay._place_overlay()

    def _cache_original(self):
        if self.survey_data:
            self.survey_data_original = {
                sheet: df.copy() for sheet, df in self.survey_data.items()
            }

    def _get_base_name(self):
        if self.mode.get() == "excel":
            return Path(self.survey_path.get()).stem
        return "survey"

    def _has_coordinates(self):
        if not self.survey_data:
            return False
        for df in self.survey_data.values():
            if ('X' in df.columns and 'Y' in df.columns) or ('x' in df.columns and 'y' in df.columns):
                return True
        return False

    def _get_nav_text(self, sheet_name):
        if not self.nav_data:
            return None
        if len(sheet_name) >= 6:
            date_prefix = sheet_name[:6]
            year = "20" + date_prefix[0:2]
            month = date_prefix[2:4]
            day = date_prefix[4:6]
            nav_key_full = year + month + day
            return self.nav_data.get(nav_key_full) or self.nav_data.get(date_prefix)
        else:
            return self.nav_data.get(sheet_name)

    def _add_statistics(self, message):
        self.statistics.add(message)

    def show_var_graph(self):
        # можно вынести в отдельный файл, но пока оставим
        if self.var_df is None or self.var_df.empty:
            messagebox.showinfo("Вариации", "Нет данных для отображения.")
            return
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        win = tk.Toplevel(self.master)
        win.title("График вариаций МВС")
        win.geometry("800x500")
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        var_df = self.var_df.copy()
        var_df['date'] = var_df['datetime'].dt.date
        for date, group in var_df.groupby('date'):
            ax.plot(group['datetime'], group['var'], linewidth=0.8, marker='', linestyle='-')
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.set_xlabel('Время')
        ax.set_ylabel('Вариация (нТл)')
        ax.set_title('Вариации магнитного поля')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, linestyle='--', alpha=0.4)
        normal_field = self.var_df.attrs.get('normal_field', 0) if hasattr(self.var_df, 'attrs') else 0
        ax.text(0.98, 0.95, f"Нормальное поле: {normal_field:.0f} нТл",
                transform=ax.transAxes, ha='right', va='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        pan_data = {'pressed': False, 'x': None, 'y': None}


        def on_press(event):
            if event.inaxes != ax or event.button != 1: return
            pan_data['pressed'] = True
            pan_data['x'] = event.xdata
            pan_data['y'] = event.ydata


        def on_motion(event):
            if not pan_data['pressed'] or event.inaxes != ax: return
            if pan_data['x'] is None or pan_data['y'] is None: return
            dx = event.xdata - pan_data['x']
            dy = event.ydata - pan_data['y']
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            ax.set_xlim(xlim[0]-dx, xlim[1]-dx)
            ax.set_ylim(ylim[0]-dy, ylim[1]-dy)
            canvas.draw()


        def on_release(event): 
            pan_data['pressed'] = False


        def on_scroll(event):
            if event.inaxes != ax: return
            scale = 1.1 if event.button == 'down' else 0.9
            xlim = ax.get_xlim(); ylim = ax.get_ylim()
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

    
    def toggle_theme(self):
        self.dark_theme = not self.dark_theme
        import matplotlib.pyplot as plt

        # Устанавливаем базовый шрифт ДО переключения темы
        default_font = ('Segoe UI', 8)
        self.master.option_add('*Font', default_font)

        # Обновляем фон canvas
        bg_color = '#2b2b2b' if self.dark_theme else 'white'
        if self.survey_map_figure:
            self.survey_map_figure.set_facecolor(bg_color)
        if self.nav_map_figure:
            self.nav_map_figure.set_facecolor(bg_color)
        if self.survey_map_canvas:
            self.survey_map_canvas.draw_idle()
        if self.nav_map_canvas:
            self.nav_map_canvas.draw_idle()

        if self.dark_theme:
            sv_ttk.set_theme("dark")
            self.theme_btn.config(text="☀️")
            plt.style.use('dark_background')
            mpl.rcParams['figure.facecolor'] = '#2b2b2b'
        else:
            sv_ttk.set_theme("light")
            self.theme_btn.config(text="🌙")
            plt.style.use('default')
            mpl.rcParams['figure.facecolor'] = 'white'

        # Явно корректируем стили после применения темы
        style = ttk.Style()                        # ← сначала создаём
        style.configure('.', font=default_font)
        style.configure('TLabel', font=default_font)
        style.configure('TButton', font=default_font)
        style.configure('TLabelframe.Label', font=default_font)
        style.configure('TRadiobutton', font=default_font)
        style.configure('TEntry', padding=1, relief='solid', borderwidth=1)   # ← теперь можно использовать

        # Обновляем мини-карты
        if self.survey_map_figure is not None and self.survey_map_canvas is not None:
            self.survey_map_figure.clear()
            ax = self.survey_map_figure.add_subplot(111)
            MapManager.draw_survey_track(ax, self.survey_data_original or self.survey_data)
            self.survey_map_canvas.draw_idle()

        if self.nav_map_figure is not None and self.nav_map_canvas is not None:
            self.mini_maps.update_nav_map()