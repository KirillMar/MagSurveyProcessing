import pandas as pd
from io import StringIO

def normalize_time(t):
    s = str(t).strip()
    if ' ' in s:
        s = s.split(' ')[1]
    if len(s) >= 8:
        s = s[:8]
    return s

def parse_navigation_text(text):
    lines = text.strip().splitlines()
    if not lines:
        return {}
    # Определяем разделитель
    sample = lines[0]
    if '\t' in sample:
        sep = '\t'
    elif ';' in sample:
        sep = ';'
    elif ',' in sample:
        sep = ','
    else:
        sep = r'\s+'
    df = pd.read_csv(StringIO(text), sep=sep, engine='python')
    df.columns = df.columns.str.lower().str.strip()
    # Поиск столбцов времени, X, Y
    time_col = next((c for c in df.columns if 'time' in c or 'время' in c), df.columns[0])
    x_col = next((c for c in df.columns if c in ('x','coord_x','lon','longitude')), df.columns[2])
    y_col = next((c for c in df.columns if c in ('y','coord_y','lat','latitude')), df.columns[1])
    df['time_norm'] = df[time_col].apply(normalize_time)
    coord_dict = {row['time_norm']: (row[x_col], row[y_col]) for _, row in df.iterrows()}
    return coord_dict

def add_coordinates_to_df(df, coord_dict):
    if 'utc_time' not in df.columns:
        return df.copy()
    df_copy = df.copy()
    df_copy['time_norm'] = df_copy['utc_time'].apply(normalize_time)
    df_copy['X'] = df_copy['time_norm'].map(lambda t: coord_dict.get(t, (None, None))[0])
    df_copy['Y'] = df_copy['time_norm'].map(lambda t: coord_dict.get(t, (None, None))[1])
    df_copy.drop(columns=['time_norm'], inplace=True)
    return df_copy