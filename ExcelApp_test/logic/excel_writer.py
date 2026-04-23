import pandas as pd
from pathlib import Path
from logic.coordinate_merger import parse_navigation_text, add_coordinates_to_df
from logic.correction_processor import read_correction_sheet, apply_correction_to_df

def save_survey_excels(survey_data, output_dir, mode, nav_data=None, keep_only_matched=False):
    """
    Сохраняет Excel-файлы с данными съёмки.
    Если nav_data передано, добавляет координаты X, Y.
    Если nav_data не передано, координаты НЕ добавляются (исходные файлы).
    keep_only_matched: если True, сохраняются только строки с координатами (при nav_data).
    Возвращает статистику.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stats = {'total_rows': 0, 'matched_rows': 0, 'removed_rows': 0, 'sheets_removed': 0}

    for day_name, sheets in survey_data.items():
        coord_dict = None
        if nav_data:
            # Преобразование дня в ключ навигации (YYYYMMDD)
            if len(day_name) == 6:
                year = "20" + day_name[4:6]
                nav_key = year + day_name[2:4] + day_name[0:2]
            else:
                nav_key = day_name
            nav_text = nav_data.get(nav_key)
            if nav_text:
                try:
                    coord_dict = parse_navigation_text(nav_text)
                except Exception as e:
                    print(f"Ошибка навигации {day_name}: {e}")

        sheets_to_save = {}
        day_total = 0
        day_matched = 0

        for sheet_name, df in sheets.items():
            df_result = df.copy()
            if coord_dict is not None:
                df_result = add_coordinates_to_df(df_result, coord_dict)
                matched = df_result['X'].notna().sum()
                day_matched += matched
            else:
                # Координаты не добавляются, столбцов X/Y нет
                matched = 0
            total = len(df_result)
            day_total += total

            if keep_only_matched and coord_dict is not None:
                before = len(df_result)
                df_result = df_result.dropna(subset=['X', 'Y'], how='all')
                after = len(df_result)
                removed = before - after
                stats['removed_rows'] += removed
                if after == 0:
                    stats['sheets_removed'] += 1
                    continue
            sheets_to_save[sheet_name] = df_result

        stats['total_rows'] += day_total
        stats['matched_rows'] += day_matched

        if not sheets_to_save:
            continue

        suffix = 'V1' if mode == 'with_v1' else ''
        excel_name = f"{day_name}{suffix}_merged.xlsx"
        save_path = out_path / excel_name
        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            for sh_name, sh_df in sheets_to_save.items():
                sh_df.to_excel(writer, sheet_name=sh_name, index=False)

    return stats

def save_survey_with_corrections(survey_data, output_dir, mode, correction_file, keep_only_matched=False):
    """
    Сохраняет Excel-файлы с применёнными поправками (var, dT).
    Для каждого дня ищет соответствующий лист в файле вариаций.
    keep_only_matched: если True, сохраняются только строки с непустым var.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stats = {'total_rows': 0, 'matched_rows': 0, 'removed_rows': 0, 'sheets_removed': 0}

    # Открываем файл вариаций для получения списка листов
    try:
        xl_corr = pd.ExcelFile(correction_file)
        available_sheets = xl_corr.sheet_names
    except Exception as e:
        raise ValueError(f"Ошибка открытия файла вариаций: {e}")

    for day_name, sheets in survey_data.items():
        corr_sheet = None
        if len(day_name) == 6:  # DDMMYY
            day = day_name[0:2]
            month = day_name[2:4]
            year = "20" + day_name[4:6]
            corr_sheet = f"{int(day):02d}.{int(month):02d}.{year}"
        else:
            corr_sheet = day_name

        if corr_sheet not in available_sheets:
            print(f"Для дня {day_name} лист '{corr_sheet}' не найден. Доступны: {available_sheets}")
            continue

        try:
            var_dict = read_correction_sheet(correction_file, corr_sheet)
        except Exception as e:
            print(f"Ошибка чтения листа '{corr_sheet}': {e}")
            continue

        sheets_to_save = {}
        day_total = 0
        day_matched = 0

        for sheet_name, df in sheets.items():
            df_result, matched = apply_correction_to_df(df, var_dict)
            total = len(df_result)
            day_total += total
            day_matched += matched

            if keep_only_matched:
                before = len(df_result)
                # Удаляем строки без вариации
                df_result = df_result.dropna(subset=['var'])
                # Если есть столбцы координат, удаляем строки без координат
                if 'X' in df_result.columns and 'Y' in df_result.columns:
                    df_result = df_result.dropna(subset=['X', 'Y'])
                after = len(df_result)
                removed = before - after
                stats['removed_rows'] += removed
                if after == 0:
                    stats['sheets_removed'] += 1
                    continue
            sheets_to_save[sheet_name] = df_result

        stats['total_rows'] += day_total
        stats['matched_rows'] += day_matched

        if not sheets_to_save:
            continue

        suffix = 'V1' if mode == 'with_v1' else ''
        excel_name = f"{day_name}{suffix}_cor.xlsx"
        save_path = out_path / excel_name
        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            for sh_name, sh_df in sheets_to_save.items():
                sh_df.to_excel(writer, sheet_name=sh_name, index=False)

    return stats