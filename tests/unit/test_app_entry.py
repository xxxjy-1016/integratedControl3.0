import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from integrated_control import app
from integrated_control.domain.results import ActionResult


class AppEntryTests(unittest.TestCase):
    """Group checks for app entry tests."""
    def application(self):
        """Application."""
        controller = Mock()
        controller.start.return_value = ActionResult.done()
        return SimpleNamespace(controller=controller, coordinates={
            "glass_platform": {"slots": [1]}, "stations": {"heater": [1]}})

    def test_default_single_lifecycle_and_start_failure(self):
        """Check default single lifecycle and start failure."""
        for started in (True, False):
            application = self.application()
            application.controller.start.return_value = (ActionResult.done() if started else
                                                         ActionResult.failed("START", "failed"))
            with self.subTest(started=started), redirect_stdout(io.StringIO()), \
                 patch.object(app, "build_application", return_value=application), \
                 patch.object(app, "run_zksz", return_value=ActionResult.done()) as single, \
                 patch.object(app, "run_batch_zksz") as batch:
                self.assertEqual(0 if started else 1, app.main([]))
            self.assertEqual(int(started), single.call_count)
            batch.assert_not_called()
            application.controller.shutdown.assert_called_once()

    def test_batch_dispatch_and_shutdown_on_failure(self):
        """Check batch dispatch and shutdown on failure."""
        with TemporaryDirectory() as directory:
            process, timing = Path(directory) / "batch.json", Path(directory) / "timing.json"
            process.write_text(json.dumps({"heat_time_min": 5, "heat_time_max": 12}), encoding="utf-8")
            timing.write_text(json.dumps({"step1_bound_s": 2, "step2_bound_s": 1,
                "heat_min_s": 5, "heat_max_s": 12, "put_offset_min_s": 2, "put_offset_max_s": 2,
                "pickup_offset_min_s": 0, "pickup_offset_max_s": 0}), encoding="utf-8")
            for failed in (False, True):
                application = self.application()
                with self.subTest(failed=failed), redirect_stdout(io.StringIO()), \
                     patch.object(app, "build_application", return_value=application) as build, \
                     patch.object(app, "run_zksz") as single, \
                     patch.object(app, "run_batch_zksz", return_value=SimpleNamespace(success=True),
                                  side_effect=RuntimeError("failed") if failed else None) as batch:
                    result = app.batch_main(["--device-mode", "simulation", "--algorithm", "beam",
                        "--batch-config", str(process), "--timing-config", str(timing)])
                self.assertEqual(1 if failed else 0, result)
                build.assert_called_once_with(mode="simulation")
                single.assert_not_called()
                self.assertEqual(1, batch.call_args.kwargs["batch"].num_glass)
                self.assertEqual("beam", batch.call_args.kwargs["algorithm_config"].method)
                self.assertIsNone(batch.call_args.kwargs["algorithm_config"].lookahead_depth)
                application.controller.shutdown.assert_called_once()

    def test_batch_missing_inputs_rejected_without_device_construction(self):
        """Check batch missing inputs rejected without device construction."""
        with patch.object(app, "build_application") as build, \
             patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as error:
            app.main(["--workflow", "batch"])
        self.assertEqual(2, error.exception.code)
        build.assert_not_called()
