"""First-run credentials must be private, consistent, and preserved on restart."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_first_start_generates_private_credentials_and_preserves_existing_env(tmp_path):
    for name in ('start_services.sh', '.env.example'):
        shutil.copy2(ROOT / name, tmp_path / name)
    docker = tmp_path / 'docker'
    docker.write_text(f'''#!{sys.executable}
import os, pathlib, sys
if sys.argv[1] == 'run':
    code = sys.stdin.read().replace('"/template"', repr(str(pathlib.Path.cwd() / '.env.example')))
    if os.environ.get('FAIL_BOOTSTRAP'):
        sys.exit(1)
    exec(code)
''')
    docker.chmod(0o755)
    env = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH']}
    command = ['sh', str(tmp_path / 'start_services.sh'), '--cpu']
    subprocess.run(command, env={**env, 'FAIL_BOOTSTRAP': '1'}, check=False, capture_output=True)
    assert not (tmp_path / '.env').exists()
    assert not (tmp_path / '.env.bootstrap.tmp').exists()
    subprocess.run(command, env=env, check=True, capture_output=True)
    local_env = tmp_path / '.env'
    original = local_env.read_bytes()
    assert local_env.stat().st_mode & 0o077 == 0
    assert b'change-me-' not in original
    values = dict(line.split('=', 1) for line in original.decode().splitlines()
                  if '=' in line and not line.startswith('#'))
    keys = ['POSTGRES_PASSWORD', 'NEO4J_PASSWORD', 'REDIS_PASSWORD',
            'S3_ACCESS_KEY', 'S3_SECRET_KEY', 'SECRET_KEY', 'SERVICE_AUTH_TOKEN']
    assert len({values[key] for key in keys}) == len(keys)
    assert values['POSTGRES_PASSWORD'] in values['POSTGRES_URL']
    subprocess.run(command, env=env, check=True, capture_output=True)
    assert local_env.read_bytes() == original
