import pandas as pd

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

def read_correction_sheet_from_df(df, sheet_name=''):
    """
    Принимает DataFrame (уже прочитанный лист вариаций) и возвращает словарь {time_norm: var}.
    """
    df.columns = df.columns.str.lower().str.strip()
    if 'time' not in df.columns:
        raise ValueError(f"В листе '{sheet_name}' нет столбца 'time'. Найдены: {list(df.columns)}")
    if 'var' not in df.columns:
        raise ValueError(f"В листе '{sheet_name}' нет столбца 'var'. Найдены: {list(df.columns)}")
    df['time_norm'] = df['time'].apply(normalize_time)
    var_dict = df.set_index('time_norm')['var'].to_dict()
    return var_dict

def apply_correction_to_df(df, var_dict):
    """
    Добавляет столбец 'var' из словаря вариаций. Использует векторизованные операции.
    Возвращает (df_result, matched_count).
    """
    if 'utc_time' not in df.columns:
        return df.copy(), 0
    
    df_result = df.copy()
    # Векторизованная нормализация времени
    s = df_result['utc_time'].astype(str).str.strip()
    s = s.str.split(' ').str[-1]        # берём часть после последнего пробела (если есть дата)
    s = s.str.split('.').str[0]         # убираем миллисекунды
    s = s.str[:8]                       # оставляем до 8 символов
    df_result['time_norm'] = s
    
    # Сопоставление с var_dict через Series.map (быстро)
    var_series = pd.Series(var_dict)
    df_result['var'] = df_result['time_norm'].map(var_series)
    df_result['var'] = pd.to_numeric(df_result['var'], errors='coerce')
    
    # Приводим 'field' к числу, если он ещё не числовой
    if 'field' in df_result.columns:
        df_result['field'] = pd.to_numeric(df_result['field'], errors='coerce')
    
    matched = df_result['var'].notna().sum()
    
    # Убираем вспомогательный столбец
    df_result.drop(columns=['time_norm'], inplace=True)
    
    return df_result, matched