import pandas as pd
from pathlib import Path

def normalize_time(t):
    s = str(t).strip()
    if ' ' in s:
        s = s.split(' ')[1]
    if len(s) >= 8:
        s = s[:8]
    return s

def read_correction_sheet(excel_path, sheet_name):
    """Читает лист вариаций, возвращает словарь {time_norm: var}."""
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"Не удалось прочитать лист '{sheet_name}': {e}")
    df.columns = df.columns.str.lower().str.strip()
    if 'time' not in df.columns:
        raise ValueError(f"В листе '{sheet_name}' нет столбца 'time'. Найдены: {list(df.columns)}")
    if 'var' not in df.columns:
        raise ValueError(f"В листе '{sheet_name}' нет столбца 'var'. Найдены: {list(df.columns)}")
    df['time_norm'] = df['time'].apply(normalize_time)
    var_dict = df.set_index('time_norm')['var'].to_dict()
    return var_dict

def apply_correction_to_df(df, var_dict):
    """Добавляет столбец 'var' и вычисляет 'dT' = field - var. Возвращает (df_result, matched_count)."""
    if 'utc_time' not in df.columns or 'field' not in df.columns:
        return df.copy(), 0
    df_copy = df.copy()
    df_copy['time_norm'] = df_copy['utc_time'].apply(normalize_time)
    df_copy['var'] = df_copy['time_norm'].map(var_dict)
    # Преобразуем field и var в числа, ошибки -> NaN
    df_copy['field'] = pd.to_numeric(df_copy['field'], errors='coerce')
    df_copy['var'] = pd.to_numeric(df_copy['var'], errors='coerce')
    df_copy['dT'] = df_copy['field'] - df_copy['var']
    matched = df_copy['var'].notna().sum()
    df_copy.drop(columns=['time_norm'], inplace=True)
    return df_copy, matched