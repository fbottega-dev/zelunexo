"""Regras de agrupamento: nomes não definem igualdade de conteúdo."""

import unittest

from rastro.domain import group_duplicates, summarize


def file_record(path, size, digest):
    return {"path": path, "size": size, "sha256": digest, "mtime_ns": 0}


class DuplicateGroupsTests(unittest.TestCase):
    def test_different_names_with_equal_content_form_one_group(self):
        records = [
            file_record("viagem/original.jpg", 7, "a" * 64),
            file_record("backup/cópia.jpg", 7, "a" * 64),
            file_record("outro.jpg", 7, "b" * 64),
        ]

        groups = group_duplicates(records)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["paths"], ["backup/cópia.jpg", "viagem/original.jpg"])
        self.assertEqual(groups[0]["potential_bytes"], 7)

    def test_name_and_size_are_not_enough_to_mark_duplicates(self):
        records = [
            file_record("a/foto.jpg", 50, "a" * 64),
            file_record("b/foto.jpg", 50, "b" * 64),
        ]

        self.assertEqual(group_duplicates(records), [])

    def test_equal_hash_with_different_sizes_does_not_form_group(self):
        records = [file_record("a", 1, "a" * 64), file_record("b", 2, "a" * 64)]

        self.assertEqual(group_duplicates(records), [])

    def test_empty_files_are_not_space_savings(self):
        records = [file_record("a", 0, "a" * 64), file_record("b", 0, "a" * 64)]

        self.assertEqual(group_duplicates(records), [])

    def test_savings_keep_one_copy_and_groups_have_stable_order(self):
        records = [
            file_record("z/2", 10, "c" * 64),
            file_record("b/3", 10, "b" * 64),
            file_record("a/2", 20, "a" * 64),
            file_record("b/1", 10, "b" * 64),
            file_record("z/1", 10, "c" * 64),
            file_record("a/1", 20, "a" * 64),
            file_record("b/2", 10, "b" * 64),
        ]

        groups = group_duplicates(records)

        self.assertEqual([group["paths"] for group in groups], [
            ["a/1", "a/2"], ["b/1", "b/2", "b/3"], ["z/1", "z/2"],
        ])
        self.assertEqual([group["potential_bytes"] for group in groups], [20, 20, 10])
        self.assertEqual(group_duplicates(list(reversed(records))), groups)

    def test_summary_includes_empty_files_skips_and_errors(self):
        scan = {
            "files": [
                file_record("a", 10, "a" * 64),
                file_record("b", 10, "a" * 64),
                file_record("c", 10, "a" * 64),
                file_record("único", 7, "b" * 64),
                file_record("vazio", 0, "c" * 64),
            ],
            "issues": [{"path": "sem-acesso", "message": "Negado"}],
            "skipped": [{"path": ".git", "reason": "Padrão de exclusão"}],
        }

        self.assertEqual(summarize(scan), {
            "scanned_files": 5, "total_bytes": 37, "duplicate_groups": 1,
            "redundant_files": 2, "potential_bytes": 20, "skipped_count": 1,
            "issues_count": 1,
        })

    def test_empty_scan_has_zero_totals(self):
        summary = summarize({"files": [], "issues": [], "skipped": []})

        self.assertTrue(summary)
        self.assertTrue(all(value == 0 for value in summary.values()))


if __name__ == "__main__":
    unittest.main()
