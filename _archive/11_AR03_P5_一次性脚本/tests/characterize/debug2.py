import sys
sys.path.insert(0, "tests/characterize")
from sandbox_builder import build_sandbox
import tempfile
from pathlib import Path
import subprocess
import time

with tempfile.TemporaryDirectory(prefix="sal_test_") as td:
    env = build_sandbox(Path(td), port=18779)
    sb = env["root"]
    script = sb / "factory_runner.py"
    lines = [
        "import sys, os",
        'sys.path.insert(0, r"' + str(sb) + '")',
        'os.chdir(r"' + str(sb) + '")',
        "from server.app import create_app",
        "app = create_app()",
        'if __name__ == "__main__":',
        "    app.run(host=\"127.0.0.1\", port=18779, debug=False, use_reloader=False)",
    ]
    with open(script, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    env2 = {"PYTHONPATH": str(sb), "PATH": __import__("os").environ.get("PATH", "")}
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(sb),
        env=env2,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(5)
    if proc.poll() is not None:
        out = proc.stdout.read() if proc.stdout else b""
        print("EXITED:", proc.returncode)
        print(out.decode(errors="replace"))
    else:
        print("Still running, pid:", proc.pid)
        proc.terminate()
        try: proc.wait(timeout=3)
        except: proc.kill()
        out = proc.stdout.read() if proc.stdout else b""
        print("OUTPUT:", out.decode(errors="replace"))
