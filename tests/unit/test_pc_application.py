import unittest
from pathlib import Path

from integrated_control.bootstrap import build_application, build_device_diagnostics
from integrated_control.domain.enums import SystemState
from integrated_control.domain.errors import ConfigurationError
from integrated_control.domain.models import SpinStep


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PcApplicationStartupTests(unittest.TestCase):
    """Group checks for pc application startup tests."""
    def test_legacy_hardware_mode_is_rejected(self) -> None:
        """Check legacy hardware mode is rejected."""
        with self.assertRaisesRegex(ConfigurationError, "Unsupported"):
            build_device_diagnostics(PROJECT_ROOT, mode="legacy_hardware")

    def test_simulated_application_reaches_ready_state(self) -> None:
        """Check simulated application reaches ready state."""
        application = build_application(PROJECT_ROOT, mode="simulation")

        self.assertEqual(
            {"x": -0.0075, "y": -0.02},
            application.coordinates["stage_origin_offset"],
        )

        result = application.controller.start()

        self.assertTrue(result.success)
        self.assertEqual(SystemState.READY, application.controller.snapshot.state)
        self.assertEqual(9, result.measurements["device_count"])
        states = application.controller.devices.states()
        self.assertTrue(all(state.lifecycle == "READY" for state in states.values()))

        camera = application.controller.devices.get("camera")
        located = camera.locate("spin_coater", "groove")  # type: ignore[attr-defined]
        self.assertTrue(located.success)
        self.assertEqual(48.5, located.measurements["x"])
        self.assertEqual(64.5, located.measurements["y"])

        application.controller.shutdown()
        self.assertEqual(SystemState.STOPPED, application.controller.snapshot.state)

    def test_simulated_spin_coater_runs_recipe(self) -> None:
        """Check simulated spin coater runs recipe."""
        application = build_application(PROJECT_ROOT, mode="simulation")
        application.controller.start()
        spin_coater = application.controller.devices.get("spin_coater")
        recipe = [SpinStep(4700, 42.0)]

        self.assertTrue(spin_coater.run(recipe).success)  # type: ignore[attr-defined]
        self.assertEqual(
            1,
            spin_coater.get_state().measurements["last_recipe_steps"],
        )


if __name__ == "__main__":
    unittest.main()
