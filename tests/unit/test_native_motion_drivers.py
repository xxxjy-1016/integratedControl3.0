import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from integrated_control.infrastructure.drivers.native import (
    PositionSensorDriver,
    StageDriver,
)
from integrated_control.infrastructure.persistence import StageStateStore


class FakeModbusClient:
    """Group checks for fake modbus client."""
    def __init__(self) -> None:
        """Initialize fake modbus client dependencies and internal state."""
        self.opened = False
        self.closed = False
        self.writes: list[tuple] = []
        self.positions = {1: 0, 2: 0}
        self.mode = 1
        self.y_homing_started = False

    def open(self) -> None:
        """Open."""
        self.opened = True

    def close(self) -> None:
        """Close."""
        self.closed = True

    def write_single_register(
        self, address: int, value: int, *, slave_id: int | None = None
    ) -> None:
        """Write single register."""
        self.writes.append(("single", slave_id, address, value))
        if address == 0x6060 and slave_id == 1:
            self.mode = value
        elif address == 0x2101 and value == 1 and slave_id == 2:
            self.positions[2] = 0
        elif address == 0x6040 and value == 0x001F and self.mode == 6:
            self.y_homing_started = True
            self.positions[1] = 0

    def write_multiple_registers(
        self, address: int, values: list[int], *, slave_id: int | None = None
    ) -> None:
        """Write multiple registers."""
        self.writes.append(("multiple", slave_id, address, list(values)))
        if address in {0x2320, 0x607A} and slave_id is not None:
            raw = b"".join(value.to_bytes(2, "big") for value in values)
            self.positions[slave_id] = int.from_bytes(raw, "big", signed=True)

    def read_holding_registers(
        self, address: int, count: int = 1, *, slave_id: int | None = None
    ) -> list[int]:
        """Read holding registers."""
        if address == 0x2303:
            return [0x0042]
        if address == 0x6061:
            return [self.mode]
        if address == 0x6041:
            status = 1 << 10
            if self.y_homing_started:
                status |= 1 << 12
            return [status]
        if address in {0, 1}:
            return [65535 if address == 0 else 0]
        return [0] * count

    def read_data_bytes(
        self, address: int, count: int, *, slave_id: int | None = None
    ) -> bytes:
        """Read data bytes."""
        value = self.positions[slave_id or 1]
        return value.to_bytes(4, "big", signed=True)


class NativeStageDriverTests(unittest.TestCase):
    """Group checks for native stage driver tests."""
    def test_initializes_both_axes_and_moves_x(self) -> None:
        """Check initializes both axes and moves x."""
        client = FakeModbusClient()
        driver = StageDriver(client)  # type: ignore[arg-type]

        self.assertTrue(driver.initialize().success)
        result = driver.move_axis("x", 25.0)

        self.assertTrue(result.success)
        self.assertEqual(25.0, result.measurements["raw_x"])
        self.assertIn(("single", 2, 0x2109, 1), client.writes)
        self.assertIn(("multiple", 2, 0x2320, [0, 10000]), client.writes)

    def test_rejects_y_target_outside_legacy_range(self) -> None:
        """Check rejects y target outside legacy range."""
        client = FakeModbusClient()
        driver = StageDriver(client)  # type: ignore[arg-type]
        driver.initialize()

        result = driver.move_axis("y", 101.0)

        self.assertFalse(result.success)
        self.assertEqual("STAGE_LIMIT", result.error_code)

    def test_x_hardware_zero_uses_current_position_clear_register(self) -> None:
        """Check x hardware zero uses current position clear register."""
        client = FakeModbusClient()
        driver = StageDriver(client)  # type: ignore[arg-type]
        driver.initialize()
        client.positions[2] = 1234

        result = driver.set_current_position_as_zero("x")

        self.assertTrue(result.success)
        self.assertEqual(0, result.measurements["position_pulses"])
        self.assertIn(("single", 2, 0x2101, 1), client.writes)

    def test_y_hardware_zero_uses_cia402_current_position_homing(self) -> None:
        """Check y hardware zero uses cia402 current position homing."""
        client = FakeModbusClient()
        driver = StageDriver(client)  # type: ignore[arg-type]
        driver.initialize()
        client.positions[1] = 4321

        result = driver.set_current_position_as_zero("y")

        self.assertTrue(result.success)
        self.assertEqual(0, result.measurements["position_pulses"])
        self.assertEqual(6, result.measurements["mode_display"])
        self.assertTrue(result.measurements["statusword"] & (1 << 12))
        self.assertIn(("single", 1, 0x6060, 6), client.writes)
        self.assertIn(("multiple", 1, 0x607C, [0, 0]), client.writes)
        self.assertIn(("single", 1, 0x6098, 0), client.writes)
        self.assertIn(("single", 1, 0x6040, 0x001F), client.writes)
        self.assertIn(("single", 1, 0x6060, 1), client.writes)

    def test_loads_saved_offsets_and_origin_flag_during_initialization(self) -> None:
        """Check loads saved offsets and origin flag during initialization."""
        with TemporaryDirectory() as directory:
            store = StageStateStore(Path(directory) / "stage.json")
            store.save_offsets(-0.0075, -0.02)
            store.save_origin(True)
            driver = StageDriver(  # type: ignore[arg-type]
                FakeModbusClient(), state_store=store
            )

            result = driver.initialize()

            self.assertTrue(result.success)
            self.assertFalse(driver.needs_startup_homing())
            self.assertEqual(-0.0075, driver.get_offset("x"))
            self.assertEqual(-0.02, driver.get_offset("y"))

    def test_logical_movement_updates_persisted_origin_flag(self) -> None:
        """Check logical movement updates persisted origin flag."""
        with TemporaryDirectory() as directory:
            store = StageStateStore(Path(directory) / "stage.json")
            store.save_origin(True)
            driver = StageDriver(  # type: ignore[arg-type]
                FakeModbusClient(), state_store=store
            )
            driver.initialize()

            moved_away = driver.move_axis("x", 25.0)
            self.assertTrue(moved_away.success)
            self.assertFalse(store.load().stage_at_origin)

            moved_back = driver.move_axis("x", 0.0)
            self.assertTrue(moved_back.success)
            self.assertTrue(store.load().stage_at_origin)

    def test_origin_state_allows_configured_position_feedback_tolerance(self) -> None:
        """Check origin state allows configured position feedback tolerance."""
        with TemporaryDirectory() as directory:
            store = StageStateStore(Path(directory) / "stage.json")
            client = FakeModbusClient()
            driver = StageDriver(client, state_store=store)  # type: ignore[arg-type]
            driver.initialize()

            client.positions[1] = -10
            client.positions[2] = 10
            driver._update_origin_from_actual_positions()
            self.assertTrue(store.load().stage_at_origin)

            client.positions[2] = 11
            driver._update_origin_from_actual_positions()
            self.assertFalse(store.load().stage_at_origin)


class NativePositionSensorDriverTests(unittest.TestCase):
    """Group checks for native position sensor driver tests."""
    def test_configures_ranges_and_converts_voltage(self) -> None:
        """Check configures ranges and converts voltage."""
        client = FakeModbusClient()
        driver = PositionSensorDriver(client)  # type: ignore[arg-type]

        self.assertTrue(driver.initialize().success)
        self.assertTrue(driver.is_triggered("x"))
        self.assertFalse(driver.is_triggered("y"))
        self.assertIn(("single", None, 200, 0x000B), client.writes)
        self.assertIn(("single", None, 201, 0x000B), client.writes)


if __name__ == "__main__":
    unittest.main()
