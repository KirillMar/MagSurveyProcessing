import pandas as pd
import numpy as np
import pyIGRF14 as pyIGRF


def read_correction_sheet_from_df(df, sheet_name=None):
    df = df.copy()
    
    # Собираем datetime
    df['Date'] = df['Date'].astype(str).str.strip()
    df['Time'] = df['Time'].astype(str).str.strip()

    # Исправляем кривые строки, где Time содержит "1900-01-01 HH:MM:SS"
    mask_has_space = df['Time'].str.contains(' ')
    if mask_has_space.any():
        df.loc[mask_has_space, 'Time'] = df.loc[mask_has_space, 'Time'].str.split().str[1]

    df['datetime'] = pd.to_datetime(
        df['Date'] + ' ' + df['Time'],
        format='%Y-%m-%d %H:%M:%S',
        errors='coerce'
    )
    
    # Удаляем строки, где не распозналось время
    df = df.dropna(subset=['datetime'])
    
    # Числовые столбцы — заменяем запятые на точки
    for col in ['Lat', 'Lon', 'Field']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # ⚠️ НЕ удаляем строки без Lat/Lon – они нам нужны для var
    # Удаляем только строки без Field (основного измерения)
    df = df.dropna(subset=['Field'])
    
    if len(df) == 0:
        raise ValueError("Нет данных после фильтрации (Field отсутствует)")
    
    # Средние координаты из первых 5 записей, где Lat/Lon присутствуют
    first_n = 5
    valid_coords = df[['Lat', 'Lon']].dropna()
    if len(valid_coords) == 0:
        raise ValueError("Нет ни одной строки с Lat/Lon для расчёта нормального поля")
    avg_lat = float(valid_coords['Lat'].iloc[:first_n].mean())
    avg_lon = float(valid_coords['Lon'].iloc[:first_n].mean())
    
    dt0 = df['datetime'].iloc[0]
    year = dt0.year + (dt0.timetuple().tm_yday - 1) / 365.25

    alt_km = 0.0
    D, I, H, X, Y, Z, F = pyIGRF.igrf_value(avg_lat, avg_lon, alt_km, year)

    normal_field = F
    
    df['var'] = df['Field'] - normal_field
    df.attrs['normal_field'] = normal_field
    
    return df[['datetime', 'var']]


def apply_correction_to_df(survey_df, var_df):
    survey_df = survey_df.copy()
    
    time_col = date_col = None
    for col in survey_df.columns:
        col_lower = col.lower()
        if col_lower in ('time', 'время', 'utc_time'):
            time_col = col
        elif col_lower in ('date', 'дата', 'utc_date'):
            date_col = col

    if time_col is None:
        print("❌ Не найден столбец времени в листе")
        survey_df['var'] = np.nan
        return survey_df, 0

    if date_col:
        date_str = survey_df[date_col].astype(str).str.strip()
    else:
        date_str = ''
    time_str = survey_df[time_col].astype(str).str.strip()

    # Парсинг времени
    formats_to_try = [
        '%d.%m.%y %H:%M:%S',
        '%d.%m.%Y %H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        None,
    ]
    survey_times = None
    for fmt in formats_to_try:
        try:
            if fmt is None:
                t = pd.to_datetime(date_str + ' ' + time_str, errors='coerce', dayfirst=True)
            else:
                t = pd.to_datetime(date_str + ' ' + time_str, format=fmt, errors='coerce')
            if t.notna().sum() > 0:
                survey_times = t
                break
        except:
            continue

    if survey_times is None or survey_times.notna().sum() == 0:
        print("❌ Не удалось распарсить время ни в одном формате")
        survey_df['var'] = np.nan
        return survey_df, 0

    survey_df['_date'] = survey_times.dt.date
    survey_dates = sorted(survey_df['_date'].dropna().unique())
    var_dates = sorted(var_df['datetime'].dt.date.unique())

    # Готовим var_df с колонкой даты
    var_df = var_df.copy()
    var_df['_date'] = var_df['datetime'].dt.date

    matched_total = 0
    survey_vars = [np.nan] * len(survey_df)

    for date_val, group in survey_df.groupby('_date'):
        if pd.isna(date_val):
            continue
        var_for_date = var_df[var_df['_date'] == date_val]
        if var_for_date.empty:
            continue

        var_times = var_for_date['datetime'].values.astype('datetime64[ns]')
        var_values = var_for_date['var'].values

                # ---------- ОТЛАДКА ВРЕМЕНИ ----------
        if matched_total == 0:  # печатаем только если ещё нет совпадений
            sample_survey_times = [survey_times.loc[i] for i in group.index[:3]]
            sample_var_times = var_for_date['datetime'].iloc[:3].tolist()
        # ------------------------------------

        for idx, row in group.iterrows():
            st = survey_times.loc[idx]
            if pd.isna(st):
                continue
            st64 = np.datetime64(st.to_datetime64())
            diffs = np.abs(var_times - st64)
            min_diff = diffs.min()
            if min_diff <= np.timedelta64(3, 's'):   # допуск 60 секунд
                min_idx = diffs.argmin()
                survey_vars[idx] = var_values[min_idx]
                matched_total += 1

    survey_df['var'] = survey_vars
    survey_df.drop(columns=['_date'], inplace=True, errors='ignore')

    return survey_df, matched_total