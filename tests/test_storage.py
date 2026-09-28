"""Persistência real em SQLite temporário e garantias de transação."""

from copy import deepcopy
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from zelunexo.storage import APPLICATION_ID, SCHEMA, connect, list_scans, load_scan, save_scan


def sample_scan():
    digest = hashlib.sha256(b"dados").hexdigest()
    return {
        "id": None,
        "created_at": "2026-01-01T12:00:00+00:00",
        "folder": "Documentos de João 東京",
        "files": [
            {"path": "álbum/cópia.txt", "size": 5, "sha256": digest, "mtime_ns": 1234567890123456789},
            {"path": "originais/ação.txt", "size": 5, "sha256": digest, "mtime_ns": 1234567890123456788},
        ],
        "issues": [{"path": "negado/maçã.txt", "message": "Acesso não permitido"}],
        "skipped": [{"path": "cache/東京", "reason": "Padrão de exclusão"}],
        "excludes": [".git", "rascunhos/ação*.txt"],
    }


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.database = self.directory / "histórico 東京" / "zelunexo.sqlite3"

    def test_roundtrip_preserves_unicode_metadata_and_sorted_files(self):
        original = sample_scan()
        unchanged = deepcopy(original)

        scan_id = save_scan(self.database, original)
        loaded = load_scan(self.database, scan_id)

        expected = deepcopy(original)
        expected["id"] = scan_id
        expected["files"].sort(key=lambda item: item["path"])
        self.assertEqual(loaded, expected)
        self.assertEqual(original, unchanged)
        self.assertIsInstance(scan_id, int)

    def test_failed_save_rolls_back_scan_and_files_and_keeps_previous_history(self):
        good = sample_scan()
        good_id = save_scan(self.database, good)
        previous = load_scan(self.database, good_id)
        invalid = sample_scan()
        invalid["files"].append(deepcopy(invalid["files"][0]))

        with self.assertRaises(sqlite3.IntegrityError):
            save_scan(self.database, invalid)

        self.assertEqual(load_scan(self.database, good_id), previous)
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM scans").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM files").fetchone()[0], 2)
        later_id = save_scan(self.database, good)
        self.assertNotEqual(later_id, good_id)
        self.assertEqual(len(list_scans(self.database)), 2)

    def test_quotes_and_sql_like_text_remain_literal_data(self):
        scan = sample_scan()
        scan["folder"] = "João'); DROP TABLE scans; --"
        scan["files"][0]["path"] = "cópia'); DELETE FROM files; --.txt"

        scan_id = save_scan(self.database, scan)
        loaded = load_scan(self.database, scan_id)

        self.assertEqual(loaded["folder"], scan["folder"])
        self.assertIn(scan["files"][0], loaded["files"])
        self.assertEqual(len(list_scans(self.database)), 1)

    def test_first_failed_save_does_not_leave_partial_scan(self):
        invalid = sample_scan()
        invalid["files"][1]["size"] = -1

        with self.assertRaises(sqlite3.IntegrityError):
            save_scan(self.database, invalid)

        self.assertEqual(list_scans(self.database), [])
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM files").fetchone()[0], 0)

    def test_failed_initialization_rolls_back_schema_and_allows_retry(self):
        broken_schema = SCHEMA.replace("CREATE TABLE IF NOT EXISTS files", "INVALID SQL; CREATE TABLE IF NOT EXISTS files")

        with patch("zelunexo.storage.SCHEMA", broken_schema), self.assertRaises(sqlite3.OperationalError):
            save_scan(self.database, sample_scan())

        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
            self.assertEqual(connection.execute("PRAGMA application_id").fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)

        scan_id = save_scan(self.database, sample_scan())
        self.assertEqual(load_scan(self.database, scan_id)["folder"], sample_scan()["folder"])
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_existing_version_one_database_remains_writable_without_reinitialization(self):
        self.database.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.executescript(SCHEMA + f"PRAGMA application_id = {APPLICATION_ID}; PRAGMA user_version = 1;")

        with patch("zelunexo.storage.SCHEMA", "INVALID SQL;"):
            scan_id = save_scan(self.database, sample_scan())

        self.assertEqual(load_scan(self.database, scan_id)["folder"], sample_scan()["folder"])

    def test_concurrent_initialization_cannot_mix_database_metadata(self):
        sqlite_connect = sqlite3.connect
        competing_errors = []
        attempted = False
        first_connection = True
        database = self.database

        class InterleavedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                nonlocal attempted
                # Outro escritor chega entre as leituras dos metadados. Timeout
                # zero torna a disputa determinística, sem esperas artificiais.
                if sql == "PRAGMA user_version" and not attempted:
                    attempted = True
                    try:
                        save_scan(database, sample_scan())
                    except sqlite3.OperationalError as error:
                        competing_errors.append(str(error))
                return super().execute(sql, parameters)

        def interleaved_connect(*args, **kwargs):
            nonlocal first_connection
            kwargs["timeout"] = 0
            if first_connection:
                first_connection = False
                kwargs["factory"] = InterleavedConnection
            return sqlite_connect(*args, **kwargs)

        with patch("zelunexo.storage.sqlite3.connect", side_effect=interleaved_connect):
            first_id = save_scan(self.database, sample_scan())

        self.assertEqual(competing_errors, ["database is locked"])
        second_id = save_scan(self.database, sample_scan())
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(list_scans(self.database)), 2)

    def test_failed_version_write_rolls_back_schema_and_application_id(self):
        sqlite_connect = sqlite3.connect

        def deny_version_write(action, name, value, database, trigger):
            if action == sqlite3.SQLITE_PRAGMA and name == "user_version" and value == "1":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        def connect_without_version_write(*args, **kwargs):
            connection = sqlite_connect(*args, **kwargs)
            connection.set_authorizer(deny_version_write)
            return connection

        with patch("zelunexo.storage.sqlite3.connect", side_effect=connect_without_version_write):
            with self.assertRaises(sqlite3.DatabaseError):
                save_scan(self.database, sample_scan())

        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
            self.assertEqual(connection.execute("PRAGMA application_id").fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)

        self.assertIsInstance(save_scan(self.database, sample_scan()), int)

    def test_reading_missing_history_does_not_create_database_or_parent(self):
        for reader in [list_scans, lambda path: load_scan(path, 1)]:
            with self.subTest(reader=reader), self.assertRaises(ValueError):
                reader(self.database)
            self.assertFalse(self.database.exists())
            self.assertFalse(self.database.parent.exists())

    def test_read_connections_cannot_modify_history(self):
        save_scan(self.database, sample_scan())

        with connect(self.database) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM scans")

        self.assertEqual(len(list_scans(self.database)), 1)

    def test_missing_scan_has_clear_error(self):
        save_scan(self.database, sample_scan())

        with self.assertRaisesRegex(ValueError, "#999.*não encontrada"):
            load_scan(self.database, 999)

    def test_history_orders_newest_first_applies_limit_and_calculates_summary(self):
        ids = []
        for folder in ["Primeira", "Segunda", "Terceira"]:
            scan = sample_scan()
            scan["folder"] = folder
            ids.append(save_scan(self.database, scan))

        history = list_scans(self.database, limit=2)

        self.assertEqual([item["id"] for item in history], ids[-1:0:-1])
        self.assertEqual([item["folder"] for item in history], ["Terceira", "Segunda"])
        self.assertEqual(history[0]["scanned_files"], 2)
        self.assertEqual(history[0]["total_bytes"], 10)
        self.assertEqual(history[0]["duplicate_groups"], 1)
        self.assertEqual(history[0]["potential_bytes"], 5)
        self.assertEqual(history[0]["issues_count"], 1)
        self.assertEqual(history[0]["skipped_count"], 1)

    def test_foreign_sqlite_is_rejected_without_changing_its_bytes(self):
        foreign = self.directory / "outro-aplicativo.sqlite3"
        with closing(sqlite3.connect(foreign)) as connection, connection:
            connection.execute("CREATE TABLE notas (texto TEXT)")
            connection.execute("INSERT INTO notas VALUES (?)", ("Não alterar este banco",))
        original_bytes = foreign.read_bytes()

        with self.assertRaises(ValueError):
            save_scan(foreign, sample_scan())
        with self.assertRaises(ValueError):
            list_scans(foreign)

        self.assertEqual(foreign.read_bytes(), original_bytes)
        with closing(sqlite3.connect(foreign)) as connection:
            self.assertEqual(connection.execute("SELECT texto FROM notas").fetchone()[0], "Não alterar este banco")

    def test_foreign_sqlite_version_one_is_rejected_before_writing(self):
        foreign = self.directory / "outro-com-versão.sqlite3"
        with closing(sqlite3.connect(foreign)) as connection, connection:
            connection.executescript("""
                CREATE TABLE scans (
                    id INTEGER PRIMARY KEY, created_at TEXT, folder TEXT,
                    issues_json TEXT, skipped_json TEXT, excludes_json TEXT
                );
                CREATE TABLE files (
                    scan_id INTEGER, path TEXT, size INTEGER, sha256 TEXT, mtime_ns INTEGER
                );
                PRAGMA user_version = 1;
            """)
        original_bytes = foreign.read_bytes()

        with self.assertRaises(ValueError):
            save_scan(foreign, sample_scan())
        with self.assertRaises(ValueError):
            list_scans(foreign)

        self.assertEqual(foreign.read_bytes(), original_bytes)

    def test_unknown_future_schema_is_rejected_and_preserved(self):
        save_scan(self.database, sample_scan())
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("PRAGMA user_version = 999")
        original_bytes = self.database.read_bytes()

        with self.assertRaises(ValueError):
            save_scan(self.database, sample_scan())
        with self.assertRaises(ValueError):
            list_scans(self.database)

        self.assertEqual(self.database.read_bytes(), original_bytes)

    def test_empty_database_owned_by_another_application_is_preserved(self):
        foreign = self.directory / "outro-vazio.sqlite3"
        with closing(sqlite3.connect(foreign)) as connection, connection:
            connection.execute("PRAGMA application_id = 12345")
        original_bytes = foreign.read_bytes()

        with self.assertRaises(ValueError):
            save_scan(foreign, sample_scan())

        self.assertEqual(foreign.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
