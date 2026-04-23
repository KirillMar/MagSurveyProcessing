from pathlib import Path
from collections import defaultdict

input_folder = r"C:\Users\shulpin.mslvl\Desktop\Навигация"
input_path = Path(input_folder)

# Папка для сохранения результатов
output_root = Path(r"C:\Users\shulpin.mslvl\Desktop\Навигация")
output_root.mkdir(exist_ok=True)

groups = defaultdict(list)
for txt_file in input_path.glob("*.txt"):
    date_prefix = txt_file.name[:6]   # первые 8 символов имени
    groups[date_prefix].append(txt_file)

for date_prefix, files in groups.items():
    files.sort()
    output_file = output_root / f"{date_prefix}_merge.txt"
    
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for i, fpath in enumerate(files):
            content = fpath.read_text(encoding='utf-8')
            out_f.write(content)
            if not content.endswith('\n'):
                out_f.write('\n')
            if i < len(files) - 1:
                out_f.write("\n" + "=" * 50 + "\n\n")

print("Merge complete!")