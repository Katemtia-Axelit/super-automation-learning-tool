"""停止由 launch_server.py 启动的后端进程，并清理占用 5000 端口的遗留进程。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PID_FILE = os.path.join(ROOT, '.run', 'server.pid')
PORT = 5000


def _kill_port_listeners(port):
    """Windows: 结束监听指定端口的进程，避免旧实例与新版代码并存。"""
    try:
        out = subprocess.check_output(['netstat', '-ano'], text=True, errors='ignore')
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    pids = set()
    needle = f':{port}'
    for line in out.splitlines():
        if needle not in line or 'LISTENING' not in line:
            continue
        parts = line.split()
        if parts and parts[-1].isdigit():
            pids.add(int(parts[-1]))
    for pid in pids:
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], check=False, capture_output=True)


if os.path.exists(PID_FILE):
    try:
        pid = int(open(PID_FILE, encoding='utf-8').read().strip())
    except ValueError:
        print('INVALID_PID_FILE')
        os.remove(PID_FILE)
        sys.exit(1)
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], check=False, capture_output=True)
    try:
        os.remove(PID_FILE)
    except OSError:
        pass
    print('STOPPED_PID=' + str(pid))
else:
    print('NO_PID_FILE')

_kill_port_listeners(PORT)
