import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path


def ask_overwrite_or_rename(output_dir: str, base_name: str, suffix: str) -> tuple:
    """
    Проверяет существование файла с именем `{base_name}_{suffix}.xlsx` в `output_dir`.
    Если файла нет — возвращает (True, base_name).
    Если файл есть — показывает диалог с тремя вариантами:
        - Да (перезаписать) -> (True, base_name)
        - Нет (сохранить под новым именем) -> (True, новое_base_name)
        - Отмена -> (False, None)
    Возвращает кортеж (продолжать_операцию, итоговое_базовое_имя_или_None).
    """
    filename = f"{base_name}_{suffix}.xlsx" if suffix else f"{base_name}.xlsx"
    path = Path(output_dir) / filename

    if not path.exists():
        return True, base_name

    # Создаём временное родительское окно для корректного отображения диалога
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    answer = messagebox.askyesnocancel(
        "Файл существует",
        f"Файл '{path.name}' уже существует.\n\n"
        "Да — перезаписать\n"
        "Нет — сохранить под другим именем\n"
        "Отмена — отменить процедуру",
        parent=root
    )

    if answer is None:  # Отмена
        root.destroy()
        return False, None

    if answer:  # Да — перезаписать
        root.destroy()
        return True, base_name

    # Нет — запрашиваем новое имя
    new_name = simpledialog.askstring(
        "Новое имя",
        "Введите новое базовое имя файла (без расширения):",
        parent=root
    )
    root.destroy()

    if not new_name:
        return False, None

    return True, new_name.strip()