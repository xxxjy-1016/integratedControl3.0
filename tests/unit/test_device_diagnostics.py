import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from integrated_control.bootstrap import build_device_diagnostics
from integrated_control.diagnostics_cli import execute_command


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DeviceDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = build_device_diagnostics(
            PROJECT_ROOT, mode="simulation"
        )
        self.assertTrue(self.controller.initialize().success)

    def tearDown(self) -> None:
        self.controller.shutdown()

    def execute(self, command: str) -> bool:
        with redirect_stdout(io.StringIO()):
            return execute_command(self.controller, command)

    def test_controls_all_non_motion_devices(self) -> None:
        for command in (
            "gz 20",
            "gopening 80",
            "gclose 60",
            "grotate -90",
            "pz 25",
            "tip tip-01",
            "aspirate 100",
            "dispense 40",
            "shome",
            "spin 1000 3 1000",
            "coverclose",
            "vopen",
            "status",
        ):
            self.assertTrue(self.execute(command), command)

        states = self.controller.device_states()
        self.assertEqual(20.0, states["gripper"].measurements["z"])
        self.assertEqual(-90.0, states["gripper"].measurements["rotation_deg"])
        self.assertEqual(25.0, states["pipette"].measurements["z"])
        self.assertEqual("tip-01", states["pipette"].measurements["tip_id"])
        self.assertEqual(60.0, states["pipette"].measurements["liquid_ul"])
        self.assertEqual(
            1, states["spin_coater"].measurements["last_recipe_steps"]
        )
        self.assertFalse(states["vacuum_station"].measurements["cover_open"])
        self.assertTrue(states["valve"].measurements["is_open"])
        self.assertIn("stage", states)
        self.assertIn("position_sensor", states)

        self.assertTrue(self.execute("tipeject"))
        self.assertTrue(self.execute("vclose"))
        states = self.controller.device_states()
        self.assertIsNone(states["pipette"].measurements["tip_id"])
        self.assertFalse(states["valve"].measurements["is_open"])

    def test_optional_arguments_and_command_validation(self) -> None:
        self.assertTrue(self.execute("gclose"))
        self.assertTrue(self.execute("tip tip-02"))
        self.assertTrue(self.execute("aspirate 20"))
        self.assertTrue(self.execute("dispense"))

        with self.assertRaisesRegex(ValueError, "最多需要一个"):
            self.execute("gclose 20 30")
        with self.assertRaisesRegex(ValueError, "吸头编号"):
            self.execute("tip")

    def test_motion_commands_delegate_to_stage_and_sensor_interfaces(self) -> None:
        for command in ("setx 2", "mx 10", "jx -3", "rx 12", "sx"):
            self.assertTrue(self.execute(command), command)

        self.assertEqual(12.0, self.controller.stage.get_raw_position("x"))
        self.assertEqual(10.0, self.controller.stage.get_position("x"))

    def test_shutdown_stops_every_registered_device(self) -> None:
        self.assertTrue(self.controller.shutdown().success)

        states = self.controller.device_states()
        self.assertEqual(
            {
                "stage",
                "position_sensor",
                "gripper",
                "pipette",
                "spin_coater",
                "vacuum_station",
                "valve",
            },
            set(states),
        )
        self.assertTrue(
            all(state.lifecycle == "OFFLINE" for state in states.values())
        )


if __name__ == "__main__":
    unittest.main()
