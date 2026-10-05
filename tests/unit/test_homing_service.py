import unittest

from integrated_control.application.calibration.homing_service import HomingService
from integrated_control.domain.models import HomingConfig
from integrated_control.infrastructure.simulation import (
    SimulatedPositionSensor,
    SimulatedStage,
)


class HomingServiceTests(unittest.TestCase):
    def test_homing_finds_both_sensor_origins(self) -> None:
        stage = SimulatedStage(initial_x=3.0, initial_y=4.0)
        sensor = SimulatedPositionSensor(stage, trigger_x=0.0, trigger_y=0.0)
        stage.initialize()
        sensor.initialize()

        result = HomingService(stage, sensor, HomingConfig(1.0, 10)).home_xy()

        self.assertTrue(result.success)
        self.assertEqual(0.0, stage.get_offset("x"))
        self.assertEqual(0.0, stage.get_offset("y"))
        self.assertEqual(0.0, stage.get_raw_position("x"))
        self.assertEqual(0.0, stage.get_raw_position("y"))

    def test_failed_homing_restores_previous_offset(self) -> None:
        stage = SimulatedStage(initial_x=10.0, initial_y=10.0)
        stage.set_offset("x", 2.5)
        sensor = SimulatedPositionSensor(stage, trigger_x=-100.0, trigger_y=0.0)
        stage.initialize()
        sensor.initialize()

        result = HomingService(stage, sensor, HomingConfig(1.0, 2)).home_xy()

        self.assertFalse(result.success)
        self.assertEqual("HOMING_X_NOT_TRIGGERED", result.error_code)
        self.assertEqual(2.5, stage.get_offset("x"))


if __name__ == "__main__":
    unittest.main()
