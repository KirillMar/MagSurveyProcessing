import re
from pathlib import Path

def rename_files(folder_path: str):
    """
    Переименовывает файлы вида DDMMYYHHMM_44n.txt в YYMMDD_HHMM00 - MM1 - 0001.txt
    """
    folder = Path(folder_path)
    if not folder.exists():
        print(f"❌ Папка '{folder_path}' не найдена.")
        return

    pattern = re.compile(r"(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})_44n\.txt$")
    renamed_count = 0

    for file_path in folder.iterdir():
        if not file_path.is_file():
            continue
        match = pattern.match(file_path.name)
        if not match:
            continue

        day, month, year, hour, minute = match.groups()
        new_name = f"{year}{month}{day}_{hour}{minute}00 - MM1 - 0001.txt"
        new_path = file_path.with_name(new_name)

        if new_path.exists():
            print(f"⚠️ Файл '{new_name}' уже существует, пропускаем '{file_path.name}'")
            continue

        file_path.rename(new_path)
        print(f"✅ {file_path.name} -> {new_name}")
        renamed_count += 1

    print(f"\n🎉 Готово! Переименовано файлов: {renamed_count}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = input("Введите путь к папке: ").strip().strip('"')
    rename_files(folder)