from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_release_script_present():
    assert (ROOT / 'scripts' / 'release_check.py').exists()


def test_version_files_aligned():
    version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()
    meta = json.loads((ROOT / 'software_metadata.json').read_text(encoding='utf-8'))
    main = (ROOT / 'main.py').read_text(encoding='utf-8', errors='ignore')
    assert meta['version'] == version
    assert meta['release_label'] == f'Fjord VI · v{version}'
    assert meta['app_build'] == f'Fjord VI {version}'
    assert f'APP_VERSION = "{version}"' in main
    assert f'APP_BUILD = "Fjord VI {version}"' in main
    assert f'RELEASE_LABEL = "Fjord VI · v{version}"' in main
