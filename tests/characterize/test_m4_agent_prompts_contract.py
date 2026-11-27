"""M4 Agent/Prompts HTTP and note-write boundaries using synthetic runtimes only."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from sandbox_env import available_port, materialize, seed, server
from test_http_characterization import request_json


def fixture(folder):
    port = available_port()
    root = materialize(Path(folder) / "runtime", port)
    seed(root)
    return root, port


def snapshot_tables(db_path):
    """Compare logical synthetic rows; never open or create production SQLite."""
    with closing(sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)) as db:
        names = [
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        return {
            name: sorted(
                (repr(row) for row in db.execute(
                    'SELECT * FROM "' + name.replace('"', '""') + '"'
                ))
            )
            for name in names
        }


def named_api_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if "api_key" in key.lower():
                yield item
            else:
                yield from named_api_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from named_api_keys(item)


class M4AgentPromptsContractTests(unittest.TestCase):
    def test_a_config_and_agents_use_only_synthetic_keys(self):
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_m4_config_") as tmp:
                root, port = fixture(tmp)
                synthetic_config = json.loads(
                    (root / "config" / "config.json").read_text(encoding="utf-8")
                )
                self.assertEqual(synthetic_config["api"]["openai_api_key"], "")
                self.assertEqual(synthetic_config["api"]["claude_api_key"], "")
                with server(root, mode, port) as base:
                    for endpoint, expected in (
                        ("/api/config", dict),
                        ("/api/agent/agents", list),
                    ):
                        status, body = request_json(base, endpoint)
                        self.assertEqual(status, 200, (mode, endpoint, body))
                        self.assertIsInstance(body, expected, (mode, endpoint))
                        for key_value in named_api_keys(body):
                            self.assertIn(key_value, ("", None), (mode, endpoint))

    def test_b_read_only_prompts_discard_and_dependencies(self):
        endpoints = (
            ("/api/prompts", list),
            ("/api/discard-pile", list),
            ("/api/dependencies", dict),
        )
        for mode in ("legacy", "factory"):
            with self.subTest(mode=mode), TemporaryDirectory(prefix="lt_m4_reads_") as tmp:
                root, port = fixture(tmp)
                db_path = root / "data" / "synthetic.sqlite3"
                with server(root, mode, port) as base:
                    before = snapshot_tables(db_path)
                    for endpoint, expected in endpoints:
                        status, body = request_json(base, endpoint)
                        self.assertEqual(status, 200, (mode, endpoint, body))
                        self.assertIsInstance(body, expected, (mode, endpoint))
                    after = snapshot_tables(db_path)
                    self.assertEqual(after, before, (mode, "GET changed synthetic rows"))

    def test_c_factory_forbids_both_note_write_paths(self):
        with TemporaryDirectory(prefix="lt_m4_notes_") as tmp:
            root, port = fixture(tmp)
            with server(root, "factory", port) as base:
                for name in ("benign-note.md", "../malicious.md"):
                    with self.subTest(filename=name):
                        status, response = request_json(
                            base, "/api/agent/save-note",
                            {"filename": name, "content": "synthetic test only"},
                        )
                        self.assertEqual(status, 403, response)
                        self.assertEqual(list((root / "vault").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
