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
    def test_batch_schedule_is_feasible_and_covers_all_glass(self) -> None:
        application = build_application(PROJECT_ROOT, mode="simulation")
        batch = BatchParams(
            time_step1=2.0,
            time_step2=1.0,
            heat_time_min=5.0,
            heat_time_max=12.0,
            num_heater=2,
            num_glass=5,
        )
        with redirect_stdout(io.StringIO()):
            plan = run_batch_zksz(application, batch=batch, mode="simulate")

        self.assertTrue(plan.feasible, plan.errors)
        step1_cmds = [c for c in plan.commands if c.kind == "step1"]
        step2_cmds = [c for c in plan.commands if c.kind == "step2"]
        self.assertEqual(5, len(step1_cmds))
        self.assertEqual(5, len(step2_cmds))
        self.assertEqual(set(range(5)), {c.n for c in step1_cmds})
        self.assertEqual(set(range(5)), {c.n for c in step2_cmds})

    def test_step1_and_step2_drive_simulated_devices(self) -> None:
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
