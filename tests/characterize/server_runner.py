# HTTP runner
import os
import sys
import time
import json
import socket
import subprocess
import signal
import urllib.request
import urllib.error
from pathlib import Path



PROJECT_ROOT = Path(r'D:\Axelit\.工作\trae\超级自动化学习工具')



def http_get(port, path, timeout=5):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}')
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode('utf-8') or 'null')
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read().decode('utf-8'))
        except: body = None
        return e.code, body


def http_post(port, path, data=None, timeout=5):
    body = json.dumps(data or {}).encode('utf-8')
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode('utf-8') or 'null')
    except urllib.error.HTTPError as e:
        try: body_resp = json.loads(e.read().decode('utf-8'))
        except: body_resp = None
        return e.code, body_resp




def _wait_for_server(port, proc, wait, label):
    deadline = time.time() + wait
    last_err = None
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else b''
            raise RuntimeError(label + ' exited: code=' + str(proc.returncode))
        try:
            r = urllib.request.urlopen('http://127.0.0.1:' + str(port) + '/api/health', timeout=1)
            if r.status == 200:
                return proc
        except Exception as e:
            last_err = e
            time.sleep(0.3)
    proc.terminate()
    raise RuntimeError(label + ' failed to start: ' + str(last_err))


def start_legacy_server(sandbox, port, wait=15):
    sandbox = Path(sandbox).resolve()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(sandbox)
    env["PYTHONUNBUFFERED"] = "1"
    script = sandbox / "legacy_runner.py"
    sb_str = str(sandbox).replace("\\", "/")
    with open(script, "w", encoding="utf-8") as f:
        f.write("import sys, os\n")
        f.write('sys.path.insert(0, r"' + str(sandbox) + '")\n')
        f.write('os.chdir(r"' + str(sandbox) + '")\n')
        f.write("from server import backend_api\n")
        f.write('if __name__ == "__main__":\n')
        f.write('    backend_api.app.run(host="127.0.0.1", port=' + str(port) + ', debug=False, use_reloader=False)\n')
    cmd = [sys.executable, str(script)]
    proc = subprocess.Popen(
        cmd,
        cwd=str(sandbox),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return _wait_for_server(port, proc, wait, "legacy")

def start_factory_server(sandbox, port, wait=15):
    sandbox = Path(sandbox).resolve()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(sandbox)
    env["PYTHONUNBUFFERED"] = "1"
    script = sandbox / "factory_runner.py"
    with open(script, "w", encoding="utf-8") as f:
        f.write("import sys, os\n")
        f.write('sys.path.insert(0, r"' + str(sandbox) + '")\n')
        f.write('os.chdir(r"' + str(sandbox) + '")\n')
        f.write("from server.app import create_app\n")
        f.write("app = create_app()\n")
        f.write('if __name__ == "__main__":\n')
        f.write('    app.run(host="127.0.0.1", port=' + str(port) + ', debug=False, use_reloader=False)\n')
    cmd = [sys.executable, str(script)]
    proc = subprocess.Popen(
        cmd,
        cwd=str(sandbox),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return _wait_for_server(port, proc, wait, "factory")


def stop_server(proc):
    if proc is None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass

