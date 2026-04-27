import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import pandas as pd
from tkinter import messagebox
from logic.excel_writer import save_survey_excels, save_survey_with_corrections, save_filtered_survey
from logic.coordinate_merger import parse_navigation_text, add_coordinates_to_df
import tkinter.simpledialog as simpledialog

class DataProcessor:
    def __init__(self, main_window):
        self.mw = main_window

    # ---------- проверка перезаписи ----------
    def _check_overwrite(self, base_name, suffix):
        filename = f"{base_name}_{suffix}.xlsx" if suffix else f"{base_name}.xlsx"
        path = Path(self.mw.output_dir.get()) / filename
        if not path.exists():
            return True, base_name
        answer = messagebox.askyesnocancel(
            "Файл существует",
            f"Файл '{path.name}' уже существует.\nПерезаписать его?\n\n"
            "Да - перезаписать\nНет - сохранить под другим именем\nОтмена - отменить процедуру"
        )
        if answer is None:
            return False, None
        elif answer:
            return True, base_name
        else:
            new_name = simpledialog.askstring("Новое имя", "Введите новое базовое имя файла (без расширения):")
            if not new_name:
                return False, None
            return True, new_name

    # ---------- Присвоение координат ----------
    def process_with_coordinates(self):
        if not self.mw.survey_data:
            messagebox.showwarning("Предупреждение", "Сначала загрузите данные съёмки")
            return
        if not self.mw.nav_data:
            messagebox.showwarning("Предупреждение", "Сначала загрузите данные навигации")
            return
        if not self.mw.output_dir.get():
            messagebox.showwarning("Предупреждение", "Выберите папку для сохранения")
            return
        if self.mw._has_coordinates():
            if not messagebox.askyesno("Навигационные данные уже присутствуют",
                                       "В файле уже есть столбцы X и Y.\nПерезаписать их? (предыдущие значения будут потеряны)"):
                return
        base = self.mw._get_base_name()
        suffix = f"{'V1' if self.mw.mode.get() == 'with_v1' else ''}_coords"
        ok, new_base = self._check_overwrite(base, suffix)
        if not ok:
            return
        self.custom_base_name = new_base

        self.mw.show_loading("Присвоение координат и удаление пустых строк...")
        self.mw._cache_original()
        self.mw.master.after(100, lambda: threading.Thread(target=self._coord_task, daemon=True).start())

    def _coord_task(self):
        try:
            coord_folder = Path(self.mw.output_dir.get())
            if self.mw.survey_data_original is None:
                self.mw._cache_original()

            base = self.custom_base_name or self.mw._get_base_name()
            self.custom_base_name = None

            stats_coord = save_survey_excels(
                self.mw.survey_data, str(coord_folder), self.mw.mode.get(),
                nav_data=self.mw.nav_data, keep_only_matched=False,
                base_name=base
            )
            # присвоение координат
            nav_cache = {}
            for sheet_name, df in list(self.mw.survey_data.items()):
                nav_text = self.mw._get_nav_text(sheet_name)
                if nav_text:
                    if nav_text not in nav_cache:
                        try:
                            nav_cache[nav_text] = parse_navigation_text(nav_text)
                        except Exception as e:
                            print(f"Ошибка парсинга: {e}")
                            continue
                    coord_dict = nav_cache.get(nav_text)
                    if coord_dict:
                        self.mw.survey_data[sheet_name] = add_coordinates_to_df(df, coord_dict)

            stats_filtered, _ = save_filtered_survey(
                self.mw.survey_data, str(coord_folder), self.mw.mode.get(),
                base_name=base
            )
            self.mw.coordinates_assigned = True

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
            self.mw._add_statistics(msg)
            self.mw.master.after(0, lambda: self.mw.correct_btn.config(state=tk.NORMAL))
            self.mw.master.after(0, self.mw.mini_maps.update_nav_map)
            self.mw.master.after(0, lambda: messagebox.showinfo("Готово", msg))
        except Exception as e:
            self.mw.master.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        finally:
            self.mw.master.after(0, self.mw.hide_loading)

    # ---------- Ввод поправок ----------
    def process_corrections(self):
        if not self.mw.survey_data:
            messagebox.showwarning("Предупреждение", "Сначала загрузите данные съёмки")
            return
        if not self.mw.correction_file.get():
            messagebox.showwarning("Предупреждение", "Выберите файл вариаций")
            return
        if not self.mw.output_dir.get():
            messagebox.showwarning("Предупреждение", "Выберите папку для сохранения")
            return
        # предупреждение о существующем var
        if any('var' in df.columns for df in self.mw.survey_data.values()):
            if not messagebox.askyesno("Внимание", "В данных уже есть столбец 'var'. Перезаписать его?"):
                return
        base = self.mw._get_base_name()
        suffix = f"{'V1' if self.mw.mode.get() == 'with_v1' else ''}_corrected"
        ok, new_base = self._check_overwrite(base, suffix)
        if not ok:
            return
        self.custom_base_name = new_base

        self.mw.show_loading("Ввод поправок...")
        self.mw.master.after(100, lambda: threading.Thread(target=self._corr_task, daemon=True).start())

    def _corr_task(self):
        try:
            corr_folder = Path(self.mw.output_dir.get())
            base = self.custom_base_name or self.mw._get_base_name()
            self.custom_base_name = None

            filtered_file = corr_folder / f"{self.mw._get_base_name()}_{'V1' if self.mw.mode.get() == 'with_v1' else ''}_filtered.xlsx"
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
                filtered_data = self.mw.survey_data

            if self.mw.var_df is None or self.mw.var_df.empty:
                raise ValueError("Сначала загрузите файл вариаций")

            stats_filtered, corrected_data = save_survey_with_corrections(
                filtered_data,
                str(corr_folder),
                self.mw.mode.get(),
                self.mw.var_df,
                keep_only_matched=True,
                base_name=base
            )
            self.mw.survey_data_corrected = corrected_data
            self.mw.survey_data = corrected_data
                
            msg = (
                f"Поправки применены.\n"
                f"Всего строк: {stats_filtered['total_rows']}\n"
                f"Строк с вариацией: {stats_filtered['matched_rows']}\n"
                f"Удалено строк без вариации: {stats_filtered.get('removed_rows', 0)}\n"
                f"Удалено пустых листов: {stats_filtered.get('sheets_removed', 0)}\n"
            )
            self.mw._add_statistics(msg)
            self.mw.master.after(0, self.mw.mini_maps.update_nav_map)
            self.mw.master.after(0, lambda: messagebox.showinfo("Готово", msg))
        except Exception as e:
            self.mw.master.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        finally:
            self.mw.master.after(0, self.mw.hide_loading)