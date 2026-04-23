from pathlib import Path
import pandas as pd
import numpy as np

def process_survey_folder(root_folder, mode, required_columns=None, progress_callback=None):
    if required_columns is None:
        required_columns = ['utc_date', 'utc_time', 'lat', 'lon', 'field', 'depth']
    
    root_path = Path(root_folder)
    result = {}
    stats = {'days': 0, 'files': 0, 'errors': []}
    
    days = [d for d in root_path.iterdir() if d.is_dir()]
    total_days = len(days)
    
    for day_idx, day_folder in enumerate(days):
        day_name = day_folder.name
        sheets = {}
        
        if progress_callback:
            progress_callback(f"День {day_name} ({day_idx+1}/{total_days})")
        
        for csv_path in day_folder.glob("**/*.csv"):
            name = csv_path.name
            # Строгое сравнение без приведения регистра
            if mode == "with_v1" and "V1" not in name:
                continue
            if mode == "without_v1" and "V1" in name:
                continue
            
            try:
                df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig',
                                 on_bad_lines='skip', index_col=False)
            except Exception as e:
                stats['errors'].append(f"{day_name}/{name}: ошибка чтения - {e}")
                continue
            
            if df.empty:
                stats['errors'].append(f"{day_name}/{name}: файл пуст")
                continue
            
            df.columns = df.columns.str.strip().str.lower()
            
            # Удаление дубликата строки заголовков
            if len(df) > 0:
                first_row = df.iloc[0].astype(str).str.strip().str.lower()
                if first_row.tolist() == df.columns.tolist():
                    df = df.iloc[1:].reset_index(drop=True)
            
            # Обработка даты/времени
            has_utc_date = 'utc_date' in df.columns
            has_utc_time = 'utc_time' in df.columns
            
            if not (has_utc_date and has_utc_time):
                if 'datetime' in df.columns:
                    dt_series = df['datetime'].fillna('').astype(str)
                    split_data = dt_series.str.split(' ', expand=True)
                    if split_data.shape[1] >= 2:
                        df['utc_date'] = split_data[0]
                        df['utc_time'] = split_data[1].str.split('.').str[0]
                    else:
                        stats['errors'].append(f"{day_name}/{name}: не удалось разделить datetime")
                        continue
                else:
                    stats['errors'].append(f"{day_name}/{name}: нет datetime и отдельных utc_date/utc_time")
                    continue
            
            # Оставляем нужные столбцы
            available = [c for c in required_columns if c in df.columns]
            if not available:
                stats['errors'].append(f"{day_name}/{name}: нет ни одного целевого столбца")
                continue
            
            result_df = df[available].copy()
            result_df.replace({np.nan: ''}, inplace=True)
            
            sheet_name = csv_path.stem[:31]
            if sheet_name in sheets:
                sheet_name = f"{csv_path.stem[:20]}_{csv_path.parent.name}"[:31]
            sheets[sheet_name] = result_df
            stats['files'] += 1
        
        if sheets:
            result[day_name] = sheets
            stats['days'] += 1
    
    return result, stats