"""Histórico SQLite: uma transação por análise, consultas parametrizadas."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from .domain import summarize

APPLICATION_ID = 0x52535452  # RSTR: identifica o banco deste aplicativo.

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    folder TEXT NOT NULL,
    issues_json TEXT NOT NULL,
    skipped_json TEXT NOT NULL,
    excludes_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    scan_id INTEGER NOT NULL REFERENCES scans(id),
    path TEXT NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    mtime_ns INTEGER NOT NULL,
    PRIMARY KEY (scan_id, path)
);
"""


@contextmanager
def connect(path: Path, *, create: bool = False):
    path = Path(path)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5)
    else:
        if not path.is_file():
            raise ValueError("Histórico não encontrado. Execute analisar primeiro.")
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if create:
            if version not in (0, 1):
                raise ValueError("Versão de banco incompatível com este Zelunexo.")
            if (version == 1 and application_id != APPLICATION_ID) or (
                version == 0 and application_id not in (0, APPLICATION_ID)
            ):
                raise ValueError("O arquivo SQLite pertence a outro aplicativo. Escolha outro --banco.")
            if version == 0:
                existing = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if existing:
                    raise ValueError("O arquivo SQLite pertence a outro aplicativo. Escolha outro --banco.")
                # executescript não abre uma transação: inclua o BEGIN no próprio
                # script para reverter tabelas e metadados juntos se algo falhar.
                with connection:
                    connection.executescript(
                        "BEGIN IMMEDIATE;\n" + SCHEMA
                        + f"PRAGMA application_id = {APPLICATION_ID}; PRAGMA user_version = 1;"
                    )
        elif version != 1 or application_id != APPLICATION_ID:
            raise ValueError("Este arquivo não é um histórico compatível do Zelunexo.")
        yield connection
    finally:
        connection.close()


def save_scan(path: Path, scan: dict) -> int:
    with connect(path, create=True) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO scans (created_at, folder, issues_json, skipped_json, excludes_json) VALUES (?, ?, ?, ?, ?)",
            (scan["created_at"], scan["folder"], json.dumps(scan["issues"], ensure_ascii=False),
             json.dumps(scan["skipped"], ensure_ascii=False), json.dumps(scan["excludes"], ensure_ascii=False)),
        )
        scan_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO files (scan_id, path, size, sha256, mtime_ns) VALUES (?, ?, ?, ?, ?)",
            [(scan_id, file["path"], file["size"], file["sha256"], file["mtime_ns"]) for file in scan["files"]],
        )
    return scan_id


def load_scan(path: Path, scan_id: int) -> dict:
    with connect(path) as connection:
        row = connection.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if row is None:
            raise ValueError(f"Análise #{scan_id} não encontrada no histórico.")
        files = connection.execute(
            "SELECT path, size, sha256, mtime_ns FROM files WHERE scan_id = ? ORDER BY path", (scan_id,)
        ).fetchall()
        return {
            "id": row["id"], "created_at": row["created_at"], "folder": row["folder"],
            "files": [dict(file) for file in files],
            "issues": json.loads(row["issues_json"]), "skipped": json.loads(row["skipped_json"]),
            "excludes": json.loads(row["excludes_json"]),
        }


def list_scans(path: Path, limit: int = 20) -> list[dict]:
    with connect(path) as connection:
        ids = [row[0] for row in connection.execute("SELECT id FROM scans ORDER BY id DESC LIMIT ?", (limit,))]
    summaries = []
    for scan_id in ids:
        scan = load_scan(path, scan_id)
        summaries.append({"id": scan_id, "folder": scan["folder"], "created_at": scan["created_at"], **summarize(scan)})
    return summaries
