import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.loading_overlay import LoadingOverlay
from logic.excel_writer import save_survey_excels, save_survey_with_corrections, save_filtered_survey
from logic.coordinate_merger import parse_navigation_text, add_coordinates_to_df
from gui.map_manager import MapManager
from gui.data_loaders import DataLoaders
from utils.helpers import open_folder


class MainWindow:
    def __init__(self, master):
        self.master = master
        master.title("Обработка данных магнитной съёмки")
        master.geometry("1000x700")

        # Переменные состояния
        self.survey_map_figure = None
        self.survey_map_canvas = None
        self.nav_map_figure = None
        self.nav_map_canvas = None
        self.nav_coords_cache = None
        self.var_df = None
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

        self.data_loaders = DataLoaders(self)
        self.create_widgets()

        self.master.bind("<Map>", self._on_window_map)

    def create_widgets(self):
        # Выходная папка
        frame_output = ttk.Frame(self.master)
        frame_output.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(frame_output, text="Папка для сохранения:").pack(side=tk.LEFT)
        ttk.Entry(frame_output, textvariable=self.output_dir, width=60).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_output, text="Обзор...", command=self.browse_output).pack(side=tk.LEFT)
        ttk.Button(frame_output, text="📁", width=3,
                   command=lambda: open_folder(self.output_dir.get())).pack(side=tk.LEFT, padx=2)

        # Источники данных
        frame_paths = ttk.LabelFrame(self.master, text="Источники данных", padding=10)
        frame_paths.pack(fill=tk.X, padx=10, pady=5)

        # Формат файла
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
        ttk.Button(entry_frame1, text="Обзор...", command=self.browse_survey).pack(side=tk.LEFT)
        ttk.Button(entry_frame1, text="📁", width=3,
                   command=lambda: open_folder(self.survey_path.get())).pack(side=tk.LEFT, padx=2)

        # Папка навигации
        ttk.Label(frame_paths, text="Папка с данными навигации:").grid(row=2, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame2 = ttk.Frame(frame_paths)
        entry_frame2.grid(row=2, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame2, textvariable=self.nav_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame2, text="Обзор...", command=self.browse_navigation).pack(side=tk.LEFT)
        ttk.Button(entry_frame2, text="📁", width=3,
                   command=lambda: open_folder(self.nav_path.get())).pack(side=tk.LEFT, padx=2)

        # Файл вариаций
        ttk.Label(frame_paths, text="Файл вариаций (Excel):").grid(row=3, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame3 = ttk.Frame(frame_paths)
        entry_frame3.grid(row=3, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame3, textvariable=self.correction_file, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame3, text="Обзор...", command=self.browse_correction).pack(side=tk.LEFT)
        ttk.Button(entry_frame3, text="📁", width=3,
                   command=lambda: open_folder(str(Path(self.correction_file.get()).parent) if self.correction_file.get() else "")).pack(side=tk.LEFT, padx=2)
        self.var_graph_btn = ttk.Button(entry_frame3, text="📊 Вариации", command=self.show_var_graph, state=tk.DISABLED)
        self.var_graph_btn.pack(side=tk.LEFT, padx=5)
        frame_paths.columnconfigure(1, weight=1)

        # Мини-карты
        maps_container = ttk.Frame(self.master)
        maps_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        survey_map_frame = ttk.LabelFrame(maps_container, text="Трек съёмки (кликните для увеличения)", padding=5)
        survey_map_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        survey_map_frame.pack_propagate(False)
        self.survey_map_figure = Figure(figsize=(5, 3), dpi=100)
        self.survey_map_canvas = FigureCanvasTkAgg(self.survey_map_figure, master=survey_map_frame)
        self.survey_map_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.survey_map_canvas.mpl_connect('button_press_event', self.on_survey_map_click)
        survey_map_frame.bind("<Configure>", self._on_survey_map_resize)

        nav_map_frame = ttk.LabelFrame(maps_container, text="Присвоенные координаты (кликните для увеличения)", padding=5)
        nav_map_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nav_map_frame.pack_propagate(False)
        self.nav_map_figure = Figure(figsize=(5, 3), dpi=100)
        self.nav_map_canvas = FigureCanvasTkAgg(self.nav_map_figure, master=nav_map_frame)
        self.nav_map_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.nav_map_canvas.mpl_connect('button_press_event', self.on_nav_map_click)
        nav_map_frame.bind("<Configure>", self._on_nav_map_resize)

        # Нижние кнопки
        bottom_frame = ttk.Frame(self.master)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        actions_left = ttk.Frame(bottom_frame)
        actions_left.pack(side=tk.LEFT)
        self.assign_btn = ttk.Button(actions_left, text="Присвоить координаты",
                                     command=self.process_with_coordinates, state=tk.DISABLED)
        self.assign_btn.pack(side=tk.LEFT, padx=5)
        self.correct_btn = ttk.Button(actions_left, text="Ввести поправки",
                                      command=self.process_corrections, state=tk.DISABLED)
        self.correct_btn.pack(side=tk.LEFT, padx=5)

        actions_right = ttk.Frame(bottom_frame)
        actions_right.pack(side=tk.RIGHT)
        self.show_errors_btn = ttk.Button(actions_right, text="Показать ошибки",
                                          command=self.show_errors, state=tk.NORMAL)
        self.show_stats_btn = ttk.Button(actions_right, text="Показать статистику",
                                         command=self.show_all_statistics, state=tk.NORMAL)
        self.show_errors_btn.pack(side=tk.RIGHT, padx=5)
        self.show_stats_btn.pack(side=tk.RIGHT, padx=5)

    # ---------------------------------------------------------------------
    # Управление оверлеем
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

    # ---------------------------------------------------------------------
    # Выбор путей
    def _ensure_output_dir(self, base_path):
        p = Path(base_path)
        if p.name.lower() == 'результаты':
            self.output_dir.set(str(p))
        else:
            self.output_dir.set(str(p / 'Результаты'))

    def browse_output(self):
        path = filedialog.askdirectory(title="Выберите папку для сохранения результатов")
        if path:
            self._ensure_output_dir(path)

    def browse_survey(self):
        if self.mode.get() == "excel":
            path = filedialog.askopenfilename(
                title="Выберите Excel-файл съёмки",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if path:
                self._reset_survey_state()
                self.survey_path.set(path)
                parent = Path(path).parent
                if not self.output_dir.get():
                    self._ensure_output_dir(parent)
                self.data_loaders.load_survey()
        else:
            path = filedialog.askdirectory(title="Данные съёмки")
            if path:
                self._reset_survey_state()
                self.survey_path.set(path)
                parent = Path(path).parent
                if not self.output_dir.get():
                    self._ensure_output_dir(parent)
                self.data_loaders.load_survey()

    def browse_navigation(self):
        path = filedialog.askdirectory(title="Данные навигации")
        if path:
            self.nav_path.set(path)
            self.data_loaders.load_navigation()

    def browse_correction(self):
        path = filedialog.askopenfilename(title="Файл вариаций",
                                          filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")])
        if path:
            self.correction_file.set(path)
            self.data_loaders.load_correction_preview(path)

    # ---------------------------------------------------------------------
    # Мини-карты
    def on_survey_map_click(self, event):
        if self.survey_data_original:
            MapManager.create_interactive_survey_map(self.master, self.survey_data_original, self.output_dir.get())

    def on_nav_map_click(self, event):
        # Проверяем, есть ли в survey_data реальные координаты X/Y
        has_real_coords = self.survey_data and any(
            ('X' in df.columns and 'Y' in df.columns) or ('x' in df.columns and 'y' in df.columns)
            for df in self.survey_data.values()
        )
        if has_real_coords:
            MapManager._create_window(
                self.master,
                "Присвоенные координаты",
                MapManager.draw_assigned_track,
                self.survey_data,
                self.output_dir.get(),
                enable_polygon=False
            )
        elif self.nav_coords_cache:
            MapManager.create_interactive_nav_map(self.master, self.nav_coords_cache)

    def _on_survey_map_resize(self, event):
        if not event.widget.winfo_exists():
            return
        w, h = event.width, event.height
        dpi = self.survey_map_figure.get_dpi()
        self.survey_map_figure.set_size_inches(max(w / dpi, 0.2), max(h / dpi, 0.2), forward=False)
        self.survey_map_canvas.get_tk_widget().update_idletasks()
        self.survey_map_canvas.draw_idle()

    def _on_nav_map_resize(self, event):
        if not event.widget.winfo_exists():
            return
        w, h = event.width, event.height
        dpi = self.nav_map_figure.get_dpi()
        self.nav_map_figure.set_size_inches(max(w / dpi, 0.2), max(h / dpi, 0.2), forward=False)
        self.nav_map_canvas.get_tk_widget().update_idletasks()
        self.nav_map_canvas.draw_idle()

    def _cache_original(self):
        if self.survey_data:
            self.survey_data_original = {
                sheet: df.copy() for sheet, df in self.survey_data.items()
            }

    def _reset_survey_state(self):
        self.survey_data_corrected = None
        self.coordinates_assigned = False
        self.survey_data_original = None

    def show_var_graph(self):
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
            if event.inaxes != ax or event.button != 1:
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
            ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            canvas.draw()
        
        def on_release(event):
            pan_data['pressed'] = False
        
        def on_scroll(event):
            if event.inaxes != ax:
                return
            scale = 1.1 if event.button == 'down' else 0.9
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            w, h = xlim[1] - xlim[0], ylim[1] - ylim[0]
            cx = event.xdata if event.xdata else (xlim[0] + xlim[1]) / 2
            cy = event.ydata if event.ydata else (ylim[0] + ylim[1]) / 2
            nw, nh = w * scale, h * scale
            ax.set_xlim(cx - nw * (cx - xlim[0]) / w, cx + nw * (xlim[1] - cx) / w)
            ax.set_ylim(cy - nh * (cy - ylim[0]) / h, cy + nh * (ylim[1] - cy) / h)
            canvas.draw()
        
        canvas.mpl_connect('button_press_event', on_press)
        canvas.mpl_connect('motion_notify_event', on_motion)
        canvas.mpl_connect('button_release_event', on_release)
        canvas.mpl_connect('scroll_event', on_scroll)

    # ---------------------------------------------------------------------
    # Обработка данных
    def _has_coordinates(self):
        if not self.survey_data:
            return False
        for df in self.survey_data.values():
            if ('X' in df.columns and 'Y' in df.columns) or ('x' in df.columns and 'y' in df.columns):
                return True
        return False

    def process_with_coordinates(self):
        if not self.survey_data:
            messagebox.showwarning("Предупреждение", "Сначала загрузите данные съёмки")
            return
        if not self.nav_data:
            messagebox.showwarning("Предупреждение", "Сначала загрузите данные навигации")
            return
        if not self.output_dir.get():
            messagebox.showwarning("Предупреждение", "Выберите папку для сохранения")
            return
        if self._has_coordinates():
            if not messagebox.askyesno("Навигационные данные уже присутствуют",
                                       "В файле уже есть столбцы X и Y.\nПерезаписать их? (предыдущие значения будут потеряны)"):
                return

        self.show_loading("Присвоение координат и удаление пустых строк...")
        self._cache_original()
        self.master.after(100, lambda: threading.Thread(target=self._process_coord_task, daemon=True).start())

    def _process_coord_task(self):
        try:
            coord_folder = Path(self.output_dir.get())

            if self.survey_data_original is None:
                self.survey_data_original = {
                    sheet: df.copy() for sheet, df in self.survey_data.items()
                }

            stats_coord = save_survey_excels(
                self.survey_data, str(coord_folder), self.mode.get(),
                nav_data=self.nav_data, keep_only_matched=False,
                base_name=self._get_base_name()
            )
            nav_cache = {}  # словарь для навигационного текста -> coord_dict
            for sheet_name, df in list(self.survey_data.items()):
                nav_text = self._get_nav_text(sheet_name)
                if nav_text:
                    if nav_text not in nav_cache:
                        try:
                            nav_cache[nav_text] = parse_navigation_text(nav_text)
                        except Exception as e:
                            print(f"Ошибка парсинга: {e}")
                            continue
                    coord_dict = nav_cache.get(nav_text)
                    if coord_dict:
                        self.survey_data[sheet_name] = add_coordinates_to_df(df, coord_dict)

            stats_filtered, _ = save_filtered_survey(
                self.survey_data, str(coord_folder), self.mode.get(),
                base_name=self._get_base_name()
            )
            self.coordinates_assigned = True

            filtered_file = coord_folder / f"{self._get_base_name()}_{'V1' if self.mode.get() == 'with_v1' else ''}_filtered.xlsx"
            if filtered_file.exists():
                xl = pd.ExcelFile(filtered_file)
                new_data = {}
                for sheet in xl.sheet_names:
                    df = xl.parse(sheet)
                    for col in df.columns:
                        if col.lower() in ('lon', 'x', 'lat', 'y'):
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    new_data[sheet] = df
                self.survey_data = new_data

            msg = (f"Координаты присвоены, пустые строки удалены.\n"
                   f"Всего строк после присвоения: {stats_coord['total_rows']}\n"
                   f"Строк с координатами: {stats_coord['matched_rows']}\n"
                   f"Удалено пустых листов (этап координат): {stats_coord['sheets_removed']}\n"
                   f"---\n"
                   f"После фильтрации пустых строк:\n"
                   f"Оставлено строк: {stats_filtered['after_rows']}\n"
                   f"Удалено строк без координат: {stats_filtered['removed_rows']}\n"
                   f"Удалено пустых листов: {stats_filtered['sheets_removed']}\n"
                   f"Файлы сохранены в: {coord_folder}")

            self._add_statistics(msg)
            self.master.after(0, lambda: self.correct_btn.config(state=tk.NORMAL))
            self.master.after(0, self._update_nav_map)
            self.master.after(0, lambda: messagebox.showinfo("Готово", msg))
        except Exception as e:
            self.master.after(0, lambda err=e: messagebox.showerror("Ошибка", str(err)))
        finally:
            self.master.after(0, self.hide_loading)

    def _update_nav_map(self):
        if not self.nav_map_figure:
            return
        self.nav_map_figure.clear()
        ax = self.nav_map_figure.add_subplot(111)

        all_x, all_y = [], []
        data = self.survey_data_corrected or self.survey_data

        if data:
            for df in data.values():
                xcol = ycol = None
                for col in df.columns:
                    cl = col.lower()
                    if cl in ('lon', 'x'):
                        xcol = col
                    elif cl in ('lat', 'y'):
                        ycol = col
                if xcol and ycol:
                    x_vals = pd.to_numeric(df[xcol], errors='coerce').dropna()
                    y_vals = pd.to_numeric(df[ycol], errors='coerce').dropna()
                    all_x.extend(x_vals)
                    all_y.extend(y_vals)

        if all_x:
            ax.plot(all_x, all_y, 'g.', markersize=1, linestyle='None')
            ax.set_xlabel('X', fontsize=8)
            ax.set_ylabel('Y', fontsize=8)
            ax.set_title(f'Присвоенные координаты (точек: {len(all_x)})', fontsize=9)
            ax.ticklabel_format(useOffset=False, style='plain')
            ax.tick_params(axis='both', labelsize=7)
            ax.grid(True)
        else:
            ax.text(0.5, 0.5, 'Нет присвоенных координат', ha='center', va='center',
                    transform=ax.transAxes)
        ax.figure.tight_layout()
        self.nav_map_canvas.draw_idle()

    def process_corrections(self):
        if not self.survey_data:
            messagebox.showwarning("Предупреждение", "Сначала загрузите данные съёмки")
            return
        if not self.correction_file.get():
            messagebox.showwarning("Предупреждение", "Выберите файл вариаций")
            return
        if not self.output_dir.get():
            messagebox.showwarning("Предупреждение", "Выберите папку для сохранения")
            return

        self.show_loading("Ввод поправок...")
        self.master.after(100, lambda: threading.Thread(target=self._process_corr_task, daemon=True).start())

    def _process_corr_task(self):
        msg = None
        try:
            corr_folder = Path(self.output_dir.get())

            filtered_file = corr_folder / f"{self._get_base_name()}_{'V1' if self.mode.get() == 'with_v1' else ''}_filtered.xlsx"
            if filtered_file.exists():
                xl = pd.ExcelFile(filtered_file)
                filtered_data = {}
                for sheet in xl.sheet_names:
                    df = xl.parse(sheet)
                    for col in df.columns:
                        if col.lower() in ('lon', 'x', 'lat', 'y'):
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    filtered_data[sheet] = df
            else:
                filtered_data = self.survey_data

            if self.var_df is None or self.var_df.empty:
                raise ValueError("Сначала загрузите файл вариаций")

            stats_filtered, corrected_data = save_survey_with_corrections(
                filtered_data,
                str(corr_folder),
                self.mode.get(),
                self.var_df,
                keep_only_matched=True,
                base_name=self._get_base_name()
            )

            self.survey_data_corrected = corrected_data
            self.master.after(0, self._update_nav_map)

            msg = (
                f"Поправки применены.\n"
                f"Всего строк: {stats_filtered['total_rows']}\n"
                f"Строк с вариацией: {stats_filtered['matched_rows']}\n"
            )
            self._add_statistics(msg)
            self.master.after(0, lambda: messagebox.showinfo("Готово", msg))

        except Exception as e:
            self.master.after(0, lambda err=e: messagebox.showerror("Ошибка", str(err)))
        finally:
            self.master.after(0, self.hide_loading)

    # ---------------------------------------------------------------------
    # Вспомогательные методы
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

    def _get_base_name(self):
        if self.mode.get() == "excel":
            return Path(self.survey_path.get()).stem
        return "survey"

    # ---------------------------------------------------------------------
    # Статистика и ошибки
    def _add_statistics(self, message):
        self.statistics_history.append(message)

    def show_all_statistics(self):
        if not self.statistics_history:
            messagebox.showinfo("Статистика", "Статистика пока не собрана.")
            return
        win = tk.Toplevel(self.master)
        win.title("Вся статистика")
        win.geometry("700x400")
        text = tk.Text(win, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(text, command=text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text['yscrollcommand'] = scroll.set
        for i, msg in enumerate(self.statistics_history, 1):
            text.insert(tk.END, f"{i}. {msg}\n\n")
        text.config(state=tk.DISABLED)

    def show_errors(self):
        if not self.errors:
            messagebox.showinfo("Ошибки", "Ошибок нет")
            return
        win = tk.Toplevel(self.master)
        win.title("Список ошибок")
        win.geometry("700x400")
        text = tk.Text(win, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(text, command=text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text['yscrollcommand'] = scroll.set
        for err in self.errors:
            text.insert(tk.END, err + "\n")
        text.config(state=tk.DISABLED)