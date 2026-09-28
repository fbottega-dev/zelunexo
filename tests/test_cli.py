import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zelunexo.cli import main, terminal_text
from zelunexo.storage import list_scans


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.demo = self.root / "acervo"
        self.db = self.root / "historico.sqlite3"

    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main([str(arg) for arg in args])
        return code, output.getvalue(), errors.getvalue()

    def test_full_flow_demo_scan_history_html_json(self):
        self.assertEqual(self.call("demo", self.demo)[0], 0)
        before = {p.relative_to(self.demo): p.read_bytes() for p in self.demo.rglob("*") if p.is_file()}
        report = self.root / "resultado.html"
        code, output, _ = self.call("analisar", self.demo, "--banco", self.db, "--html", report)
        self.assertEqual(code, 0)
        self.assertIn("4 grupos", output)
        self.assertIn("<!doctype html>", report.read_text(encoding="utf-8").lower())
        self.assertIn("#1", self.call("historico", "--banco", self.db)[1])
        exported = self.root / "resultado.json"
        self.assertEqual(self.call("exportar", 1, "--banco", self.db, "--saida", exported, "--formato", "json")[0], 0)
        data = json.loads(exported.read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["duplicate_groups"], 4)
        self.assertEqual(data["folder"], "acervo")
        self.assertEqual(len(data["files"]), 14)
        self.assertEqual(before, {p.relative_to(self.demo): p.read_bytes() for p in self.demo.rglob("*") if p.is_file()})

    def test_refuses_existing_demo_without_changes(self):
        self.call("demo", self.demo)
        sentinel = self.demo / "pessoal.txt"
        sentinel.write_text("preservar")
        self.assertEqual(self.call("demo", self.demo)[0], 2)
        self.assertEqual(sentinel.read_text(), "preservar")

    def test_refuses_database_or_report_inside_source(self):
        self.call("demo", self.demo)
        self.assertEqual(self.call("analisar", self.demo, "--banco", self.demo / "novo.db")[0], 2)
        self.assertEqual(self.call("analisar", self.demo, "--banco", self.db, "--html", self.demo / "novo.html")[0], 2)
        self.assertFalse(self.db.exists())

    def test_never_overwrites_report_and_preflights_before_scan(self):
        self.call("demo", self.demo)
        report = self.root / "pessoal.html"
        report.write_text("preservar")
        self.assertEqual(self.call("analisar", self.demo, "--banco", self.db, "--html", report)[0], 2)
        self.assertFalse(self.db.exists())
        self.assertEqual(report.read_text(), "preservar")

    def test_partial_scan_is_persisted_but_exit_is_three(self):
        self.demo.mkdir()
        with patch("zelunexo.scanner.digest_file", side_effect=PermissionError("Sem acesso")):
            (self.demo / "a.txt").write_text("arquivo")
            code, output, errors = self.call("analisar", self.demo, "--banco", self.db)
        self.assertEqual(code, 3)
        self.assertIn("PARCIAL", output)
        self.assertIn("Sem acesso", errors)
        self.assertEqual(list_scans(self.db)[0]["issues_count"], 1)

    def test_missing_folder_returns_clear_error_without_database(self):
        self.assertEqual(self.call("analisar", self.demo, "--banco", self.db)[0], 2)
        self.assertFalse(self.db.exists())

    def test_export_missing_id_is_error(self):
        self.call("demo", self.demo)
        self.call("analisar", self.demo, "--banco", self.db)
        self.assertEqual(self.call("exportar", 99, "--banco", self.db, "--saida", self.root / "x.html")[0], 2)

    def test_export_rejects_ids_outside_sqlite_range_without_crashing(self):
        self.call("demo", self.demo)
        self.call("analisar", self.demo, "--banco", self.db)
        output = self.root / "invalid-id.html"
        original_database = self.db.read_bytes()
        for scan_id in (2**63, -(2**63) - 1, 0, -1):
            with self.subTest(scan_id=scan_id):
                code, _, errors = self.call("exportar", scan_id, "--banco", self.db, "--saida", output)
                self.assertEqual(code, 2)
                self.assertIn("ID deve estar entre 1 e 9223372036854775807", errors)
                self.assertFalse(output.exists())
                self.assertEqual(self.db.read_bytes(), original_database)

    def test_largest_supported_export_id_reports_missing_scan(self):
        self.call("demo", self.demo)
        self.call("analisar", self.demo, "--banco", self.db)
        code, _, errors = self.call("exportar", 2**63 - 1, "--banco", self.db,
                                    "--saida", self.root / "limite.html")
        self.assertEqual(code, 2)
        self.assertIn("não encontrada", errors)

    def test_terminal_controls_are_escaped(self):
        self.assertEqual(terminal_text("ação\x1b[31m\n"), "ação\\u001b[31m\\u000a")

    def test_failed_export_removes_partial_output_and_allows_retry(self):
        self.call("demo", self.demo)
        self.call("analisar", self.demo, "--banco", self.db)
        output = self.root / "exportado.json"
        original_open = Path.open

        class FailingWriter:
            def __enter__(self):
                self.stream = original_open(output, "x", encoding="utf-8")
                return self

            def write(self, content):
                self.stream.write(content[:20])
                self.stream.flush()
                raise OSError("Disco cheio (simulado)")

            def __exit__(self, *args):
                self.stream.close()

        def open_with_failure(path, *args, **kwargs):
            return FailingWriter() if path == output else original_open(path, *args, **kwargs)

        with patch.object(Path, "open", open_with_failure):
            code, _, errors = self.call("exportar", 1, "--banco", self.db,
                                        "--saida", output, "--formato", "json")
        self.assertEqual(code, 2)
        self.assertIn("Disco cheio", errors)
        self.assertFalse(output.exists(), "Uma exportação falha não deve bloquear a próxima tentativa")
        self.assertEqual(self.call("exportar", 1, "--banco", self.db,
                                  "--saida", output, "--formato", "json")[0], 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["id"], 1)

    def test_output_created_after_preflight_is_preserved(self):
        self.call("demo", self.demo)
        self.call("analisar", self.demo, "--banco", self.db)
        output = self.root / "concorrente.json"
        from zelunexo.cli import require_new_output

        def competing_writer(path):
            require_new_output(path)
            path.write_text("Arquivo de outro processo", encoding="utf-8")

        with patch("zelunexo.cli.require_new_output", side_effect=competing_writer):
            code, _, _ = self.call("exportar", 1, "--banco", self.db,
                                   "--saida", output, "--formato", "json")
        self.assertEqual(code, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "Arquivo de outro processo")


if __name__ == "__main__":
    unittest.main()
