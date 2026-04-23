import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import os
import pandas as pd
import subprocess
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.widgets import PolygonSelector
from matplotlib.path import Path as MplPath

from logic.survey_processor import process_survey_folder
from logic.navigation_processor import process_navigation_folder
from logic.excel_writer import save_survey_excels, save_survey_with_corrections
from logic.coordinate_merger import parse_navigation_text, add_coordinates_to_df
from gui.preview_table import PreviewTable

class MainWindow:
    def __init__(self, master):
        self.master = master
        master.title("Обработка данных магнитной съёмки")
        master.geometry("1000x900")

        self.survey_map_figure = None
        self.survey_map_canvas = None
        self.nav_map_figure = None
        self.nav_map_canvas = None
        self.nav_coords_cache = None
        self.survey_path = tk.StringVar()
        self.nav_path = tk.StringVar()
        self.correction_file = tk.StringVar()
        self.mode = tk.StringVar(value="with_v1")
        self.survey_data = None
        self.nav_data = None
        self.output_dir = tk.StringVar()
        self.coordinates_assigned = False
        self.errors = []
        self.statistics_history = []

        self.create_widgets()

    def create_widgets(self):
        # ===== Выходная папка =====
        frame_output = ttk.Frame(self.master)
        frame_output.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(frame_output, text="Папка для сохранения:").pack(side=tk.LEFT)
        ttk.Entry(frame_output, textvariable=self.output_dir, width=60).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_output, text="Обзор...", command=self.browse_output).pack(side=tk.LEFT)
        ttk.Button(frame_output, text="📁", width=3, command=lambda: self.open_folder(self.output_dir.get())).pack(side=tk.LEFT, padx=2)

        # ===== Источники данных =====
        frame_paths = ttk.LabelFrame(self.master, text="Источники данных", padding=10)
        frame_paths.pack(fill=tk.X, padx=10, pady=5)

        # Формат файла (строка 0)
        ttk.Label(frame_paths, text="Формат файла:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        fmt_subframe = ttk.Frame(frame_paths)
        fmt_subframe.grid(row=0, column=1, sticky='w')
        
        ttk.Radiobutton(fmt_subframe, text="CSV с V1", variable=self.mode, value="with_v1").pack(side=tk.LEFT)
        ttk.Radiobutton(fmt_subframe, text="CSV без V1", variable=self.mode, value="without_v1").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(fmt_subframe, text="Текстовый файл", variable=self.mode, value="text",
                        command=self._on_text_mode_selected).pack(side=tk.LEFT, padx=10)

        # Папка съёмки (строка 1)
        ttk.Label(frame_paths, text="Папка с данными съёмки:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame1 = ttk.Frame(frame_paths)
        entry_frame1.grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame1, textvariable=self.survey_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame1, text="Обзор...", command=self.browse_survey).pack(side=tk.LEFT)
        ttk.Button(entry_frame1, text="📁", width=3, command=lambda: self.open_folder(self.survey_path.get())).pack(side=tk.LEFT, padx=2)

        # Папка навигации (строка 2)
        ttk.Label(frame_paths, text="Папка с данными навигации:").grid(row=2, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame2 = ttk.Frame(frame_paths)
        entry_frame2.grid(row=2, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame2, textvariable=self.nav_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame2, text="Обзор...", command=self.browse_navigation).pack(side=tk.LEFT)
        ttk.Button(entry_frame2, text="📁", width=3, command=lambda: self.open_folder(self.nav_path.get())).pack(side=tk.LEFT, padx=2)

        # Файл вариаций (строка 3)
        ttk.Label(frame_paths, text="Файл вариаций (Excel):").grid(row=3, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame3 = ttk.Frame(frame_paths)
        entry_frame3.grid(row=3, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame3, textvariable=self.correction_file, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame3, text="Обзор...", command=self.browse_correction).pack(side=tk.LEFT)
        ttk.Button(entry_frame3, text="📁", width=3,
                   command=lambda: self.open_folder(str(Path(self.correction_file.get()).parent) if self.correction_file.get() else "")).pack(side=tk.LEFT, padx=2)

        # Разрешаем второй колонке растягиваться
        frame_paths.columnconfigure(1, weight=1)

        # ===== Предпросмотр =====
        frame_preview = ttk.LabelFrame(self.master, text="Предварительный просмотр", padding=10)
        frame_preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        paned = ttk.PanedWindow(frame_preview, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Съёмка
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        ttk.Label(left_frame, text="Данные съёмки (по дням)").pack()
        self.survey_table = PreviewTable(left_frame, columns=['День', 'Листов', 'Строк'])
        self.survey_table.pack(fill=tk.BOTH, expand=True)

        # Навигация
        mid_frame = ttk.Frame(paned)
        paned.add(mid_frame, weight=1)
        ttk.Label(mid_frame, text="Данные навигации (по датам)").pack()
        self.nav_table = PreviewTable(mid_frame, columns=['Дата', 'Строк'])
        self.nav_table.pack(fill=tk.BOTH, expand=True)

        # Вариации
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        self.corr_label_var = tk.StringVar(value="Файл вариаций не выбран")
        ttk.Label(right_frame, textvariable=self.corr_label_var).pack()
        self.corr_table = PreviewTable(right_frame, columns=['Лист', 'Строк'])
        self.corr_table.pack(fill=tk.BOTH, expand=True)

        # ===== Мини-карты (съёмка и навигация) =====
        maps_container = ttk.Frame(self.master)
        maps_container.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

        # Левая мини-карта (съёмка)
        survey_map_frame = ttk.LabelFrame(maps_container, text="Трек съёмки (кликните для увеличения)", padding=5)
        survey_map_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.survey_map_figure = Figure(figsize=(5, 3), dpi=100)
        self.survey_map_canvas = FigureCanvasTkAgg(self.survey_map_figure, master=survey_map_frame)
        self.survey_map_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.survey_map_canvas.mpl_connect('button_press_event', self.on_survey_map_click)

        # Правая мини-карта (навигация)
        nav_map_frame = ttk.LabelFrame(maps_container, text="Навигационные точки (кликните для увеличения)", padding=5)
        nav_map_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.nav_map_figure = Figure(figsize=(5, 3), dpi=100)
        self.nav_map_canvas = FigureCanvasTkAgg(self.nav_map_figure, master=nav_map_frame)
        self.nav_map_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.nav_map_canvas.mpl_connect('button_press_event', self.on_nav_map_click)

        # ===== Нижние кнопки =====
        bottom_frame = ttk.Frame(self.master)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        # Кнопки действий слева
        actions_left = ttk.Frame(bottom_frame)
        actions_left.pack(side=tk.LEFT)
        ttk.Button(actions_left, text="Присвоить координаты", command=self.process_with_coordinates).pack(side=tk.LEFT, padx=5)
        self.correct_btn = ttk.Button(actions_left, text="Применить поправки", command=self.process_corrections, state=tk.DISABLED)
        self.correct_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_left, text="Выделить полигон", command=self.open_polygon_selector).pack(side=tk.LEFT, padx=5)

        # Кнопки статистики и ошибок справа
        actions_right = ttk.Frame(bottom_frame)
        actions_right.pack(side=tk.RIGHT)
        ttk.Button(actions_right, text="Показать ошибки", command=self.show_errors).pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions_right, text="Показать статистику", command=self.show_all_statistics).pack(side=tk.RIGHT, padx=5)

        # ===== Статусная строка =====
        self.status_var = tk.StringVar(value="Готов")
        status_bar = ttk.Label(self.master, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.progress = ttk.Progressbar(status_bar, mode='indeterminate', length=100)
        self.progress.pack(side=tk.RIGHT, padx=5)
    
    def draw_survey_track(self, ax):
        """Рисует трек съёмки на оси ax (без очистки)."""
        if not self.survey_data:
            ax.text(0.5, 0.5, 'Нет данных съёмки', ha='center', va='center', transform=ax.transAxes)
            return
        all_lon, all_lat = [], []
        for day, sheets in self.survey_data.items():
            for df in sheets.values():
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

    def draw_nav_track(self, ax):
        if not self.nav_coords_cache:
            ax.text(0.5, 0.5, 'Нет данных навигации', ha='center', va='center', transform=ax.transAxes)
            return
        all_lon, all_lat = [], []
        for points in self.nav_coords_cache.values():
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

    def on_survey_map_click(self, event):
        if not self.survey_data:
            return
        win = tk.Toplevel(self.master)
        win.title("Интерактивная карта съёмки")
        win.geometry("900x700")
        fig = Figure(figsize=(9, 7), dpi=100)
        ax = fig.add_subplot(111)
        self.draw_survey_track(ax)
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Pan & Zoom (как раньше, без изменений)
        pan_data = {'pressed': False, 'x': None, 'y': None}
        def on_press(event):
            if event.inaxes != ax: return
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
            ax.set_xlim([xlim[0] - dx, xlim[1] - dx])
            ax.set_ylim([ylim[0] - dy, ylim[1] - dy])
            canvas.draw()
        def on_release(event):
            pan_data['pressed'] = False
        canvas.mpl_connect('button_press_event', on_press)
        canvas.mpl_connect('motion_notify_event', on_motion)
        canvas.mpl_connect('button_release_event', on_release)
        
        def on_scroll(event):
            scale_factor = 1.1
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            xdata = event.xdata
            ydata = event.ydata
            if xdata is None or ydata is None: return
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

    def on_nav_map_click(self, event):
        if not self.nav_data:
            return
        win = tk.Toplevel(self.master)
        win.title("Интерактивная карта навигации")
        win.geometry("900x700")
        fig = Figure(figsize=(9, 7), dpi=100)
        ax = fig.add_subplot(111)
        self.draw_nav_track(ax)
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        
        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Pan & Zoom (аналогично)
        pan_data = {'pressed': False, 'x': None, 'y': None}
        def on_press(event):
            if event.inaxes != ax: return
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
            ax.set_xlim([xlim[0] - dx, xlim[1] - dx])
            ax.set_ylim([ylim[0] - dy, ylim[1] - dy])
            canvas.draw()
        def on_release(event):
            pan_data['pressed'] = False
        canvas.mpl_connect('button_press_event', on_press)
        canvas.mpl_connect('motion_notify_event', on_motion)
        canvas.mpl_connect('button_release_event', on_release)
        
        def on_scroll(event):
            scale_factor = 1.1
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            xdata = event.xdata
            ydata = event.ydata
            if xdata is None or ydata is None: return
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

    # ---------- Вспомогательные методы ----------
    def open_folder(self, path):
        if path and os.path.exists(path):
            if os.name == 'nt':
                os.startfile(path)
            else:
                subprocess.run(['open', path])

    def browse_survey(self):
        path = filedialog.askdirectory(title="Данные съемки")
        if path:
            self.survey_path.set(path)
            parent = Path(path).parent

            if not self.output_dir.get():
                default_out = parent / "Результаты"
                self.output_dir.set(str(default_out))
                
            total_csv = len(list(Path(path).glob("**/*.csv")))
            self.status_var.set(f"Папка выбрана, найдено CSV: {total_csv}.")
            if self.mode.get() != "text":
                self.load_survey()

    def browse_navigation(self):
        path = filedialog.askdirectory(title="Данные навигации")
        if path:
            self.nav_path.set(path)
            total_txt = len(list(Path(path).glob("*.txt")))
            self.status_var.set(f"Папка выбрана, найдено TXT: {total_txt}")
            self.load_navigation()

    def browse_correction(self):
        path = filedialog.askopenfilename(
            title="Файл вариаций",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if path:
            self.correction_file.set(path)
            self.load_correction_preview(path)

    def browse_output(self):
        path = filedialog.askdirectory(title="Выберите папку для сохранения результатов")
        if path:
            # Создаём папку "Результаты" внутри выбранной директории
            results_folder = Path(path) / "Результаты"
            self.output_dir.set(str(results_folder))

    # ---------- Загрузка и предпросмотр ----------
    def load_survey(self):
        if not self.survey_path.get():
            return
        if self.mode.get() == "text":
            messagebox.showinfo("Информация", "Режим 'Текстовый файл' находится в разработке")
            return
        self.status_var.set("Загрузка данных съёмки...")
        self.progress.start()
        self.master.update()
        def task():
            try:
                data, stats = process_survey_folder(
                    self.survey_path.get(),
                    self.mode.get(),
                    progress_callback=lambda msg: self.master.after(0, self.status_var.set, msg)
                )
                self.survey_data = data
                self.errors = stats.get('errors', [])
                self.master.after(0, self.update_survey_preview, data, stats)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.master.after(0, self.progress.stop)
                self.master.after(0, self.status_var.set, "Готов")
        threading.Thread(target=task, daemon=True).start()

    def _on_text_mode_selected(self):
        if self.mode.get() == "text":
            messagebox.showinfo("Информация", 
                                "Режим 'Текстовый файл' находится в разработке.\n"
                                "Данные не будут загружены при выборе папки.")
            # Автоматически переключаем обратно на CSV с V1
            self.mode.set("with_v1")
        
    def update_survey_preview(self, data, stats):
        self.survey_table.clear()
        total_rows = 0
        for day, sheets in data.items():
            rows_in_day = sum(len(df) for df in sheets.values())
            total_rows += rows_in_day
            self.survey_table.insert_row([day, len(sheets), rows_in_day])
        
        try:
            source_folder = Path(self.output_dir.get()) / "Исходники"
            save_survey_excels(self.survey_data, str(source_folder), self.mode.get(), nav_data=None, keep_only_matched=False)
        except Exception as e:
            self.errors.append(f"Не удалось сохранить исходные файлы: {e}")
        
        # Создаём объединённый Excel
        self.save_merged_survey_excel()

        # Обновляем мини-карту
        if self.survey_map_figure is not None:
            self.survey_map_figure.clear()
            ax = self.survey_map_figure.add_subplot(111)
            self.draw_survey_track(ax)
            self.survey_map_canvas.draw()

        msg = f"Съёмка загружена. Дней: {stats['days']}, файлов: {stats['files']}, всего строк: {total_rows}"
        if stats['errors']:
            msg += f"\nОшибок: {len(stats['errors'])} (нажмите 'Показать ошибки')"
        self._add_statistics(msg)
        messagebox.showinfo("Готово", msg)
        
    def load_navigation(self):
        if not self.nav_path.get():
            return
        self.status_var.set("Загрузка навигационных данных...")
        self.progress.start()
        self.master.update()
        def task():
            try:
                data = process_navigation_folder(self.nav_path.get())
                self.nav_data = data
                self.master.after(0, self.update_nav_preview, data)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.master.after(0, self.progress.stop)
                self.master.after(0, self.status_var.set, "Готов")
        threading.Thread(target=task, daemon=True).start()

    def update_nav_preview(self, data):
        self.nav_table.clear()
        total_lines = 0
        for date_str, text in data.items():
            lines = text.count('\n') + 1 if text else 0
            total_lines += lines
            self.nav_table.insert_row([date_str, lines])
        
        # Сохраняем объединённые навигационные файлы в Исходники
        if self.output_dir.get():
            sources_folder = Path(self.output_dir.get()) / "Исходники"
            sources_folder.mkdir(parents=True, exist_ok=True)
            for date_str, content in data.items():
                # Преобразуем YYYYMMDD в DDMMYY
                if len(date_str) == 8:
                    day = date_str[6:8]
                    month = date_str[4:6]
                    year = date_str[2:4]
                    short_date = f"{day}{month}{year}"
                else:
                    short_date = date_str
                # Добавляем V1 если режим with_v1
                suffix = "V1" if self.mode.get() == "with_v1" else ""
                nav_file = sources_folder / f"{short_date}{suffix}.txt"
                try:
                    nav_file.write_text(content, encoding='utf-8')
                except Exception as e:
                    self.errors.append(f"Не удалось сохранить навигацию {short_date}{suffix}: {e}")
        
         # Строим кэш координат для быстрой отрисовки карты
        self.nav_coords_cache = {}
        from logic.coordinate_merger import parse_navigation_text
        for date_str, text in data.items():
            try:
                coords = parse_navigation_text(text)
                points = list(coords.values())
                self.nav_coords_cache[date_str] = points
            except:
                self.nav_coords_cache[date_str] = []

        if self.nav_map_figure is not None:
            self.nav_map_figure.clear()
            ax = self.nav_map_figure.add_subplot(111)
            self.draw_nav_track(ax)
            self.nav_map_canvas.draw()

        msg = f"Навигация загружена. Дат: {len(data)}, всего строк: {total_lines}"
        self._add_statistics(msg)
        messagebox.showinfo("Готово", msg)

    def load_correction_preview(self, file_path):
        self.status_var.set("Чтение файла вариаций...")
        self.progress.start()
        self.master.update()
        def task():
            try:
                xl = pd.ExcelFile(file_path)
                sheets = xl.sheet_names
                total_rows = 0
                sheet_stats = []
                for sheet in sheets:
                    df = xl.parse(sheet)
                    rows = len(df)
                    total_rows += rows
                    sheet_stats.append((sheet, rows))
                self.master.after(0, self._update_correction_preview, file_path, sheet_stats, len(sheets), total_rows)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", f"Не удалось прочитать файл вариаций:\n{e}")
            finally:
                self.master.after(0, self.progress.stop)
                self.master.after(0, self.status_var.set, "Готов")
        threading.Thread(target=task, daemon=True).start()

    def _update_correction_preview(self, file_path, sheet_stats, sheets_count, total_rows):
        self.corr_table.clear()
        for sheet, rows in sheet_stats:
            self.corr_table.insert_row([sheet, rows])
        self.corr_label_var.set(f"Файл: {Path(file_path).name}")
        msg = f"Вариации загружены. Листов: {sheets_count}, всего строк: {total_rows}"
        self._add_statistics(msg)
        messagebox.showinfo("Готово", msg)

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

    # ---------- Проверка координат ----------
    def _has_coordinates(self):
        if not self.survey_data:
            return False
        for sheets in self.survey_data.values():
            for df in sheets.values():
                if 'X' in df.columns and 'Y' in df.columns:
                    return True
        return False

    # ---------- Обработка координат ----------
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
        self.status_var.set("Присвоение координат...")
        self.progress.start()
        self.master.update()
        def task():
            try:
                coord_folder = Path(self.output_dir.get()) / "С координатами"
                stats_filtered = save_survey_excels(
                    self.survey_data,
                    str(coord_folder),
                    self.mode.get(),
                    nav_data=self.nav_data,
                    keep_only_matched=False
                )
                # === ОБНОВЛЯЕМ survey_data, добавляя X и Y ===
                for day, sheets in self.survey_data.items():
                    if len(day) == 6:
                        year = "20" + day[4:6]
                        nav_key = year + day[2:4] + day[0:2]
                    else:
                        nav_key = day
                    nav_text = self.nav_data.get(nav_key)
                    if nav_text:
                        try:
                            coord_dict = parse_navigation_text(nav_text)
                            for sheet_name, df in sheets.items():
                                df_res = add_coordinates_to_df(df, coord_dict)
                                self.survey_data[day][sheet_name] = df_res
                        except Exception as e:
                            print(f"Не удалось добавить координаты в данные {day}: {e}")
                self.coordinates_assigned = True
                # ============================================
                msg = (f"Координаты присвоены.\n"
                    f"Всего строк: {stats_filtered['total_rows']}\n"
                    f"Строк с координатами: {stats_filtered['matched_rows']}\n"
                    f"Удалено строк без координат: {stats_filtered['removed_rows']}\n"
                    f"Удалено пустых листов: {stats_filtered['sheets_removed']}\n"
                    f"Файлы сохранены в: {coord_folder}")
                self._add_statistics(msg)
                self.master.after(0, lambda: self.correct_btn.config(state=tk.NORMAL))
                self.master.after(0, messagebox.showinfo, "Готово", msg)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.master.after(0, self.progress.stop)
                self.master.after(0, self.status_var.set, "Готов")
        threading.Thread(target=task, daemon=True).start()

    # ---------- Применение поправок ----------
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
        if not self._has_coordinates():
            messagebox.showwarning("Предупреждение", "Сначала присвойте координаты")
            return
        self.status_var.set("Применение поправок...")
        self.progress.start()
        self.master.update()
        def task():
            try:
                corr_folder = Path(self.output_dir.get()) / "С поправками"
                stats_filtered = save_survey_with_corrections(
                    self.survey_data,
                    str(corr_folder),
                    self.mode.get(),
                    self.correction_file.get(),
                    keep_only_matched=True
                )
                msg = (f"Поправки применены.\n"
                    f"Всего строк: {stats_filtered['total_rows']}\n"
                    f"Строк с вариацией: {stats_filtered['matched_rows']}\n"
                    f"Удалено строк без вариации: {stats_filtered['removed_rows']}\n"
                    f"Удалено пустых листов: {stats_filtered['sheets_removed']}\n"
                    f"Файлы сохранены в: {corr_folder}")
                self._add_statistics(msg)
                self.master.after(0, messagebox.showinfo, "Готово", msg)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.master.after(0, self.progress.stop)
                self.master.after(0, self.status_var.set, "Готов")
        threading.Thread(target=task, daemon=True).start()

    # ========== НОВЫЕ МЕТОДЫ ДЛЯ ПОЛИГОНОВ ==========
    def _merge_all_survey_data(self):
        """Объединяет все листы из survey_data в один DataFrame."""
        if not self.survey_data:
            return None
        all_dfs = []
        for day, sheets in self.survey_data.items():
            for sheet_name, df in sheets.items():
                if 'lon' not in df.columns or 'lat' not in df.columns:
                    continue
                df_copy = df.copy()
                df_copy['lon'] = pd.to_numeric(df_copy['lon'], errors='coerce')
                df_copy['lat'] = pd.to_numeric(df_copy['lat'], errors='coerce')
                df_copy = df_copy.dropna(subset=['lon', 'lat'])
                if df_copy.empty:
                    continue
                df_copy['source_sheet'] = f"{day}_{sheet_name}"
                all_dfs.append(df_copy)
        if not all_dfs:
            return None
        return pd.concat(all_dfs, ignore_index=True)

    def save_merged_survey_excel(self):
        """Создаёт merged_all.xlsx в папке Исходники."""
        df_merged = self._merge_all_survey_data()
        if df_merged is None:
            return
        merged_path = Path(self.output_dir.get()) / "Исходники" / "merged_all.xlsx"
        merged_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(merged_path, engine='openpyxl') as writer:
            df_merged.to_excel(writer, sheet_name='All_Data', index=False)

    def open_polygon_selector(self):
        """Открывает окно с картой и инструментом выделения полигона."""
        df_merged = self._merge_all_survey_data()
        if df_merged is None:
            messagebox.showwarning("Нет данных", "Сначала загрузите данные съёмки.")
            return

        win = tk.Toplevel(self.master)
        win.title("Выделение полигона")
        win.geometry("900x700")

        fig = Figure(figsize=(9, 7), dpi=100)
        ax = fig.add_subplot(111)
        # Рисуем точки
        ax.plot(df_merged['lon'], df_merged['lat'], 'b.', markersize=1)
        ax.set_xlabel('Долгота')
        ax.set_ylabel('Широта')
        ax.set_title('Выделите полигон (клики левой кнопкой, Enter для завершения)')
        ax.grid(True)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        polygon_vertices = []

        def on_select(verts):
            polygon_vertices.clear()
            polygon_vertices.extend(verts)
            print(f"Полигон: {len(verts)} вершин")

        selector = PolygonSelector(ax, on_select, useblit=True)
        win.selector = selector
        canvas.draw_idle()

        # Кнопка сохранения
        save_btn = ttk.Button(win, text="Сохранить выделенные точки", command=lambda: self.save_polygon_points(df_merged, polygon_vertices, win))
        save_btn.pack(side=tk.BOTTOM, pady=10)

    def save_polygon_points(self, df_merged, vertices, parent_window):
        """Сохраняет точки внутри полигона в Excel."""
        if not vertices:
            messagebox.showerror("Ошибка", "Полигон не нарисован.")
            return
        poly_path = MplPath(vertices)
        points = df_merged[['lon', 'lat']].to_numpy()
        inside = poly_path.contains_points(points)
        df_selected = df_merged[inside].copy()
        if df_selected.empty:
            messagebox.showinfo("Результат", "В полигон не попало ни одной точки.")
            return

        # Папка "Полигоны"
        poly_folder = Path(self.output_dir.get()) / "Полигоны"
        poly_folder.mkdir(parents=True, exist_ok=True)
        file_name = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialdir=str(poly_folder),
            title="Сохранить полигон как"
        )
        if not file_name:
            return
        out_path = Path(file_name)
        with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
            df_selected.to_excel(writer, sheet_name='Polygon', index=False)
        messagebox.showinfo("Готово", f"Сохранено {len(df_selected)} строк в {out_path}")
        parent_window.destroy()