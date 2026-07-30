import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import contract_stats


class ContractStatsFilenameTests(unittest.TestCase):
    def test_missing_file_warning_uses_awards_filename(self):
        with tempfile.TemporaryDirectory() as data_dir_name:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                contract_stats.process_fiscal_year(
                    2026,
                    Path(data_dir_name),
                )

        self.assertIn("nasa_awards_2026.csv not found", output.getvalue())


if __name__ == "__main__":
    unittest.main()
