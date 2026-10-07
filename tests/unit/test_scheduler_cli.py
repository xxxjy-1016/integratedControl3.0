import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from integrated_control import diagnostics_cli
from integrated_control.application.scheduler import cli
from integrated_control.application.scheduler.algorithm import AlgorithmConfig
from integrated_control.application.scheduler.contracts import TaskPlan
from integrated_control.application.scheduler.decision_preview import OnlineTiming
from integrated_control.application.scheduler.experiment_manager import ExperimentManager


class SchedulerCliTests(unittest.TestCase):
    """Group checks for scheduler cli tests."""
    def test_dry_compiles_shared_experiment_and_plans_full_batch(self):
        """Check dry compiles shared experiment and plans full batch."""
        original = ExperimentManager._compile_zksz
        with patch.object(ExperimentManager, "_compile_zksz", wraps=original) as compile_tasks:
            plan = cli.dry(num_glass=2, num_heater=1,
                timing=OnlineTiming(2, 1, 5, 12, 2, 2, 0, 0),
                config=AlgorithmConfig("exact", time_limit_s=1))
        compile_tasks.assert_called_once()
        self.assertTrue(plan.feasible, plan.errors)
        self.assertTrue(plan.proven_optimal)
        self.assertEqual(4, len(plan.commands))
        by_id = {c.task_id: c for c in plan.commands}
        for n in range(2):
            put, pick = by_id[f"dry:{n}:step1"], by_id[f"dry:{n}:step2"]
            self.assertGreaterEqual(pick.start - put.end, 5)
            self.assertLessEqual(pick.start - put.end, 12)

    def test_diagnostic_command_line_bypasses_device_construction(self):
        """Check diagnostic command line bypasses device construction."""
        with patch("sys.argv", ["debug", "dry", "--algorithm", "exact", "--num-glass", "1",
                                  "--pickup-offset-min-s", "0", "--pickup-offset-max-s", "0"]), \
             patch.object(diagnostics_cli, "build_device_diagnostics") as build, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, diagnostics_cli.main())
        build.assert_not_called()
        self.assertIn("dry:0:step1", output.getvalue())

    def test_interactive_gantt_does_not_access_controller(self):
        """Check interactive gantt does not access controller."""
        with redirect_stdout(io.StringIO()) as output:
            self.assertTrue(diagnostics_cli.execute_command(None,
                "gantt --algorithm exact --num-glass 1 --cols 40 "
                "--pickup-offset-min-s 0 --pickup-offset-max-s 0"))
        self.assertIn("[gantt]", output.getvalue())
        self.assertIn("#", output.getvalue())

    def test_help_and_bad_arguments_do_not_close_interactive_session(self):
        """Check help and bad arguments do not close interactive session."""
        with redirect_stdout(io.StringIO()), patch("sys.stderr", new_callable=io.StringIO):
            self.assertTrue(diagnostics_cli.execute_command(None, "dry --help"))
            self.assertTrue(diagnostics_cli.execute_command(None, "dry --algorithm unknown"))

    def test_infeasible_plan_is_reported_as_failure(self):
        """Check infeasible plan is reported as failure."""
        with redirect_stdout(io.StringIO()) as output:
            code = cli.main(["dry", "--algorithm", "exact", "--num-glass", "1",
                             "--heat-min-s", "0", "--heat-max-s", "0",
                             "--pickup-offset-min-s", "1", "--pickup-offset-max-s", "1"])
        self.assertEqual(1, code)
        self.assertIn("feasible=False", output.getvalue())

    def test_empty_and_invalid_gantt(self):
        """Check empty and invalid gantt."""
        empty = TaskPlan((), True, True, "exact", 0)
        self.assertEqual("(空计划)", cli.gantt(empty))
        with self.assertRaises(ValueError):
            cli.gantt(empty, cols=0)

    def test_batch_config_overrides_and_invalid_config(self):
        """Check batch config overrides and invalid config."""
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            config = Path(directory) / "batch.json"
            config.write_text(json.dumps({"time_step1": 3, "time_step2": 1,
                "heat_time_min": 5, "heat_time_max": 12, "num_heater": 1, "num_glass": 4}),
                encoding="utf-8")
            with redirect_stdout(io.StringIO()) as output:
                result = cli.main(["dry", "--algorithm", "exact", "--batch-config", str(config),
                                   "--num-glass", "1", "--step1-s", "2",
                                   "--pickup-offset-min-s", "0", "--pickup-offset-max-s", "0"])
            self.assertEqual(0, result)
            self.assertIn("tasks=2", output.getvalue())
            self.assertIn("duration=2.000s", output.getvalue())
            config.write_text("{bad json", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(2, cli.main(["dry", "--algorithm", "exact", "--batch-config", str(config)]))

    def test_command_line_requires_explicit_pickup_offsets(self):
        """Check dry rejects a command that omits either pickup-event offset."""
        with redirect_stdout(io.StringIO()) as output:
            result = cli.main(["dry", "--algorithm", "exact", "--num-glass", "1"])
        self.assertEqual(2, result)
        self.assertIn("explicit --pickup-offset-min-s and --pickup-offset-max-s", output.getvalue())



if __name__ == "__main__":
    unittest.main()
