"""Regras puras: agrupar conteúdo igual e calcular bytes redundantes."""

from collections import defaultdict


def group_duplicates(files: list[dict]) -> list[dict]:
    buckets = defaultdict(list)
    for file in files:
        # Arquivos vazios não ajudam a encontrar espaço redundante.
        if file["size"] > 0:
            buckets[(file["size"], file["sha256"])].append(file["path"])
    groups = [
        {
            "sha256": digest,
            "size": size,
            "paths": sorted(paths),
            "potential_bytes": size * (len(paths) - 1),
        }
        for (size, digest), paths in buckets.items()
        if len(paths) > 1
    ]
    return sorted(groups, key=lambda group: (-group["potential_bytes"], group["paths"][0]))


def summarize(scan: dict) -> dict:
    groups = group_duplicates(scan["files"])
    return {
        "scanned_files": len(scan["files"]),
        "total_bytes": sum(file["size"] for file in scan["files"]),
        "duplicate_groups": len(groups),
        "redundant_files": sum(len(group["paths"]) - 1 for group in groups),
        "potential_bytes": sum(group["potential_bytes"] for group in groups),
        "skipped_count": len(scan["skipped"]),
        "issues_count": len(scan["issues"]),
    }
