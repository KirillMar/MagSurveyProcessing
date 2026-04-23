from pathlib import Path
import shutil

# === НАСТРОЙКИ ===
root_folder = Path(r"M:\01_project\Экоскай-25 Певек\05_Геофизика\02_КР\Кириллу\Море")
output_root = Path(r"M:\01_project\Экоскай-25 Певек\05_Геофизика\02_КР\Кириллу\для проги")
mode = "with_v1"   # "with_v1" или "without_v1"
# =================

output_root.mkdir(exist_ok=True)

total_copied = 0

for day_folder in root_folder.iterdir():
    if not day_folder.is_dir():
        continue

    day_name = day_folder.name
    target_folder = output_root / day_name
    target_folder.mkdir(exist_ok=True)

    day_copied = 0

    for subfolder in day_folder.iterdir():
        if subfolder.is_dir():
            for csv_file in subfolder.glob("*.csv"):
                name = csv_file.name
                condition = ("V1" in name) if mode == "with_v1" else ("V1" not in name)
                if condition:
                    dest_file = target_folder / name
                    if dest_file.exists():
                        dest_file = target_folder / f"{csv_file.stem}_{subfolder.name}{csv_file.suffix}"
                    shutil.copy2(csv_file, dest_file)
                    day_copied += 1
                    break

    total_copied += day_copied
    print(f"День {day_name}: скопировано файлов {day_copied}")

print(f"\nВсего скопировано файлов: {total_copied}")
print(f"Файлы сохранены в: {output_root}")