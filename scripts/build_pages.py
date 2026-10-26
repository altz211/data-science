from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
output = root / 'dist'
if output.exists():
    shutil.rmtree(output)
output.mkdir()
shutil.copy2(root / 'index.html', output / 'index.html')
(output / '.nojekyll').touch()
for project in sorted(root.iterdir()):
    web = project / 'web'
    if project.is_dir() and (web / 'index.html').is_file():
        shutil.copytree(web, output / project.name)
        print(f'Built {project.name}')
