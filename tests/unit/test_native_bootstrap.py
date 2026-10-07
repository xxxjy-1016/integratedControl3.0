import json
import unittest
from pathlib import Path

from integrated_control.bootstrap import build_native_devices
from integrated_control.infrastructure.drivers.native import (
    GripperDriver,
    PipetteDriver,
    PositionSensorDriver,
    SpinCoaterDriver,
    StageDriver,
    VacuumStationDriver,
    ValveDriver,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class NativeBootstrapTests(unittest.TestCase):
    """Group checks for native bootstrap tests."""
    def test_coordinates_match_old_code_calibration(self) -> None:
        """Check coordinates match old code calibration."""
        coordinates = json.loads(
            (PROJECT_ROOT / "config" / "coordinates.yaml").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            {"x": -0.0075, "y": -0.02},
            coordinates["stage_origin_offset"],
        )
        self.assertEqual(
            {"gripper_z": 1.0, "pipette_z": 0.0},
            coordinates["safe_pose"],
        )
        spin_coater = coordinates["stations"]["spin_coater"]
        self.assertEqual(
            {"x": 48.5, "y": 64.5, "gripper_z": 87.1, "pipette_z": 0.0},
            spin_coater["gripper"],
        )
        self.assertEqual(
            {"x": 57.2, "y": 90.0, "gripper_z": 0.0, "pipette_z": 18.0},
            spin_coater["pipette"],
        )
        self.assertEqual(3, len(coordinates["stations"]["bottles"]))
        self.assertEqual(8, len(coordinates["stations"]["heater"]))

        slots = coordinates["glass_platform"]["slots"]
        self.assertEqual(list(range(1, 25)), [slot["id"] for slot in slots])
        self.assertEqual((95.3, 19.0, 87.5), (
            slots[0]["x"], slots[0]["y"], slots[0]["gripper_z"]
        ))
        self.assertEqual((72.9, 86.7, 87.5), (
            slots[-1]["x"], slots[-1]["y"], slots[-1]["gripper_z"]
        ))

        tip_rack = coordinates["tip_rack"]
        self.assertEqual(
            {"row": 3, "column": 4, "x": 101.3, "y": 4.8},
            tip_rack["reference"],
        )
        self.assertEqual((-2.2, 4.5, 93.0), (
            tip_rack["column_step_x"],
            tip_rack["row_step_y"],
            tip_rack["pipette_z"],
        ))
        self.assertEqual(
            {"holding_opening": 30.0, "glass_release_opening": 64.0},
            coordinates["gripper"],
        )

        safety = json.loads(
            (PROJECT_ROOT / "config" / "safety_limits.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(1.0, safety["homing_step"])
        self.assertEqual(500, safety["homing_max_steps"])

    def test_builds_every_existing_native_device_from_legacy_aligned_settings(
        self,
    ) -> None:
        """Check builds every existing native device from legacy aligned settings."""
        config = json.loads(
            (PROJECT_ROOT / "config" / "devices.yaml").read_text(encoding="utf-8")
        )

        (
            stage,
            sensor,
            gripper,
            pipette,
            spin_coater,
            vacuum_station,
            valve,
        ) = build_native_devices(config)

        self.assertIsInstance(stage, StageDriver)
        self.assertIsInstance(sensor, PositionSensorDriver)
        self.assertIsInstance(gripper, GripperDriver)
        self.assertIsInstance(pipette, PipetteDriver)
        self.assertIsInstance(spin_coater, SpinCoaterDriver)
        self.assertIsInstance(vacuum_station, VacuumStationDriver)
        self.assertIsInstance(valve, ValveDriver)

        self.assertEqual("COM8", stage._client.transport.settings.port)
        self.assertEqual(115200, stage._client.transport.settings.baudrate)
        self.assertEqual(0.0, stage._client.transport.settings.timeout_s)
        self.assertEqual(0.1, stage._client.transport.settings.response_delay_s)
        self.assertEqual(
            (-140.0, 140.0),
            (stage._config.minimum_x, stage._config.maximum_x),
        )
        self.assertEqual(
            (-100.0, 100.0),
            (stage._config.minimum_y, stage._config.maximum_y),
        )
        self.assertEqual(40000, stage._config.pulses_x)
        self.assertEqual(80000, stage._config.pulses_y)
        self.assertEqual(
            (700, 100, 100),
            (
                stage._config.speed_x,
                stage._config.acceleration_x,
                stage._config.deceleration_x,
            ),
        )
        self.assertEqual(
            (70, 100, 100),
            (
                stage._config.speed_y,
                stage._config.acceleration_y,
                stage._config.deceleration_y,
            ),
        )
        self.assertEqual(10.0, stage._config.movement_timeout_s)
        self.assertEqual(10, stage._config.hardware_zero_tolerance_pulses)

        self.assertEqual("COM10", sensor._client.transport.settings.port)
        self.assertEqual(9600, sensor._client.transport.settings.baudrate)
        self.assertEqual(0.0, sensor._client.transport.settings.timeout_s)
        self.assertEqual(0.2, sensor._client.transport.settings.response_delay_s)

        self.assertEqual("COM7", gripper._transport.settings.port)
        self.assertEqual(115200, gripper._transport.settings.baudrate)
        self.assertEqual(0.0, gripper._transport.settings.timeout_s)
        self.assertEqual(0.1, gripper._transport.settings.response_delay_s)
        self.assertEqual(15000, gripper._config.z_pulses_per_100)
        self.assertEqual(10.0, gripper._config.movement_timeout_s)

        self.assertEqual("COM9", pipette._transport.settings.port)
        self.assertEqual(115200, pipette._transport.settings.baudrate)
        self.assertEqual(0.0, pipette._transport.settings.timeout_s)
        self.assertEqual(0.1, pipette._transport.settings.response_delay_s)
        self.assertEqual(150000, pipette._config.z_pulses_per_100)
        self.assertEqual(10.0, pipette._config.movement_timeout_s)

        self.assertEqual("COM14", spin_coater._client.transport.settings.port)
        self.assertEqual(115200, spin_coater._client.transport.settings.baudrate)
        self.assertEqual(0.0, spin_coater._client.transport.settings.timeout_s)
        self.assertEqual(0.2, spin_coater._client.transport.settings.response_delay_s)
        self.assertEqual(8388608, spin_coater._config.maximum_single_revolution_position)
        self.assertEqual(3458608, spin_coater._config.glass_origin_position)
        self.assertEqual(1.5, spin_coater._config.home_poll_start_delay_s)
        self.assertEqual(0.25, spin_coater._config.home_poll_interval_s)
        self.assertEqual(10000, spin_coater._config.home_position_tolerance_counts)
        self.assertEqual(3.0, spin_coater._client.continuous_failure_timeout_s)
        self.assertEqual(0.1, spin_coater._client.retry_interval_s)

        self.assertEqual("COM15", vacuum_station._transport.settings.port)
        self.assertEqual(9600, vacuum_station._transport.settings.baudrate)
        self.assertEqual(0.0, vacuum_station._transport.settings.timeout_s)
        self.assertEqual(0.2, vacuum_station._transport.settings.response_delay_s)
        self.assertEqual(-120, vacuum_station._config.open_speed)
        self.assertEqual(105, vacuum_station._config.close_speed)

        self.assertEqual("COM13", valve._client.transport.settings.port)
        self.assertEqual(38400, valve._client.transport.settings.baudrate)
        self.assertEqual(0.0, valve._client.transport.settings.timeout_s)
        self.assertEqual(0.1, valve._client.transport.settings.response_delay_s)


if __name__ == "__main__":
    unittest.main()
