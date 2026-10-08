"""Compare real Legacy __main__ registration with Factory route inventory."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from sandbox_env import available_port, materialize, seed

_SCANNER = '''
import json, runpy, sys
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
mode=sys.argv[1]
if mode=="legacy":
    from flask import Flask
    Flask.run=lambda self,*args,**kwargs: None
    app=runpy.run_path(str(root/"server"/"backend_api.py"),run_name="__main__")["app"]
else:
    from server.app import create_app
    app=create_app()
routes=sorted({(r.rule,m) for r in app.url_map.iter_rules()
              for m in r.methods if m not in {"HEAD","OPTIONS"}})
print("ROUTES_JSON="+json.dumps(routes))
'''


class RouteInventoryTests(unittest.TestCase):
    def test_factory_covers_actual_legacy_entry(self):
        routes = {}
        with TemporaryDirectory(prefix="lt_route_inventory_") as temp:
            root = materialize(Path(temp) / "sandbox", available_port())
            seed(root)
            runner = root / "_route_scanner.py"
            runner.write_text(_SCANNER, encoding="utf-8")
            env = {k:v for k,v in os.environ.items() if (
                "API_KEY" not in k.upper() and "TOKEN" not in k.upper()
                and k.upper() not in ("PYTHONPATH", "PYTHONHOME")
            )}
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            for mode in ("legacy", "factory"):
                proc = subprocess.run(
                    [sys.executable, "-I", str(runner), mode],
                    cwd=root, env=env, capture_output=True, text=True,
                    timeout=20,
                )
                self.assertEqual(proc.returncode,0,(mode,proc.stderr[-1000:]))
                lines = [line for line in proc.stdout.splitlines()
                         if line.startswith("ROUTES_JSON=")]
                self.assertEqual(len(lines),1,(mode,proc.stdout[-1000:]))
                routes[mode] = {tuple(r) for r in json.loads(lines[0][12:])}
        missing = routes["legacy"] - routes["factory"]
        self.assertFalse(missing, f"Legacy routes missing in Factory: {sorted(missing)}")


if __name__ == "__main__":
    unittest.main()
