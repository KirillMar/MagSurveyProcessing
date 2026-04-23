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