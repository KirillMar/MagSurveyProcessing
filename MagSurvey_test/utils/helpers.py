import os
import subprocess

def open_folder(path):
    """Открыть папку в проводнике ОС."""
    if path and os.path.exists(path):
        if os.name == 'nt':
            os.startfile(path)
        else:
            subprocess.run(['open', path])