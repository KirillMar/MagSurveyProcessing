import tkinter as tk
from tkinter import filedialog
from pathlib import Path

class PathSelectors:
    def __init__(self, main_window):
        self.mw = main_window

    def _ensure_output_dir(self, base_path):
        p = Path(base_path)
        if p.name.lower() == 'результаты':
            self.mw.output_dir.set(str(p))
        else:
            self.mw.output_dir.set(str(p / 'Результаты'))

    def browse_output(self):
        path = filedialog.askdirectory(title="Выберите папку для сохранения результатов")
        if path:
            self._ensure_output_dir(path)

    def browse_survey(self):
        if self.mw.mode.get() == "excel":
            path = filedialog.askopenfilename(
                title="Выберите Excel-файл съёмки",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if path:
                self.mw.survey_path.set(path)
                parent = Path(path).parent
                if not self.mw.output_dir.get():
                    self._ensure_output_dir(parent)
                self.mw.data_loaders.load_survey()
        else:
            path = filedialog.askdirectory(title="Данные съёмки")
            if path:
                self.mw.survey_path.set(path)
                parent = Path(path).parent
                if not self.mw.output_dir.get():
                    self._ensure_output_dir(parent)
                self.mw.data_loaders.load_survey()

    def browse_navigation(self):
        path = filedialog.askdirectory(title="Данные навигации")
        if path:
            self.mw.nav_path.set(path)
            self.mw.data_loaders.load_navigation()

    def browse_correction(self):
        path = filedialog.askopenfilename(title="Файл вариаций",
                                          filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")])
        if path:
            self.mw.correction_file.set(path)
            self.mw.data_loaders.load_correction_preview(path)