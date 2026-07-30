import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "filter_by_project.py"
SPEC = importlib.util.spec_from_file_location("filter_by_project", SCRIPT_PATH)
filter_by_project = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(filter_by_project)

PROJECTS = {
    "Alpha": ["Alpha", "~legacy"],
    "Beta": ["Beta mission"],
}
ROWS = [
    {
        "Contractor": "Alpha Corporation",
        "Contract/Mod Number": "A1 Modification 0 (Base Record)",
        "Award Type": "Contract",
        "Description": "Unrelated work",
    },
    {
        "Contractor": "Supplier",
        "Contract/Mod Number": "A2 Modification 0 (Base Record)",
        "Award Type": "Contract",
        "Description": "Alpha payload",
    },
    {
        "Contractor": "Supplier",
        "Contract/Mod Number": "A3 Modification 0 (Base Record)",
        "Award Type": "Contract",
        "Description": "Alpha legacy payload",
    },
    {
        "Contractor": "Supplier",
        "Contract/Mod Number": "B1 Modification 0 (Base Record)",
        "Award Type": "Grant",
        "Description": "Beta mission study",
    },
    {
        "Contractor": "Supplier",
        "Contract/Mod Number": "AB1 Modification 0 (Base Record)",
        "Award Type": "Grant",
        "Description": "Alpha and Beta mission payloads",
    },
]


class FilterByProjectPerformanceTests(unittest.TestCase):
    def test_main_reads_each_year_once_for_all_projects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir()
            for year in (2026, 2025, 2024, 2023):
                year_rows = pd.DataFrame(ROWS)
                if year == 2025:
                    year_rows = year_rows[
                        [
                            "Description",
                            "Award Type",
                            "Contract/Mod Number",
                            "Contractor",
                        ]
                    ]
                year_rows.to_csv(data_dir / f"nasa_awards_{year}.csv", index=False)

            original_read_csv = pd.read_csv
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.object(filter_by_project, "PROJECTS", PROJECTS),
                    patch.object(filter_by_project, "CHUNK_SIZE", 2),
                    patch.object(
                        filter_by_project.pd,
                        "read_csv",
                        wraps=original_read_csv,
                    ) as read_csv,
                ):
                    filter_by_project.main()
            finally:
                os.chdir(previous_cwd)

            input_reads = [
                call
                for call in read_csv.call_args_list
                if Path(call.args[0]).parent.name == "data"
            ]
            self.assertEqual(len(input_reads), 4)

            years = "2026_2025_2024_2023"
            alpha_contracts = original_read_csv(
                root / "filtered" / f"Alpha_{years}_contracts.csv"
            )
            alpha_grants = original_read_csv(
                root / "filtered" / f"Alpha_{years}_grants.csv"
            )
            beta_grants = original_read_csv(
                root / "filtered" / f"Beta_{years}_grants.csv"
            )

            columns = [
                "Year",
                "Contractor",
                "Contract",
                "Mod Number",
                "Award Type",
                "Description",
            ]
            pd.testing.assert_frame_equal(
                alpha_contracts,
                pd.DataFrame(
                    [
                        [
                            2026,
                            "Supplier",
                            "A2",
                            "Modification 0 (Base Record)",
                            "Contract",
                            "Alpha payload",
                        ]
                    ],
                    columns=columns,
                ),
            )
            pd.testing.assert_frame_equal(
                alpha_grants,
                pd.DataFrame(
                    [
                        [
                            2026,
                            "Supplier",
                            "AB1",
                            "Modification 0 (Base Record)",
                            "Grant",
                            "Alpha and Beta mission payloads",
                        ]
                    ],
                    columns=columns,
                ),
            )
            pd.testing.assert_frame_equal(
                beta_grants,
                pd.DataFrame(
                    [
                        [
                            2026,
                            "Supplier",
                            "AB1",
                            "Modification 0 (Base Record)",
                            "Grant",
                            "Alpha and Beta mission payloads",
                        ],
                        [
                            2026,
                            "Supplier",
                            "B1",
                            "Modification 0 (Base Record)",
                            "Grant",
                            "Beta mission study",
                        ],
                    ],
                    columns=columns,
                ),
            )

    def test_project_matches_are_yielded_one_chunk_at_a_time(self):
        iterator = getattr(filter_by_project, "iter_project_matches_for_year", None)
        self.assertIsNotNone(iterator)

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "contracts.csv"
            pd.DataFrame(ROWS).to_csv(csv_path, index=False)
            patterns, candidate_pattern = filter_by_project.compile_project_patterns(
                PROJECTS
            )

            with patch.object(filter_by_project, "CHUNK_SIZE", 2):
                yielded = [
                    (project_name, matches["Contract/Mod Number"].tolist())
                    for project_name, matches in iterator(
                        2026,
                        csv_path,
                        patterns,
                        candidate_pattern,
                    )
                ]

        self.assertEqual(
            yielded,
            [
                ("Alpha", ["A2 Modification 0 (Base Record)"]),
                ("Beta", ["B1 Modification 0 (Base Record)"]),
                ("Alpha", ["AB1 Modification 0 (Base Record)"]),
                ("Beta", ["AB1 Modification 0 (Base Record)"]),
            ],
        )

    def test_filter_mask_uses_row_positions_when_index_labels_repeat(self):
        rows = pd.DataFrame(
            [
                {"Contractor": "Supplier", "Description": "Alpha payload"},
                {"Contractor": "Supplier", "Description": "Unrelated work"},
            ],
            index=[7, 7],
        )

        mask = filter_by_project.build_filter_mask(rows, ["Alpha"])

        self.assertEqual(mask.tolist(), [True, False])


if __name__ == "__main__":
    unittest.main()
