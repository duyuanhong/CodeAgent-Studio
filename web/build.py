from pathlib import Path
import shutil

ROOT = Path(__file__).parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
VENDOR = ROOT / "vendor"

if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir(parents=True)
shutil.copytree(VENDOR, DIST / "vendor")
for name in ("index.html", "app.js", "styles.css"):
    shutil.copy2(SRC / name, DIST / name)
print(f"Built static Web IDE -> {DIST}")
