from pathlib import Path
import pandas as pd
import numpy as np
import re
from pathlib import Path
from collections import defaultdict


def process_navigation_folder(folder):
    nav_path = Path(folder)
    groups = defaultdict(list)
    for txt_file in nav_path.glob("*.txt"):
        if len(txt_file.name) >= 8:
            date_prefix = txt_file.name[:8]
            groups[date_prefix].append(txt_file)
    
    merged = {}
    for date_str, files in groups.items():
        files.sort()
        combined = ""
        for i, fpath in enumerate(files):
            try:
                content = fpath.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    content = fpath.read_text(encoding='windows-1251')
                except:
                    content = f"[Ошибка чтения: {fpath.name}]"
            combined += content
            if not content.endswith('\n'):
                combined += '\n'
            if i < len(files) - 1:
                combined += "\n" + "=" * 50 + "\n\n"
        merged[date_str] = combined
    return merged


def process_survey_folder(root_folder, mode, required_columns=None, progress_callback=None):
    """
    Обрабатывает папку с данными съёмки.
    Поддерживаются подпапки с именами YYMMDD (старый формат) или DDMMYYHHMM (новый).
    Все CSV внутри одной подпапки объединяются в один DataFrame.
    Результат – словарь {имя_папки: DataFrame}.
    """
    if required_columns is None:
        required_columns = ['utc_date', 'utc_time', 'lat', 'lon', 'field', 'depth']

    root_path = Path(root_folder)
    result = {}
    stats = {'sheets': 0, 'files': 0, 'errors': []}

    # Регулярки для имён папок
    old_pattern = re.compile(r'^\d{6}$')      # YYMMDD
    new_pattern = re.compile(r'^\d{10}$')     # DDMMYYHHMM

    all_folders = sorted([d for d in root_path.iterdir() if d.is_dir()])
    total_folders = len(all_folders)

    for idx, folder in enumerate(all_folders):
        name = folder.name
        if not (old_pattern.match(name) or new_pattern.match(name)):
            continue

        if progress_callback:
            progress_callback(f"Обработка папки {name} ({idx+1}/{total_folders})")

        csv_files = list(folder.glob("**/*.csv"))

        # Фильтр по режиму (V1 / без V1)
        if mode == "with_v1":
            csv_files = [f for f in csv_files if "V1" in f.name]
        elif mode == "without_v1":
            csv_files = [f for f in csv_files if "V1" not in f.name]

        if not csv_files:
            continue

        dfs = []
        for csv_path in csv_files:
            try:
                df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig',
                                 on_bad_lines='skip', index_col=False)
            except Exception as e:
                stats['errors'].append(f"{name}/{csv_path.name}: ошибка чтения - {e}")
                continue

            if df.empty:
                stats['errors'].append(f"{name}/{csv_path.name}: файл пуст")
                continue

            df.columns = df.columns.str.strip().str.lower()

            # Удаление дублирующейся строки заголовка, если она есть
            if len(df) > 0:
                first_row = df.iloc[0].astype(str).str.strip().str.lower()
                if first_row.tolist() == df.columns.tolist():
                    df = df.iloc[1:].reset_index(drop=True)

            # Обработка даты/времени
            if not ('utc_date' in df.columns and 'utc_time' in df.columns):
                if 'datetime' in df.columns:
                    dt_series = df['datetime'].fillna('').astype(str)
                    split_data = dt_series.str.split(' ', expand=True)
                    if split_data.shape[1] >= 2:
                        df['utc_date'] = split_data[0]
                        df['utc_time'] = split_data[1].str.split('.').str[0]
                    else:
                        stats['errors'].append(f"{name}/{csv_path.name}: не удалось разделить datetime")
                        continue
                else:
                    stats['errors'].append(f"{name}/{csv_path.name}: нет datetime и отдельных utc_date/utc_time")
                    continue

            # Оставляем только нужные столбцы
            available = [c for c in required_columns if c in df.columns]
            if not available:
                stats['errors'].append(f"{name}/{csv_path.name}: нет ни одного целевого столбца")
                continue

            df = df[available].copy()
            df.replace({np.nan: ''}, inplace=True)
            dfs.append(df)
            stats['files'] += 1

        if dfs:
            merged = pd.concat(dfs, ignore_index=True)
            # Имя листа = имя папки
            sheet_name = name
            result[sheet_name] = merged
            stats['sheets'] += 1

    return result, stats