import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import os
import pandas as pd
import subprocess
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from logic.survey_processor import process_survey_folder
from logic.navigation_processor import process_navigation_folder
from logic.excel_writer import save_survey_excels, save_survey_with_corrections
from logic.coordinate_merger import parse_navigation_text, add_coordinates_to_df

from gui.preview_table import PreviewTable
from gui.map_manager import MapManager
from gui.data_loaders import DataLoaders
from utils.helpers import open_folder


class MainWindow:
    def __init__(self, master):
        self.master = master
        master.title("Обработка данных магнитной съёмки")
        master.geometry("1000x900")

        # Переменные состояния
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

        # Инициализация загрузчиков данных (передаём self)
        self.data_loaders = DataLoaders(self)

        self.create_widgets()

    # ========== Построение интерфейса ==========
    def create_widgets(self):
        # Выходная папка
        frame_output = ttk.Frame(self.master)
        frame_output.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(frame_output, text="Папка для сохранения:").pack(side=tk.LEFT)
        ttk.Entry(frame_output, textvariable=self.output_dir, width=60).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_output, text="Обзор...", command=self.browse_output).pack(side=tk.LEFT)
        ttk.Button(frame_output, text="📁", width=3, command=lambda: open_folder(self.output_dir.get())).pack(side=tk.LEFT, padx=2)

        # Источники данных
        frame_paths = ttk.LabelFrame(self.master, text="Источники данных", padding=10)
        frame_paths.pack(fill=tk.X, padx=10, pady=5)

        # Формат файла
        ttk.Label(frame_paths, text="Формат файла:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        fmt_subframe = ttk.Frame(frame_paths)
        fmt_subframe.grid(row=0, column=1, sticky='w')
        ttk.Radiobutton(fmt_subframe, text="CSV с V1", variable=self.mode, value="with_v1").pack(side=tk.LEFT)
        ttk.Radiobutton(fmt_subframe, text="CSV без V1", variable=self.mode, value="without_v1").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(fmt_subframe, text="Текстовый файл", variable=self.mode, value="text",
                        command=self._on_text_mode_selected).pack(side=tk.LEFT, padx=10)

        # Папка съёмки
        ttk.Label(frame_paths, text="Папка с данными съёмки:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame1 = ttk.Frame(frame_paths)
        entry_frame1.grid(row=1, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame1, textvariable=self.survey_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame1, text="Обзор...", command=self.browse_survey).pack(side=tk.LEFT)
        ttk.Button(entry_frame1, text="📁", width=3, command=lambda: open_folder(self.survey_path.get())).pack(side=tk.LEFT, padx=2)

        # Папка навигации
        ttk.Label(frame_paths, text="Папка с данными навигации:").grid(row=2, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame2 = ttk.Frame(frame_paths)
        entry_frame2.grid(row=2, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame2, textvariable=self.nav_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame2, text="Обзор...", command=self.browse_navigation).pack(side=tk.LEFT)
        ttk.Button(entry_frame2, text="📁", width=3, command=lambda: open_folder(self.nav_path.get())).pack(side=tk.LEFT, padx=2)

        # Файл вариаций
        ttk.Label(frame_paths, text="Файл вариаций (Excel):").grid(row=3, column=0, sticky='w', padx=(0, 10), pady=2)
        entry_frame3 = ttk.Frame(frame_paths)
        entry_frame3.grid(row=3, column=1, sticky='ew', pady=2)
        ttk.Entry(entry_frame3, textvariable=self.correction_file, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame3, text="Обзор...", command=self.browse_correction).pack(side=tk.LEFT)
        ttk.Button(entry_frame3, text="📁", width=3,
                   command=lambda: open_folder(str(Path(self.correction_file.get()).parent) if self.correction_file.get() else "")).pack(side=tk.LEFT, padx=2)

        frame_paths.columnconfigure(1, weight=1)

        # Предпросмотр
        frame_preview = ttk.LabelFrame(self.master, text="Предварительный просмотр", padding=10)
        frame_preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        paned = ttk.PanedWindow(frame_preview, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Съёмка
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        ttk.Label(left_frame, text="Данные съёмки (по дням)").pack()
        self.survey_table = PreviewTable(left_frame, columns=['День', 'Строк'])
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

        # Мини-карты
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

        # Нижние кнопки
        bottom_frame = ttk.Frame(self.master)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        actions_left = ttk.Frame(bottom_frame)
        actions_left.pack(side=tk.LEFT)
        ttk.Button(actions_left, text="Присвоить координаты", command=self.process_with_coordinates).pack(side=tk.LEFT, padx=5)
        self.correct_btn = ttk.Button(actions_left, text="Ввести поправки", command=self.process_corrections, state=tk.DISABLED)
        self.correct_btn.pack(side=tk.LEFT, padx=5)

        actions_right = ttk.Frame(bottom_frame)
        actions_right.pack(side=tk.RIGHT)
        ttk.Button(actions_right, text="Показать ошибки", command=self.show_errors).pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions_right, text="Показать статистику", command=self.show_all_statistics).pack(side=tk.RIGHT, padx=5)

        # Статусная строка
        self.status_var = tk.StringVar(value="Готов")
        status_bar = ttk.Label(self.master, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.progress = ttk.Progressbar(status_bar, mode='indeterminate', length=100)
        self.progress.pack(side=tk.RIGHT, padx=5)

    # ========== Обработчики выбора путей ==========
    def browse_output(self):
        path = filedialog.askdirectory(title="Выберите папку для сохранения результатов")
        if path:
            results_folder = Path(path) / "Результаты"
            self.output_dir.set(str(results_folder))

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
                self.data_loaders.load_survey()

    def browse_navigation(self):
        path = filedialog.askdirectory(title="Данные навигации")
        if path:
            self.nav_path.set(path)
            total_txt = len(list(Path(path).glob("*.txt")))
            self.status_var.set(f"Папка выбрана, найдено TXT: {total_txt}")
            self.data_loaders.load_navigation()

    def browse_correction(self):
        path = filedialog.askopenfilename(
            title="Файл вариаций",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if path:
            self.correction_file.set(path)
            self.data_loaders.load_correction_preview(path)

    def _on_text_mode_selected(self):
        if self.mode.get() == "text":
            messagebox.showinfo("Информация", 
                                "Режим 'Текстовый файл' находится в разработке.\n"
                                "Данные не будут загружены при выборе папки.")
            self.mode.set("with_v1")

    # ========== Работа с картами ==========
    def on_survey_map_click(self, event):
        if not self.survey_data:
            return
        MapManager.create_interactive_map_window(
            self.master, "Интерактивная карта съёмки",
            MapManager.draw_survey_track, self.survey_data
        )

    def on_nav_map_click(self, event):
        if not self.nav_data:
            return
        MapManager.create_interactive_map_window(
            self.master, "Интерактивная карта навигации",
            MapManager.draw_nav_track, self.nav_coords_cache
        )

    # ========== Обработка данных ==========
    def _has_coordinates(self):
        if not self.survey_data:
            return False
        for df in self.survey_data.values():   # теперь df — это DataFrame
            if 'X' in df.columns and 'Y' in df.columns:
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

                # Обновляем survey_data, добавляя координаты для дальнейшей обработки
                for sheet_name, df in self.survey_data.items():
                    if len(sheet_name) >= 6:
                        date_prefix = sheet_name[:6]          # YYMMDD
                        year = "20" + date_prefix[0:2]
                        month = date_prefix[2:4]
                        day = date_prefix[4:6]
                        nav_key_full = year + month + day
                        nav_text = self.nav_data.get(nav_key_full) or self.nav_data.get(date_prefix)
                    else:
                        nav_text = self.nav_data.get(sheet_name)
                    if nav_text:
                        try:
                            coord_dict = parse_navigation_text(nav_text)
                            self.survey_data[sheet_name] = add_coordinates_to_df(df, coord_dict)
                        except Exception as e:
                            print(f"Не удалось добавить координаты в {sheet_name}: {e}")

                self.coordinates_assigned = True
                msg = (f"Координаты присвоены.\n"
                    f"Всего строк: {stats_filtered['total_rows']}\n"
                    f"Строк с координатами: {stats_filtered['matched_rows']}\n"
                    f"Удалено строк без координат: {stats_filtered['removed_rows']}\n"
                    f"Удалено пустых листов: {stats_filtered['sheets_removed']}\n"
                    f"Файл сохранён: {coord_folder}")
                self._add_statistics(msg)
                self.master.after(0, lambda: self.correct_btn.config(state=tk.NORMAL))
                self.master.after(0, messagebox.showinfo, "Готово", msg)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.master.after(0, self.progress.stop)
                self.master.after(0, self.status_var.set, "Готов")

        threading.Thread(target=task, daemon=True).start()

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

        self.status_var.set("Ввод поправок...")
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

    # ========== Вспомогательные методы статистики и ошибок ==========
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