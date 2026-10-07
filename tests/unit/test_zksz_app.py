import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from integrated_control.application.workflows.zksz import (
    BOTTLE_1_GRIPPER,
    BOTTLE_1_PIPETTE,
    GLASS_RELEASE_OPENING,
    GLASS_SLOT_2,
    GRIP_OPENING,
    SPIN_COATER_GRIPPER,
    SPIN_COATER_PIPETTE,
    TIP_1,
    ZkszWorkflow,
    run_zksz,
)
from integrated_control.bootstrap import build_application
from integrated_control.domain.results import ActionResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ZkszWorkflowTests(unittest.TestCase):
    """Group checks for zksz workflow tests."""
    def test_preserves_old_code_process_parameters(self) -> None:
        """Check preserves old code process parameters."""
        self.assertEqual((97.7, 1.8, 99.0), (TIP_1.x, TIP_1.y, TIP_1.pipette_z))
        self.assertEqual(
            (46.5, 65.5, 87.0),
            (
                SPIN_COATER_GRIPPER.x,
                SPIN_COATER_GRIPPER.y,
                SPIN_COATER_GRIPPER.gripper_z,
            ),
        )
        self.assertEqual(
            (56.0, 87.8, 18.0),
            (
                SPIN_COATER_PIPETTE.x,
                SPIN_COATER_PIPETTE.y,
                SPIN_COATER_PIPETTE.pipette_z,
            ),
        )
        self.assertEqual(
            (47.3, 11.0, 80.0),
            (
                BOTTLE_1_GRIPPER.x,
                BOTTLE_1_GRIPPER.y,
                BOTTLE_1_GRIPPER.gripper_z,
            ),
        )
        self.assertEqual(
            (56.7, 33.5, 45.0),
            (
                BOTTLE_1_PIPETTE.x,
                BOTTLE_1_PIPETTE.y,
                BOTTLE_1_PIPETTE.pipette_z,
            ),
        )
        self.assertEqual((88.7, 19.0, 87.5), (
            GLASS_SLOT_2.x,
            GLASS_SLOT_2.y,
            GLASS_SLOT_2.gripper_z,
        ))
        self.assertEqual(30.0, GRIP_OPENING)
        self.assertEqual(64.0, GLASS_RELEASE_OPENING)

    def test_full_workflow_runs_through_new_device_interfaces(self) -> None:
        """Check full workflow runs through new device interfaces."""
        application = build_application(PROJECT_ROOT, mode="simulation")
        with redirect_stdout(io.StringIO()):
            self.assertTrue(application.controller.start().success)
            result = run_zksz(application, sleep=lambda _seconds: None)

        self.assertTrue(result.success, result.message)
        states = application.controller.devices.states()
        self.assertAlmostEqual(88.7, states["stage"].measurements["logical_x"])
        self.assertAlmostEqual(19.0, states["stage"].measurements["logical_y"])
        self.assertEqual(1.0, states["gripper"].measurements["z"])
        self.assertEqual(0.0, states["pipette"].measurements["z"])
        self.assertIsNone(states["pipette"].measurements["tip_id"])
        self.assertEqual(0.0, states["pipette"].measurements["liquid_ul"])
        self.assertEqual(1, states["spin_coater"].measurements["last_recipe_steps"])
        self.assertFalse(states["valve"].measurements["is_open"])
        self.assertFalse(states["vacuum_station"].measurements["cover_open"])
        application.controller.shutdown()

    def test_bottle_opening_continues_without_cap_during_bench_test(self) -> None:
        """Check bottle opening continues without cap during bench test."""
        application = build_application(PROJECT_ROOT, mode="simulation")
        workflow = ZkszWorkflow(application, sleep=lambda _seconds: None)
        with redirect_stdout(io.StringIO()):
            self.assertTrue(application.controller.start().success)
            workflow._gripper.set_opening = lambda _opening: ActionResult.done(
                "No object on the bench",
                {"holding_object": False},
            )
            workflow._open_bottle(BOTTLE_1_GRIPPER, 360.0)

        state = workflow._gripper.get_state()
        self.assertEqual(-360.0, state.measurements["rotation_deg"])
        application.controller.shutdown()

    def test_workflow_disables_liquid_requirement_during_bench_test(self) -> None:
        """Check workflow disables liquid requirement during bench test."""
        application = build_application(PROJECT_ROOT, mode="simulation")
        workflow = ZkszWorkflow(application, sleep=lambda _seconds: None)
        observed: dict[str, bool] = {}
        with redirect_stdout(io.StringIO()):
            self.assertTrue(application.controller.start().success)
            workflow._pipette.attach_tip("dry-run-tip")
            original_aspirate = workflow._pipette.aspirate

            def record_policy(
                volume_ul: float,
                *,
                require_liquid_detection: bool = True,
            ) -> ActionResult:
                """Record policy."""
                observed["required"] = require_liquid_detection
                return original_aspirate(
                    volume_ul,
                    require_liquid_detection=require_liquid_detection,
                )

            workflow._pipette.aspirate = record_policy  # type: ignore[method-assign]
            workflow._aspirate(BOTTLE_1_PIPETTE, 100.0)

        self.assertFalse(observed["required"])
        application.controller.shutdown()


if __name__ == "__main__":
    unittest.main()
