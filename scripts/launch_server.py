"""启动 Web 后端并记录 PID（供 stop_web_safe.bat 使用）"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_DIR = os.path.join(ROOT, '.run')
PID_FILE = os.path.join(RUN_DIR, 'server.pid')
LOG_FILE = os.path.join(RUN_DIR, 'server.log')

os.makedirs(RUN_DIR, exist_ok=True)

log = open(LOG_FILE, 'a', encoding='utf-8')
log.write('\n--- server start ---\n')
log.flush()

flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
proc = subprocess.Popen(
    [sys.executable, os.path.join(ROOT, 'server', 'backend_api.py')],
    cwd=ROOT,
    stdout=log,
    stderr=subprocess.STDOUT,
    creationflags=flags,
)

with open(PID_FILE, 'w', encoding='utf-8') as f:
    f.write(str(proc.pid))

print('SERVER_PID=' + str(proc.pid))
print('LOG=' + LOG_FILE)
