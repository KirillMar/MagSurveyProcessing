import pandas as pd
from pathlib import Path
from logic.coordinate_merger import parse_navigation_text, add_coordinates_to_df
from logic.correction_processor import read_correction_sheet_from_df, apply_correction_to_df

def save_survey_excels(survey_data, output_dir, mode, nav_data=None, keep_only_matched=False):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stats = {'total_rows': 0, 'matched_rows': 0, 'removed_rows': 0, 'sheets_removed': 0}

    suffix = 'V1' if mode == 'with_v1' else ''
    if nav_data is None:
        filename = f"survey_{suffix}_source.xlsx"
    else:
        filename = f"survey_{suffix}_coords.xlsx"
    save_path = out_path / filename

    sheets_to_save = {}
    for sheet_name, df in survey_data.items():
        coord_dict = None
        if nav_data:
            if len(sheet_name) >= 6:
                date_prefix = sheet_name[:6]              # YYMMDD
                year = "20" + date_prefix[0:2]            # 20YY
                month = date_prefix[2:4]                  # MM
                day = date_prefix[4:6]                    # DD
                nav_key_full = year + month + day         # YYYYMMDD
                nav_text = nav_data.get(nav_key_full) or nav_data.get(date_prefix)
            else:
                nav_text = nav_data.get(sheet_name)
            if nav_text:
                try:
                    coord_dict = parse_navigation_text(nav_text)
                except Exception as e:
                    print(f"Ошибка парсинга навигации для {sheet_name}: {e}")

        df_result = df.copy()
        if coord_dict is not None:
            df_result = add_coordinates_to_df(df_result, coord_dict)
            matched = df_result['X'].notna().sum()
        else:
            matched = 0

        total = len(df_result)
        stats['total_rows'] += total
        stats['matched_rows'] += matched

        if keep_only_matched and coord_dict is not None:
            before = len(df_result)
            df_result = df_result.dropna(subset=['X', 'Y'], how='all')
            after = len(df_result)
            stats['removed_rows'] += before - after
            if after == 0:
                stats['sheets_removed'] += 1
                continue

        sheets_to_save[sheet_name] = df_result

    if sheets_to_save:
        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            for sh_name, sh_df in sheets_to_save.items():
                sh_df.to_excel(writer, sheet_name=sh_name, index=False)

    return stats


def save_survey_with_corrections(survey_data, output_dir, mode, correction_file, keep_only_matched=False):
    from pathlib import Path
    import pandas as pd
    from logic.correction_processor import read_correction_sheet_from_df, apply_correction_to_df

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stats = {'total_rows': 0, 'matched_rows': 0, 'removed_rows': 0, 'sheets_removed': 0}

    suffix = 'V1' if mode == 'with_v1' else ''
    filename = f"survey_{suffix}_corrected.xlsx"
    save_path = out_path / filename

    try:
        xl_corr = pd.ExcelFile(correction_file)
        available_sheets = xl_corr.sheet_names
    except Exception as e:
        raise ValueError(f"Ошибка открытия файла вариаций: {e}")

    sheets_to_save = {}
    correction_cache = {}   # dict для кеширования

    for sheet_name, df in survey_data.items():
        # Определяем лист вариаций
        if len(sheet_name) >= 6:
            date_prefix = sheet_name[:6]          # YYMMDD
            year_s = "20" + date_prefix[0:2]
            month_s = date_prefix[2:4]
            day_s = date_prefix[4:6]
            corr_sheet = f"{int(day_s):02d}.{int(month_s):02d}.{year_s}"
        else:
            corr_sheet = sheet_name

        if corr_sheet not in available_sheets:
            print(f"Для листа {sheet_name} лист вариаций '{corr_sheet}' не найден.")
            continue

        # Получаем словарь вариаций (из кеша или читаем)
        if corr_sheet not in correction_cache:
            try:
                corr_df = xl_corr.parse(corr_sheet)
                var_dict = read_correction_sheet_from_df(corr_df, corr_sheet)
                correction_cache[corr_sheet] = var_dict
            except Exception as e:
                print(f"Ошибка чтения листа вариаций '{corr_sheet}': {e}")
                continue
        else:
            var_dict = correction_cache[corr_sheet]

        df_result, matched = apply_correction_to_df(df, var_dict)
        stats['total_rows'] += len(df_result)
        stats['matched_rows'] += matched

        if keep_only_matched:
            before = len(df_result)
            df_result = df_result.dropna(subset=['var'])
            if 'X' in df_result.columns and 'Y' in df_result.columns:
                df_result = df_result.dropna(subset=['X', 'Y'])
            stats['removed_rows'] += before - len(df_result)
            if len(df_result) == 0:
                stats['sheets_removed'] += 1
                continue

        sheets_to_save[sheet_name] = df_result

    if sheets_to_save:
        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            for sh_name, sh_df in sheets_to_save.items():
                sh_df.to_excel(writer, sheet_name=sh_name, index=False)

    return stats


def save_filtered_survey(survey_data, output_dir, mode):
    """
    Удаляет строки без вариации (var) и без координат (X, Y), сохраняет результат.
    Возвращает статистику с ключами: total_rows, after_rows, removed_rows, sheets_removed.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    suffix = 'V1' if mode == 'with_v1' else ''
    filename = f"survey_{suffix}_filtered.xlsx"
    save_path = out_path / filename

    sheets_to_save = {}
    stats = {
        'total_rows': 0,
        'after_rows': 0,
        'removed_rows': 0,
        'sheets_removed': 0
    }

    for sheet_name, df in survey_data.items():
        total = len(df)
        stats['total_rows'] += total

        df_result = df.copy()

        # Удаляем строки без var, если столбец есть
        if 'var' in df_result.columns:
            df_result = df_result.dropna(subset=['var'])

        # Удаляем строки без координат, если столбцы есть
        if 'X' in df_result.columns and 'Y' in df_result.columns:
            df_result = df_result.dropna(subset=['X', 'Y'])

        removed = total - len(df_result)
        stats['removed_rows'] += removed
        stats['after_rows'] += len(df_result)

        if len(df_result) == 0:
            stats['sheets_removed'] += 1
            continue

        sheets_to_save[sheet_name] = df_result

    if sheets_to_save:
        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            for sh_name, sh_df in sheets_to_save.items():
                sh_df.to_excel(writer, sheet_name=sh_name, index=False)

    return stats