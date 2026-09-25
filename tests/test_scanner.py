"""Varreduras reais em pastas temporárias; falhas e corridas determinísticas."""

import errno
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from zelunexo.domain import group_duplicates, summarize
from zelunexo.scanner import BLOCK_SIZE, digest_file, scan_folder


def changed_stat(info):
    """Simula uma alteração de metadados sem depender da resolução do relógio."""
    return SimpleNamespace(
        st_mode=info.st_mode, st_dev=info.st_dev, st_ino=info.st_ino,
        st_size=info.st_size, st_mtime_ns=info.st_mtime_ns + 1,
        st_ctime_ns=info.st_ctime_ns,
        st_file_attributes=getattr(info, "st_file_attributes", 0),
    )


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "minha coleção"
        self.root.mkdir()

    def write_file(self, relative, content=b"conteudo"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_hashes_contents_and_ignores_names_as_equality_criterion(self):
        self.write_file("férias/original.txt", b"iguais")
        self.write_file("cópia renomeada.txt", b"iguais")
        self.write_file("a/mesmo.txt", b"ABCDEF")
        self.write_file("b/mesmo.txt", b"UVWXYZ")

        scan = scan_folder(self.root)

        self.assertEqual(scan["issues"], [])
        self.assertEqual(len(scan["files"]), 4)
        groups = group_duplicates(scan["files"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["paths"], ["cópia renomeada.txt", "férias/original.txt"])
        self.assertEqual(groups[0]["sha256"], hashlib.sha256(b"iguais").hexdigest())

    def test_empty_files_are_counted_but_do_not_inflate_savings(self):
        self.write_file("vazio 1", b"")
        self.write_file("vazio 2", b"")

        scan = scan_folder(self.root)

        self.assertEqual([file["size"] for file in scan["files"]], [0, 0])
        self.assertEqual(scan["files"][0]["sha256"], hashlib.sha256(b"").hexdigest())
        self.assertEqual(summarize(scan)["scanned_files"], 2)
        self.assertEqual(summarize(scan)["potential_bytes"], 0)
        self.assertEqual(group_duplicates(scan["files"]), [])

    def test_large_file_digest_covers_multiple_read_blocks(self):
        contents = b"a" * BLOCK_SIZE + b"b" * BLOCK_SIZE + b"fim"
        self.write_file("grande.bin", contents)

        scan = scan_folder(self.root)
        self.assertEqual(scan["issues"], [])
        record = scan["files"][0]

        self.assertEqual(record["size"], len(contents))
        self.assertEqual(record["sha256"], hashlib.sha256(contents).hexdigest())

    def test_unicode_paths_are_relative_sorted_and_use_forward_slashes(self):
        expected = ["ação/東京.txt", "arquivo com espaço.txt", "álbum/Olá.txt"]
        for relative in reversed(expected):
            self.write_file(relative, relative.encode("utf-8"))

        scan = scan_folder(self.root)

        self.assertEqual([file["path"] for file in scan["files"]], sorted(expected))
        self.assertEqual(scan["folder"], "minha coleção")
        self.assertNotIn(str(self.root), repr(scan))

    def test_default_exclusions_prune_directories_at_any_depth(self):
        for relative in [
            ".git/config", "projeto/node_modules/lib.js",
            "projeto/.venv/config", "projeto/__pycache__/module.pyc",
            "projeto/normal.py",
        ]:
            self.write_file(relative)

        scan = scan_folder(self.root)

        self.assertEqual([file["path"] for file in scan["files"]], ["projeto/normal.py"])
        self.assertEqual([item["path"] for item in scan["skipped"]], [
            ".git", "projeto/.venv", "projeto/__pycache__", "projeto/node_modules",
        ])
        self.assertEqual(scan["issues"], [])

    def test_custom_exclusions_match_components_and_relative_globs(self):
        for relative in [
            "cache/item.txt", "nested/cache/item.txt", "nested/rascunho.tmp",
            "relatórios/antigo.bak", "outros/antigo.bak", "leia.txt",
        ]:
            self.write_file(relative)

        scan = scan_folder(self.root, ["cache", "*.tmp", "relatórios/*.bak"])

        self.assertEqual(scan["issues"], [])
        self.assertEqual([file["path"] for file in scan["files"]], ["leia.txt", "outros/antigo.bak"])
        self.assertEqual([item["path"] for item in scan["skipped"]], [
            "cache", "nested/cache", "nested/rascunho.tmp", "relatórios/antigo.bak",
        ])

    def test_invalid_exclusion_patterns_are_rejected(self):
        for pattern in ["", "pasta\\arquivo"]:
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                scan_folder(self.root, [pattern])

    def test_file_is_not_accepted_as_root(self):
        path = self.write_file("arquivo.txt")

        with self.assertRaises(ValueError):
            scan_folder(path)

    def test_symbolic_links_do_not_follow_files_directories_or_cycles(self):
        original = self.write_file("original.txt")
        external = Path(self.temporary.name) / "fora"
        external.mkdir()
        (external / "segredo.txt").write_text("fora do escopo", encoding="utf-8")
        try:
            os.symlink(original, self.root / "atalho.txt")
            os.symlink(external, self.root / "externa", target_is_directory=True)
            os.symlink(self.root, self.root / "ciclo", target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Sistema não permite criar links simbólicos: {error}")

        scan = scan_folder(self.root)

        self.assertEqual([file["path"] for file in scan["files"]], ["original.txt"])
        self.assertEqual([item["path"] for item in scan["skipped"]], ["atalho.txt", "ciclo", "externa"])
        self.assertTrue(all("Link" in item["reason"] for item in scan["skipped"]))
        self.assertEqual(scan["issues"], [])

    def test_symbolic_link_root_is_rejected(self):
        link = Path(self.temporary.name) / "atalho raiz"
        try:
            os.symlink(self.root, link, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Sistema não permite criar link simbólico: {error}")

        with self.assertRaises(ValueError):
            scan_folder(link)

    def test_hard_links_are_counted_once_without_false_savings(self):
        original = self.write_file("a-original.bin", b"dados")
        try:
            os.link(original, self.root / "b-hardlink.bin")
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Sistema não permite criar hard link: {error}")
        self.write_file("c-cópia.bin", b"dados")

        scan = scan_folder(self.root)

        self.assertEqual(scan["issues"], [])
        self.assertEqual([file["path"] for file in scan["files"]], ["a-original.bin", "c-cópia.bin"])
        self.assertEqual(scan["skipped"], [{"path": "b-hardlink.bin", "reason": "Hard link já contado"}])
        self.assertEqual(summarize(scan)["potential_bytes"], len(b"dados"))

    def test_file_permission_failure_becomes_issue_and_scan_continues(self):
        denied = self.write_file("negado.txt")
        self.write_file("permitido.txt")
        original_open = os.open

        def controlled_open(path, flags, *args, **kwargs):
            if Path(path) == denied:
                raise PermissionError(errno.EACCES, "Acesso negado")
            return original_open(path, flags, *args, **kwargs)

        with patch("zelunexo.scanner.os.open", side_effect=controlled_open):
            scan = scan_folder(self.root)

        self.assertEqual([file["path"] for file in scan["files"]], ["permitido.txt"])
        self.assertEqual(scan["issues"], [{"path": "negado.txt", "message": "Acesso negado"}])

    def test_directory_permission_failure_becomes_issue_and_scan_continues(self):
        self.write_file("negada/arquivo.txt")
        self.write_file("permitido.txt")
        original_scandir = os.scandir

        def controlled_scandir(path):
            if Path(path) == self.root / "negada":
                raise PermissionError(errno.EACCES, "Pasta sem acesso")
            return original_scandir(path)

        with patch("zelunexo.scanner.os.scandir", side_effect=controlled_scandir):
            scan = scan_folder(self.root)

        self.assertEqual([file["path"] for file in scan["files"]], ["permitido.txt"])
        self.assertEqual(scan["issues"], [{"path": "negada", "message": "Pasta sem acesso"}])

    def test_changed_file_before_read_is_rejected(self):
        path = self.write_file("mudou.txt")
        expected = path.lstat()

        with patch("zelunexo.scanner.os.fstat", return_value=changed_stat(expected)):
            with self.assertRaisesRegex(OSError, "mudou antes"):
                digest_file(path, expected)

    def test_different_ctime_conventions_between_stat_apis_are_supported(self):
        path = self.write_file("metadados.bin", b"estavel")
        expected = path.lstat()
        descriptor_info = changed_stat(expected)
        descriptor_info.st_mtime_ns = expected.st_mtime_ns
        descriptor_info.st_ctime_ns += 100

        with patch("zelunexo.scanner.os.fstat", side_effect=[descriptor_info, descriptor_info]):
            digest = digest_file(path, expected)

        self.assertEqual(digest, hashlib.sha256(b"estavel").hexdigest())

    def test_changed_ctime_on_same_descriptor_is_rejected(self):
        path = self.write_file("alterado.bin")
        expected = path.lstat()
        changed = changed_stat(expected)
        changed.st_mtime_ns = expected.st_mtime_ns
        changed.st_ctime_ns += 1

        with patch("zelunexo.scanner.os.fstat", side_effect=[expected, changed]):
            with self.assertRaisesRegex(OSError, "mudou durante"):
                digest_file(path, expected)

    def test_windows_reparse_point_is_skipped_without_opening_target(self):
        path = self.write_file("junction")
        reparse_info = changed_stat(path.lstat())
        reparse_info.st_file_attributes = 0x400
        original_lstat = Path.lstat

        def controlled_lstat(current, *args, **kwargs):
            if current == path:
                return reparse_info
            return original_lstat(current, *args, **kwargs)

        with patch.object(Path, "lstat", controlled_lstat):
            scan = scan_folder(self.root)

        self.assertEqual(scan["files"], [])
        self.assertEqual(scan["issues"], [])
        self.assertEqual(scan["skipped"], [{"path": "junction", "reason": "Link ou junction"}])

    def test_changed_file_during_read_becomes_issue_without_digest_record(self):
        path = self.write_file("mudou.txt")
        expected = path.lstat()

        with patch("zelunexo.scanner.os.fstat", side_effect=[expected, changed_stat(expected)]):
            scan = scan_folder(self.root)

        self.assertEqual(scan["files"], [])
        self.assertEqual(len(scan["issues"]), 1)
        self.assertEqual(scan["issues"][0]["path"], "mudou.txt")
        self.assertIn("mudou durante", scan["issues"][0]["message"])

    def test_replaced_path_after_read_is_rejected(self):
        path = self.write_file("substituído.txt")
        expected = path.lstat()

        with patch.object(Path, "lstat", return_value=changed_stat(expected)):
            with self.assertRaisesRegex(OSError, "mudou durante"):
                digest_file(path, expected)

    def test_source_contents_names_and_mtimes_are_preserved(self):
        paths = [self.write_file("a.txt", b"igual"), self.write_file("pasta/b.txt", b"igual")]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

        scan_folder(self.root)

        after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        self.assertEqual(before, after)
        self.assertEqual(sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*") if path.is_file()),
                         ["a.txt", "pasta/b.txt"])


if __name__ == "__main__":
    unittest.main()
