import tkinter as tk
import threading
from pathlib import Path
import pandas as pd
from tkinter import messagebox

from logic.survey_processor import process_survey_folder
from logic.navigation_processor import process_navigation_folder
from logic.excel_writer import save_survey_excels
from logic.coordinate_merger import parse_navigation_text
from gui.map_manager import MapManager


class DataLoaders:
    def __init__(self, main_window):
        self.mw = main_window

    # ------------------------------------------------------------
    # Загрузка съёмки (CSV папка)
    # ------------------------------------------------------------
    def load_survey(self):
        if not self.mw.survey_path.get():
            return
        # Excel-файл обрабатывается отдельно
        if self.mw.mode.get() == "excel":
            self.load_survey_from_excel(self.mw.survey_path.get())
            return

        self.mw.show_loading("Загрузка данных съёмки...")
        self.mw.master.update()

        def task():
            try:
                data, stats = process_survey_folder(
                    self.mw.survey_path.get(),
                    self.mw.mode.get()
                )
                self.mw.survey_data = data
                self.mw.errors = stats.get('errors', [])
                self.mw.master.after(0, self._update_survey_preview, data, stats)
            except Exception as e:
                self.mw.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.mw.master.after(0, self.mw.hide_loading)

        threading.Thread(target=task, daemon=True).start()

    # ------------------------------------------------------------
    # Загрузка готового Excel
    # ------------------------------------------------------------
    def load_survey_from_excel(self, file_path):
        self.mw.show_loading("Загрузка Excel...")
        self.mw.master.update()

        def task():
            try:
                xl = pd.ExcelFile(file_path)
                sheets = {}
                total_rows = 0
                for sheet_name in xl.sheet_names:
                    df = xl.parse(sheet_name)
                    df.columns = df.columns.str.strip().str.lower()
                    rows = len(df)
                    total_rows += rows
                    sheets[sheet_name] = df
                self.mw.survey_data = sheets
                self.mw.errors = []
                stats = {'sheets': len(sheets), 'files': 1, 'errors': []}
                self.mw.master.after(0, self._update_survey_preview, sheets, stats)
            except Exception as e:
                self.mw.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.mw.master.after(0, self.mw.hide_loading)

        threading.Thread(target=task, daemon=True).start()

    # ------------------------------------------------------------
    # Обновление предпросмотра после загрузки съёмки
    # ------------------------------------------------------------
    def _update_survey_preview(self, data, stats):
        total_rows = sum(len(df) for df in data.values())

        # Сохранение исходников (только для CSV, не для Excel)
        if self.mw.mode.get() != 'excel':
            source_folder = Path(self.mw.output_dir.get())
            save_survey_excels(self.mw.survey_data, str(source_folder), self.mw.mode.get(),
                               nav_data=None, keep_only_matched=False)

        # Обновление мини-карты съёмки
        if self.mw.survey_map_figure is not None:
            self.mw.survey_map_figure.clear()
            ax = self.mw.survey_map_figure.add_subplot(111)
            MapManager.draw_survey_track(ax, self.mw.survey_data)
            self.mw.survey_map_canvas.draw()

        # Активируем кнопки
        self.mw.assign_btn.config(state=tk.NORMAL)
        self.mw.correct_btn.config(state=tk.NORMAL)
        self.mw.remove_empty_btn.config(state=tk.NORMAL)
        self.mw.show_errors_btn.config(state=tk.NORMAL)
        self.mw.show_stats_btn.config(state=tk.NORMAL)

        msg = f"Съёмка загружена. Листов: {len(data)}, всего строк: {total_rows}"
        if stats['errors']:
            msg += f"\nОшибок: {len(stats['errors'])}"
        self.mw._add_statistics(msg)
        messagebox.showinfo("Готово", msg)

    # ------------------------------------------------------------
    # Загрузка навигации
    # ------------------------------------------------------------
    def load_navigation(self):
        if not self.mw.nav_path.get():
            return
        self.mw.show_loading("Загрузка навигации...")
        self.mw.master.update()

        def task():
            try:
                data = process_navigation_folder(self.mw.nav_path.get())
                self.mw.nav_data = data
                self.mw.master.after(0, self._update_nav_preview, data)
            except Exception as e:
                self.mw.master.after(0, messagebox.showerror, "Ошибка", str(e))
            finally:
                self.mw.master.after(0, self.mw.hide_loading)

        threading.Thread(target=task, daemon=True).start()

    # ------------------------------------------------------------
    # Обновление после загрузки навигации
    # ------------------------------------------------------------
    def _update_nav_preview(self, data):
        total_lines = sum(t.count('\n') + 1 if t else 0 for t in data.values())

        # Сохраняем объединённый файл навигации в корень Результатов
        if self.mw.output_dir.get():
            combined_text = ""
            for date_str, content in data.items():
                combined_text += f"# Дата: {date_str}\n{content}\n"
            suffix = "V1" if self.mw.mode.get() == "with_v1" else ""
            nav_file = Path(self.mw.output_dir.get()) / f"navigation_{suffix}.txt"
            try:
                nav_file.write_text(combined_text, encoding='utf-8')
            except Exception as e:
                self.mw.errors.append(f"Не удалось сохранить навигацию: {e}")

        # Кэш координат для карты
        self.mw.nav_coords_cache = {}
        for date_str, text in data.items():
            try:
                coords = parse_navigation_text(text)
                points = list(coords.values())
                self.mw.nav_coords_cache[date_str] = points
            except:
                self.mw.nav_coords_cache[date_str] = []

        # Обновление мини-карты навигации
        if self.mw.nav_map_figure is not None:
            self.mw.nav_map_figure.clear()
            ax = self.mw.nav_map_figure.add_subplot(111)
            MapManager.draw_nav_track(ax, self.mw.nav_coords_cache)
            self.mw.nav_map_canvas.draw()

        msg = f"Навигация загружена. Дат: {len(data)}, всего строк: {total_lines}"
        self.mw._add_statistics(msg)
        messagebox.showinfo("Готово", msg)

    # ------------------------------------------------------------
    # Загрузка файла вариаций (только предпросмотр)
    # ------------------------------------------------------------
    def load_correction_preview(self, file_path):
        self.mw.show_loading("Чтение файла вариаций...")
        self.mw.master.update()

        def task():
            try:
                # Быстро получаем только имена листов
                xl = pd.ExcelFile(file_path, engine='openpyxl')
                sheets = xl.sheet_names
                self.mw.master.after(0, lambda: messagebox.showinfo(
                    "Вариации", f"Файл вариаций загружен.\nНайдено листов: {len(sheets)}"))
            except Exception as e:
                self.mw.master.after(0, messagebox.showerror, "Ошибка", f"Не удалось прочитать файл вариаций:\n{e}")
            finally:
                self.mw.master.after(0, self.mw.hide_loading)

        threading.Thread(target=task, daemon=True).start()