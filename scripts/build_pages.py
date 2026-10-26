"""Copy each project's web/ folder into dist/ for GitHub Pages."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
output = root / "dist"
shutil.rmtree(output, ignore_errors=True)
output.mkdir()
shutil.copy2(root / "index.html", output / "index.html")
(output / ".nojekyll").touch()

for project in sorted(path for path in root.iterdir() if (path / "web" / "index.html").is_file()):
    shutil.copytree(project / "web", output / project.name)
    print(f"Built {project.name}")
