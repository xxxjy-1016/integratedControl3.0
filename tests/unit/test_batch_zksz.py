import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from integrated_control.application.workflows.batch_zksz import (
    BatchParams,
    run_batch_zksz,
)
from integrated_control.application.workflows.zksz import ZkszWorkflow
from integrated_control.bootstrap import build_application


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class BatchZkszTests(unittest.TestCase):
    """Group checks for batch zksz tests."""
    def test_process_parameters_are_validated_at_construction(self):
        """Check process parameters are validated at construction."""
        invalid = [
            {"time_step1": 0}, {"time_step2": -1}, {"time_step1": float("nan")},
            {"heat_time_max": float("inf")}, {"heat_time_min": -1},
            {"heat_time_min": 10, "heat_time_max": 9}, {"time_step1": "2"},
            {"num_glass": -1}, {"num_glass": 1.5}, {"num_glass": True},
            {"num_heater": 0}, {"num_heater": False},
            {"method": "unknown"}, {"beam_width": 0}, {"time_limit": float("nan")},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                BatchParams(**values)

    def test_counts_resolve_from_coordinates_and_are_validated(self):
        """Check counts resolve from coordinates and are validated."""
        unresolved = BatchParams()
        resolved = unresolved.resolve({"glass_platform": {"slots": [1, 2, 3]},
                                       "stations": {"heater": [1, 2]}})
        self.assertIsNone(unresolved.num_glass)
        self.assertEqual(3, resolved.num_glass)
        self.assertEqual(2, resolved.num_heater)
        with self.assertRaises(ValueError):
            unresolved.resolve({})
        explicit = BatchParams(num_glass=0, num_heater=1).resolve({})
        self.assertEqual(0, explicit.num_glass)
        self.assertEqual(1, explicit.num_heater)

    def test_parameter_helpers_preserve_process_meaning(self):
        """Check parameter helpers preserve process meaning."""
        batch = BatchParams(time_step2=3, heat_time_min=5, heat_time_max=8,
                            num_glass=2, num_heater=1)
        self.assertEqual(3, batch.slack)
        self.assertNotIn("method", batch.to_dict())
        self.assertEqual(3, batch.to_dict()["time_step2"])

    def test_online_batch_receives_batchparams_without_old_params_conversion(self):
        """Check online batch receives batchparams without old params conversion."""
        from unittest.mock import patch
        from integrated_control.application.scheduler.decision_preview import OnlineTiming
        application = build_application(PROJECT_ROOT, mode="simulation")
        batch = BatchParams(time_step1=2, time_step2=1, heat_time_min=5,
                            heat_time_max=12, num_glass=1, num_heater=1)
        timing = OnlineTiming(2, 1, 5, 12, 2, 2, 0, 0)
        with patch("integrated_control.application.workflows.batch_zksz._run_experiment") as run:
            run_batch_zksz(application, batch=batch, mode="online", online_timing=timing)
        self.assertIsInstance(run.call_args.args[1], BatchParams)
        self.assertEqual(batch, run.call_args.args[1])

    def test_removed_modes_rejected_before_device_access(self):
        """Check removed modes rejected before device access."""
        for mode in ("dry", "simulate", "realtime"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                run_batch_zksz(None, mode=mode)

    def test_step1_and_step2_drive_simulated_devices(self) -> None:
        """Check step1 and step2 drive simulated devices."""
        application = build_application(PROJECT_ROOT, mode="simulation")
        self.assertTrue(application.controller.start().success)
        workflow = ZkszWorkflow(application, sleep=lambda _seconds: None)
        heater = application.controller.devices.get("heater")

        with redirect_stdout(io.StringIO()):
            workflow.step1(0, 1)
            slots = heater.get_state().measurements["slots"]
            self.assertEqual("glass-0", slots[1])

            workflow.step2(0, 1)
            slots = heater.get_state().measurements["slots"]
            self.assertIsNone(slots[1])

        application.controller.shutdown()

    def test_pose_mapping_uses_configured_coordinates(self) -> None:
        """Check pose mapping uses configured coordinates."""
        application = build_application(PROJECT_ROOT, mode="simulation")
        workflow = ZkszWorkflow(application, sleep=lambda _seconds: None)

        # coordinates.yaml: glass_platform.slots[0] -> id=1, x=95.3, y=19.0
        glass = workflow.glass_pose(0)
        self.assertAlmostEqual(95.3, glass.x)
        self.assertAlmostEqual(19.0, glass.y)

        # coordinates.yaml: stations.heater[0] -> step=1, position=1, x=0.0, y=6.0
        heater = workflow.heater_pose(1)
        self.assertAlmostEqual(0.0, heater.x)
        self.assertAlmostEqual(6.0, heater.y)


if __name__ == "__main__":
    unittest.main()
