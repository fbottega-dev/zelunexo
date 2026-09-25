"""Report safety and meaningful data states, without browser dependencies."""

from html.parser import HTMLParser
import unittest

from zelunexo.report import format_size, render_html


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def scan_with(files=None, **overrides):
    scan = {
        "id": 7,
        "created_at": "2026-09-24T21:30:00+00:00",
        "folder": "Projetos",
        "files": files or [],
        "issues": [],
        "skipped": [],
        "excludes": [],
    }
    scan.update(overrides)
    return scan


def file(path, size=1024, sha256="a" * 64):
    return {"path": path, "size": size, "sha256": sha256, "mtime_ns": 0}


class ReportTests(unittest.TestCase):
    def test_renders_groups_and_logical_estimate(self):
        html = render_html(scan_with([file("A/original.txt"), file("B/cópia.txt"), file("C/cópia.txt")]))
        document = Document(html)
        groups = [attrs for tag, attrs in document.tags if tag == "details" and attrs.get("class") == "duplicate-group"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["data-files"], "3")
        self.assertIn("2,0 KiB", html)
        self.assertIn("66,7% do volume", html)
        self.assertIn("A/original.txt", html)
        self.assertIn("B/cópia.txt", html)
        self.assertIn("C/cópia.txt", html)
        self.assertIn("nem garante espaço livre", html.lower())
        self.assertIn("24 set 2026 · 21:30 UTC", html)

    def test_user_text_cannot_introduce_markup_or_script(self):
        attack = '\"><img src=x onerror=alert(1)><script>alert("x")</script>'
        scan = scan_with(
            [file(f"A/{attack}"), file(f"B/{attack}")],
            folder=attack,
            created_at=attack,
            id=attack,
            issues=[{"path": attack, "message": attack}],
            skipped=[{"path": attack, "reason": attack}],
            excludes=[attack],
        )
        html = render_html(scan)
        document = Document(html)
        self.assertEqual(sum(tag == "script" for tag, _ in document.tags), 1)
        self.assertFalse(any(tag == "img" for tag, _ in document.tags))
        self.assertFalse(any(key.startswith("on") for _, attrs in document.tags for key in attrs))
        self.assertIn(attack, "".join(document.text))
        scripts = [attrs for tag, attrs in document.tags if tag == "script"]
        self.assertNotIn("src", scripts[0])

    def test_hash_is_escaped_even_for_untrusted_imported_data(self):
        digest = "</code><img src=x onerror=alert(1)>"
        html = render_html(scan_with([file("a", sha256=digest), file("b", sha256=digest)]))
        self.assertIn("&lt;/code&gt;&lt;img", html)
        self.assertFalse(any(tag == "img" for tag, _ in Document(html).tags))

    def test_empty_scan_does_not_claim_no_duplicates_were_found(self):
        html = render_html(scan_with())
        self.assertIn("Nenhum arquivo analisado.", html)
        self.assertNotIn("Nenhum grupo duplicado.", html)
        self.assertIn("0,0% do volume", html)
        self.assertNotIn('id="file-search"', html)

    def test_unique_files_have_clear_empty_state(self):
        html = render_html(scan_with([file("único.txt")]))
        self.assertIn("Nenhum grupo duplicado.", html)
        self.assertIn("Análise concluída", html)

    def test_zero_byte_files_explain_why_they_are_not_grouped(self):
        html = render_html(scan_with([file("vazio-a", size=0), file("vazio-b", size=0)]))
        self.assertIn("Não há grupos de arquivos não vazios", html)
        self.assertIn("Arquivos vazios entram na contagem, mas não nos grupos", html)
        self.assertNotIn('class="duplicate-group"', html)

    def test_partial_report_includes_failure_and_exclusion_context(self):
        html = render_html(scan_with(
            [file("legível.txt")],
            issues=[{"path": "negado.txt", "message": "Permissão negada"}],
            skipped=[{"path": "atalho", "reason": "Link simbólico"}],
            excludes=["*.tmp"],
        ))
        self.assertIn("Análise parcial", html)
        self.assertIn("apenas os arquivos analisados", html)
        self.assertIn("negado.txt", html)
        self.assertIn("Permissão negada", html)
        self.assertIn("Link simbólico", html)
        self.assertIn("*.tmp", html)

    def test_report_is_standalone_and_paths_are_not_file_links(self):
        document = Document(render_html(scan_with([file("pasta/a"), file("pasta/b")])))
        for tag, attrs in document.tags:
            self.assertNotIn("src", attrs)
            if "href" in attrs:
                self.assertTrue(attrs["href"].startswith("#"))
        self.assertTrue(any(tag == "html" and attrs.get("lang") == "pt-BR" for tag, attrs in document.tags))

    def test_utc_date_preserves_real_instant(self):
        html = render_html(scan_with(created_at="2026-09-24T18:30:00-03:00"))
        self.assertIn("24 set 2026 · 21:30 UTC", html)

    def test_binary_units_and_negative_values(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1023), "1023 B")
        self.assertEqual(format_size(1024), "1,0 KiB")
        self.assertEqual(format_size(1024 ** 2 + 512 * 1024), "1,5 MiB")
        with self.assertRaises(ValueError):
            format_size(-1)


if __name__ == "__main__":
    unittest.main()
