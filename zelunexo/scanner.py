"""Percorre uma pasta sem escrever nela; cada arquivo é lido em blocos."""

from datetime import datetime, timezone
from fnmatch import fnmatchcase
import hashlib
import os
from pathlib import Path
import stat

DEFAULT_EXCLUDES = (".git", "node_modules", ".venv", "__pycache__")
BLOCK_SIZE = 1024 * 1024


def is_link(info: os.stat_result) -> bool:
    # Reparse points incluem junctions no Windows, além de links simbólicos.
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def signature(info: os.stat_result) -> tuple:
    # No Windows, lstat e fstat podem atribuir significados diferentes a ctime.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def digest_file(path: Path, expected: os.stat_result) -> str:
    """Recusa trocas/alterações comuns entre a listagem e o fim da leitura."""
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or signature(before) != signature(expected):
            raise OSError("Arquivo mudou antes da leitura; execute outra análise.")
        digest = hashlib.sha256()
        while chunk := stream.read(BLOCK_SIZE):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    if (is_link(final) or signature(after) != signature(before) or signature(final) != signature(before)
            or after.st_ctime_ns != before.st_ctime_ns or final.st_ctime_ns != expected.st_ctime_ns):
        raise OSError("Arquivo mudou durante a leitura; execute outra análise.")
    return digest.hexdigest()


def excluded(relative: str, patterns: list[str], *, is_directory: bool = False) -> bool:
    # Sem barra, o padrão vale para qualquer componente. Com barra, para o caminho relativo.
    for pattern in patterns:
        if pattern.endswith("/"):
            if not is_directory:
                continue
            pattern = pattern[:-1]
        matches = (
            fnmatchcase(relative, pattern)
            if "/" in pattern
            else any(fnmatchcase(part, pattern) for part in relative.split("/"))
        )
        if matches:
            return True
    return False


def scan_folder(root: Path, excludes: list[str] | None = None) -> dict:
    root = Path(root).absolute()
    info = root.lstat()
    if is_link(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError("Escolha uma pasta real, sem link simbólico ou junction na raiz.")
    patterns = list(DEFAULT_EXCLUDES) + list(excludes or [])
    if any(not pattern or "\\" in pattern for pattern in patterns):
        raise ValueError("Use padrões não vazios e barras / em --ignorar.")
    result = {
        "id": None,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "folder": root.name or str(root.anchor),
        "files": [],
        "issues": [],
        "skipped": [],
        "excludes": patterns,
    }
    identities = set()
    pending = [(root, info)]
    while pending:
        directory, expected_directory = pending.pop()
        relative_directory = directory.relative_to(root).as_posix()
        try:
            current = directory.lstat()
            if is_link(current) or (current.st_dev, current.st_ino) != (
                expected_directory.st_dev, expected_directory.st_ino
            ):
                raise OSError("Pasta mudou durante a análise; execute novamente.")
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda entry: entry.name)
        except OSError as error:
            result["issues"].append({"path": relative_directory, "message": error.strerror or str(error)})
            continue
        for entry in children:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            if excluded(relative, patterns):
                result["skipped"].append({"path": relative, "reason": "Padrão de exclusão"})
                continue
            try:
                info = path.lstat()
                if is_link(info):
                    result["skipped"].append({"path": relative, "reason": "Link ou junction"})
                elif stat.S_ISDIR(info.st_mode):
                    if excluded(relative, patterns, is_directory=True):
                        result["skipped"].append({"path": relative, "reason": "Padrão de exclusão"})
                    else:
                        pending.append((path, info))
                elif stat.S_ISREG(info.st_mode):
                    identity = (info.st_dev, info.st_ino)
                    if info.st_ino and identity in identities:
                        result["skipped"].append({"path": relative, "reason": "Hard link já contado"})
                        continue
                    digest = digest_file(path, info)
                    identities.add(identity)
                    result["files"].append({
                        "path": relative, "size": info.st_size,
                        "sha256": digest, "mtime_ns": info.st_mtime_ns,
                    })
                else:
                    result["skipped"].append({"path": relative, "reason": "Arquivo especial"})
            except OSError as error:
                result["issues"].append({"path": relative, "message": error.strerror or str(error)})
    result["files"].sort(key=lambda file: file["path"])
    result["issues"].sort(key=lambda issue: issue["path"])
    result["skipped"].sort(key=lambda item: item["path"])
    return result
