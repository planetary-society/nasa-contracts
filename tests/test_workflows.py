import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DAILY_WORKFLOW = ROOT / ".github" / "workflows" / "daily-fetch.yaml"


class DailyWorkflowTests(unittest.TestCase):
    def test_daily_refresh_exports_current_year_award_stats(self):
        workflow = yaml.load(
            DAILY_WORKFLOW.read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        job = workflow["jobs"]["fetch_data"]
        steps = job["steps"]
        steps_by_name = {step["name"]: step for step in steps}

        self.assertEqual({"contents": "write"}, job["permissions"])

        expected_actions = {
            "Checkout repository": "actions/checkout",
            "Set up Python": "actions/setup-python",
            "Commit updated CSV files": "EndBug/add-and-commit",
        }
        for step_name, action in expected_actions.items():
            repository, separator, revision = steps_by_name[step_name]["uses"].partition("@")
            self.assertEqual(action, repository)
            self.assertEqual("@", separator)
            self.assertRegex(revision, r"^[0-9a-f]{40}$")

        install = steps_by_name["Install dependencies"]["run"]
        self.assertIn(
            "python -m pip install --requirement requirements.txt",
            install,
        )

        compute = steps_by_name["Compute fiscal years and fetch contract data"]["run"]
        self.assertIn(
            'echo "FISCAL_YEAR=$FISCAL_YEAR" >> "$GITHUB_ENV"',
            compute,
        )
        self.assertIn("python fetch-contracts.py -fy $FY1 $FY2 $FY3", compute)

        expected_stats = (
            'python award_stats.py --fys "$FISCAL_YEAR" '
            '--export "data/nasa_new_award_stats_${FISCAL_YEAR}.csv"'
        )
        stats = steps_by_name["Export current fiscal year award statistics"]["run"]
        self.assertEqual(expected_stats, stats.strip())

        commit = steps_by_name["Commit updated CSV files"]
        self.assertEqual("data/*.csv", commit["with"]["add"])

        step_names = [step["name"] for step in steps]
        self.assertLess(
            step_names.index("Compute fiscal years and fetch contract data"),
            step_names.index("Export current fiscal year award statistics"),
        )
        self.assertLess(
            step_names.index("Export current fiscal year award statistics"),
            step_names.index("Commit updated CSV files"),
        )


if __name__ == "__main__":
    unittest.main()
