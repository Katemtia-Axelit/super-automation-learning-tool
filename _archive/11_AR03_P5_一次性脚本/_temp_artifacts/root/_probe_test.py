"""Debug probe for multi-draw."""
import sys, os, shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import time, json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0, 'tests/characterize')
from sandbox_env import materialize, seed, available_port

with TemporaryDirectory(prefix='lt_probe_') as temp:
    port = available_port()
    root = materialize(Path(temp) / 'runtime', port)
    seed(root)
    src_root = Path.cwd().parent.parent
    shutil.copyfile(src_root / 'run_app.py', root / 'run_app.py')
    import subprocess
    env = {k:v for k,v in os.environ.items() if not (k.upper() in {'PYTHONPATH','PYTHONHOME'} or any(s in k.upper() for s in ('API_KEY','TOKEN','SECRET')))}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    p = subprocess.Popen([sys.executable, '-I', 'run_app.py'], cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        time.sleep(3)
        sb = (root / 'server' / 'blueprints' / 'gacha_bp.py').read_text(encoding='utf-8')
        print('Sandbox def count:', sb.count('def _parse_available_time'))
        print('Sandbox call count:', sb.count('minutes = _parse_available_time'))
        req = Request('http://127.0.0.1:%d/api/gacha/multi-draw' % port,
                      data=json.dumps({'available_time': 30, 'count': 2}).encode('utf-8'),
                      headers={'Content-Type':'application/json'})
        try:
            with urlopen(req, timeout=3) as r:
                print('STATUS:', r.status)
                print('BODY:', r.read().decode('utf-8')[:500])
        except HTTPError as e:
            print('STATUS:', e.code)
            body = e.read().decode('utf-8')
            print('BODY:', body[:500])
        time.sleep(0.5)
        p.terminate()
        out, _ = p.communicate(timeout=3)
        outpath = Path(r'D:\Axelit\.工作\trae\超级自动化学习工具\_probe_out.txt')
        outpath.write_bytes(out)
        print('Server output written to', outpath)
    except:
        p.kill()
        raise
