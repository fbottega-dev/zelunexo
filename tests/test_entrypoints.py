"""Os dois comandos públicos devem emitir UTF-8, inclusive com saída redirecionada."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1]
with (PROJECT / "pyproject.toml").open("rb") as configuration:
    ENTRYPOINT = tomllib.load(configuration)["project"]["scripts"]["zelunexo"]


class EntrypointTests(unittest.TestCase):
    def run_command(self, mode, *args):
        if mode == "module":
            command = [sys.executable, "-m", "zelunexo"]
        else:
            # Resolve o mesmo ponto de entrada usado pelo executável instalado.
            code = (
                "import importlib, sys; "
                f"module, name = {ENTRYPOINT!r}.split(':'); "
                "raise SystemExit(getattr(importlib.import_module(module), name)())"
            )
            command = [sys.executable, "-c", code]
        return subprocess.run(
            [*command, *map(str, args)], cwd=PROJECT,
            env={**os.environ, "PYTHONIOENCODING": "ascii"},
            capture_output=True, timeout=20,
        )

    def test_help_uses_utf8_for_both_entrypoints(self):
        for mode in ("module", "installed"):
            with self.subTest(mode=mode):
                result = self.run_command(mode, "--help")
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
                self.assertIn("conteúdo", result.stdout.decode("utf-8"))

    def test_unicode_demo_path_does_not_turn_success_into_error(self):
        with tempfile.TemporaryDirectory() as folder:
            for mode in ("module", "installed"):
                with self.subTest(mode=mode):
                    target = Path(folder) / f"coleção-{mode}"
                    result = self.run_command(mode, "demo", target)
                    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
                    self.assertIn("arquivos fictícios", result.stdout.decode("utf-8"))
                    self.assertIn(target.name, result.stdout.decode("utf-8"))
                    self.assertTrue((target / "referencias/leia-me.txt").exists())

    def test_errors_are_readable_in_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            for mode in ("module", "installed"):
                with self.subTest(mode=mode):
                    result = self.run_command(mode, "historico", "--banco", Path(folder) / "ausente.db")
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("Histórico não encontrado", result.stderr.decode("utf-8"))
                    self.assertNotIn("Traceback", result.stderr.decode("utf-8"))
