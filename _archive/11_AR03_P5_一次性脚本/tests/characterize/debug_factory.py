import sys
sys.path.insert(0, "tests/characterize")
from sandbox_builder import build_sandbox
import tempfile
from pathlib import Path
import subprocess

with tempfile.TemporaryDirectory(prefix="sal_test_") as td:
    env = build_sandbox(Path(td), port=18777)
    sb = env["root"]
    script = sb / "factory_runner.py"
    lines = [
        "import sys, os",
        'sys.path.insert(0, "' + str(sb) + '")',
        'os.chdir("' + str(sb) + '")',
        "from server.app import create_app",
        "app = create_app()",
        'if __name__ == "__main__":',
        "    app.run(host=\"127.0.0.1\", port=18777, debug=False, use_reloader=False)",
    ]
    with open(script, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    result = subprocess.run([sys.executable, str(script)], cwd=str(sb), capture_output=True, timeout=10, env={"PYTHONPATH": str(sb), "PATH": __import__("os").environ.get("PATH", "")})
    print("stdout:", result.stdout.decode(errors="replace"))
    print("stderr:", result.stderr.decode(errors="replace"))
