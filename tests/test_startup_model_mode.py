"""Exercise startup selection without changing the host Docker stack."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('native,gpu,flag,expected', [
    (True, True, None, 'native'),
    (False, True, None, 'gpu'),
    (False, False, None, 'cpu'),
    (True, True, '--cpu', 'cpu'),
    (False, False, '--native', 'native'),
    (False, False, '--gpu', 'gpu'),
])
def test_start_and_stop_use_selected_runtime(tmp_path, native, gpu, flag, expected):
    for name in ('start_services.sh', 'stop_services.sh'):
        shutil.copy2(ROOT / name, tmp_path / name)
    (tmp_path / '.env').touch()
    docker = tmp_path / 'docker'
    docker.write_text(f'''#!{sys.executable}
import os, sys, json
from pathlib import Path
args = sys.argv[1:]
with Path('calls.jsonl').open('a') as log:
    log.write(json.dumps([args, os.environ.get('COMPOSE_FILE')]) + '\\n')
if args[0] == 'run':
    sys.exit(0 if os.environ['NATIVE' if '/probe.py' in args else 'GPU'] == '1' else 1)
''')
    docker.chmod(0o755)
    env = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
           'NATIVE': str(int(native)), 'GPU': str(int(gpu))}
    subprocess.run(['sh', str(tmp_path / 'start_services.sh'), *([flag] if flag else []), '--build'],
                   env=env, check=True, capture_output=True)
    assert (tmp_path / '.lumidoc-model-mode').read_text().strip() == expected
    subprocess.run(['sh', str(tmp_path / 'stop_services.sh')], env=env, check=True, capture_output=True)
    import json
    calls = [json.loads(line) for line in (tmp_path / 'calls.jsonl').read_text().splitlines()]
    up = next(call for call in calls if call[0][:2] == ['compose', 'up'])
    down = next(call for call in calls if call[0][:2] == ['compose', 'down'])
    assert '--build' in up[0]
    assert up[1] == down[1]
    suffix = 'docker-compose.yml' if expected == 'cpu' else f'docker-compose.{expected}.yml'
    assert up[1].endswith(suffix)
    if flag:
        assert not any(call[0][0] == 'run' for call in calls)


@pytest.mark.parametrize('apple,models,unreachable,expected', [
    ('1', [], False, 0),
    ('0', [{'size_vram': 1024}], False, 0),
    ('0', [{'size_vram': 0}], False, 1),
    ('0', [], False, 1),
    ('1', [], True, 1),
])
def test_native_probe_checks_reachability_and_gpu(monkeypatch, apple, models, unreachable, expected):
    import io
    import json
    import runpy
    import urllib.request

    monkeypatch.setenv('APPLE_SILICON', apple)

    def urlopen(url, timeout):
        assert url.endswith('/api/ps')
        assert timeout == 3
        if unreachable:
            raise OSError('Unavailable')
        return io.BytesIO(json.dumps({'models': models}).encode())

    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(ROOT / 'scripts/detect_native_gpu.py'))
    assert result.value.code == expected
