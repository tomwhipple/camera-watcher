from pathlib import Path
from PIL import Image

from .connection import application_config

__all__ = ['task_write_image']

def task_write_image(img, img_relpath):
    basedir = Path(application_config('system','BASE_DIR'))
    fullpath = str(basedir / img_relpath)
    img.save(fullpath, quality=85)
    print(f"wrote {fullpath}")