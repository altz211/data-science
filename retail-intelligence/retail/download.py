import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from zipfile import ZipFile
from retail.paths import DATA

URL = 'https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip'


def download():
    folder = DATA / 'raw'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / 'online_retail_ii.zip'
    if not archive.exists():
        temporary = archive.with_suffix('.part')
        with urllib.request.urlopen(URL, timeout=120) as response, temporary.open('wb') as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        temporary.replace(archive)
    with ZipFile(archive) as files:
        name = next(name for name in files.namelist() if name.endswith('.xlsx'))
        target = folder / 'online_retail_II.xlsx'
        if not target.exists() or target.stat().st_size != files.getinfo(name).file_size:
            temporary = target.with_suffix('.part')
            temporary.write_bytes(files.read(name))
            temporary.replace(target)
    manifest = {'url': URL, 'downloaded_utc': datetime.now(timezone.utc).isoformat(),
                'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'license': 'CC BY 4.0', 'citation': 'Chen, D. (2012). Online Retail II. https://doi.org/10.24432/C5CG6D'}
    manifest_path = folder / 'source.json'
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(target)
    return target


if __name__ == '__main__':
    download()
