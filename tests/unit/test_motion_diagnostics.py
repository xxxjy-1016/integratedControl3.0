import unittest

from integrated_control.application.calibration.homing_service import HomingService
from integrated_control.application.device_diagnostics import (
    DeviceDiagnosticsController,
)
from integrated_control.application.device_manager import DeviceManager
from integrated_control.domain.models import HomingConfig
from integrated_control.infrastructure.simulation import (
    SimulatedPositionSensor,
    SimulatedStage,
)


class MotionDiagnosticsTests(unittest.TestCase):
    """Group checks for motion diagnostics tests."""
    def setUp(self) -> None:
        """Set up."""
        self.stage = SimulatedStage(initial_x=5.0, initial_y=8.0)
        self.sensor = SimulatedPositionSensor(
            self.stage, trigger_x=0.0, trigger_y=0.0
        )
        homing = HomingService(self.stage, self.sensor, HomingConfig(1.0, 20))
        self.controller = DeviceDiagnosticsController(
            DeviceManager([self.stage, self.sensor]), homing
        )
        self.assertTrue(self.controller.initialize().success)

    def tearDown(self) -> None:
        """Tear down."""
        self.controller.shutdown()

    def test_stage_operations_stay_on_the_stage_interface(self) -> None:
        """Check stage operations stay on the stage interface."""
        self.stage.set_offset("x", 2.0)

        moved = self.controller.stage.move_xy(10.0, 20.0)
        jogged = self.controller.stage.jog("x", -3.0)

        self.assertTrue(moved.success)
        self.assertTrue(jogged.success)
        self.assertEqual(9.0, self.stage.get_raw_position("x"))
        self.assertEqual(7.0, self.stage.get_position("x"))
        self.assertEqual(20.0, self.stage.get_position("y"))

    def test_snapshot_combines_motion_and_sensor_data(self) -> None:
        """Check snapshot combines motion and sensor data."""
        snapshot = self.controller.snapshot()

        self.assertEqual(5.0, snapshot.raw_x)
        self.assertEqual(8.0, snapshot.raw_y)
        self.assertFalse(snapshot.sensor_x_triggered)
        self.assertFalse(snapshot.sensor_y_triggered)

    def test_cross_device_homing_remains_on_the_controller(self) -> None:
        """Check cross device homing remains on the controller."""
        result = self.controller.home_axis("x")

        self.assertTrue(result.success)
        self.assertEqual(0.0, self.stage.get_position("x"))

    def test_homing_fails_before_lifecycle_initialization(self) -> None:
        """Check homing fails before lifecycle initialization."""
        stage = SimulatedStage()
        sensor = SimulatedPositionSensor(stage)
        controller = DeviceDiagnosticsController(
            DeviceManager([stage, sensor]), HomingService(stage, sensor)
        )

        result = controller.home_axis("x")

        self.assertFalse(result.success)
        self.assertEqual("DEVICE_NOT_READY", result.error_code)


if __name__ == "__main__":
    unittest.main()
