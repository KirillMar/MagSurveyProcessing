import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from gui.loading_overlay import LoadingOverlay
from logic.survey_processor import process_survey_folder
from logic.navigation_processor import process_navigation_folder
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
        self.survey_path = tk.StringVar()
        self.nav_path = tk.StringVar()
        self.correction_file = tk.StringVar()
        self.mode = tk.StringVar(value="with_v1")
        self.survey_data = None
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
        ttk.Radiobutton(fmt_subframe, text="Готовый Excel", variable=self.mode, value="excel").pack(side=tk.LEFT, padx=10)

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

        nav_map_frame = ttk.LabelFrame(maps_container, text="Навигационные точки (кликните для увеличения)", padding=5)
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
        self.assign_btn = ttk.Button(actions_left, text="Присвоить координаты", command=self.process_with_coordinates, state=tk.DISABLED)
        self.assign_btn.pack(side=tk.LEFT, padx=5)
        self.correct_btn = ttk.Button(actions_left, text="Ввод поправок", command=self.process_corrections, state=tk.DISABLED)
        self.correct_btn.pack(side=tk.LEFT, padx=5)
        self.remove_empty_btn = ttk.Button(actions_left, text="Удалить строки без координат", command=self.remove_empty_rows, state=tk.DISABLED)
        self.remove_empty_btn.pack(side=tk.LEFT, padx=5)

        actions_right = ttk.Frame(bottom_frame)
        actions_right.pack(side=tk.RIGHT)
        self.show_errors_btn = ttk.Button(actions_right, text="Показать ошибки", command=self.show_errors, state=tk.DISABLED)
        self.show_errors_btn.pack(side=tk.RIGHT, padx=5)
        self.show_stats_btn = ttk.Button(actions_right, text="Показать статистику", command=self.show_all_statistics, state=tk.DISABLED)
        self.show_stats_btn.pack(side=tk.RIGHT, padx=5)

    # ---------------------------------------------------------------------
    # Управление оверлеем
    def show_loading(self, text="Загрузка..."):
        if not self.loading_overlay_shown:
            self.loading_overlay_shown = True
            self.loading_overlay.show(text)

    def hide_loading(self):
        if self.loading_overlay_shown:
            self.loading_overlay_shown = False
            self.loading_overlay.hide()

    # ---------------------------------------------------------------------
    # Выбор путей
    def browse_output(self):
        path = filedialog.askdirectory(title="Выберите папку для сохранения результатов")
        if path:
            self.output_dir.set(str(Path(path) / "Результаты"))

    def browse_survey(self):
        if self.mode.get() == "excel":
            path = filedialog.askopenfilename(title="Выберите Excel-файл съёмки",
                                              filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")])
            if path:
                self.survey_path.set(path)
                parent = Path(path).parent
                if not self.output_dir.get():
                    self.output_dir.set(str(parent / "Результаты"))
                self.data_loaders.load_survey()
        else:
            path = filedialog.askdirectory(title="Данные съёмки")
            if path:
                self.survey_path.set(path)
                parent = Path(path).parent
                if not self.output_dir.get():
                    self.output_dir.set(str(parent / "Результаты"))
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
        if self.survey_data:
            MapManager.create_interactive_survey_map(self.master, self.survey_data, self.output_dir.get())

    def on_nav_map_click(self, event):
        if self.nav_data:
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

        self.show_loading("Присвоение координат...")
        self.master.update()

        def task():
            try:
                coord_folder = Path(self.output_dir.get())
                stats_filtered = save_survey_excels(self.survey_data, str(coord_folder), self.mode.get(),
                                                    nav_data=self.nav_data, keep_only_matched=False)
                for sheet_name, df in self.survey_data.items():
                    if len(sheet_name) >= 6:
                        date_prefix = sheet_name[:6]
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
                self.master.after(0, lambda: self.remove_empty_btn.config(state=tk.NORMAL))
                self.master.after(0, messagebox.showinfo, "Готово", msg)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.master.after(0, self.hide_loading)

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

        self.show_loading("Ввод поправок...")
        self.master.update()

        def task():
            try:
                corr_folder = Path(self.output_dir.get())
                # пусть функция возвращает кортеж (статистика, обновлённые данные)
                stats_filtered, corrected_data = save_survey_with_corrections(
                    self.survey_data, str(corr_folder),
                    self.mode.get(), self.correction_file.get(),
                    keep_only_matched=False
                )
                self.survey_data = corrected_data          # ← обновляем данные в памяти
                self.master.after(0, lambda: self.remove_empty_btn.config(state=tk.NORMAL))
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
                self.master.after(0, self.hide_loading)

        threading.Thread(target=task, daemon=True).start()

    def remove_empty_rows(self):
        if not self.survey_data:
            messagebox.showwarning("Предупреждение", "Нет данных")
            return
        if not self.output_dir.get():
            messagebox.showwarning("Предупреждение", "Выберите папку для сохранения")
            return

        self.show_loading("Удаление пустых строк...")
        self.master.update()

        def task():
            try:
                out_folder = Path(self.output_dir.get())
                stats = save_filtered_survey(self.survey_data, str(out_folder), self.mode.get())
                msg = (f"Пустые строки удалены.\n"
                       f"Исходных строк: {stats['total_rows']}\n"
                       f"Оставлено строк: {stats['after_rows']}\n"
                       f"Удалено строк: {stats['removed_rows']}\n"
                       f"Удалено пустых листов: {stats['sheets_removed']}\n"
                       f"Файл сохранён: {out_folder}")
                self._add_statistics(msg)
                self.master.after(0, messagebox.showinfo, "Готово", msg)
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.master.after(0, self.hide_loading)

        threading.Thread(target=task, daemon=True).start()

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