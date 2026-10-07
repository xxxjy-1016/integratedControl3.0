import unittest

from integrated_control.domain.models import SpinStep
from integrated_control.infrastructure.drivers.native.spin_coater_driver import (
    SpinCoaterDriver,
    SpinCoaterDriverConfig,
)
from integrated_control.infrastructure.drivers.native.vacuum_station_driver import (
    VacuumStationDriver,
    VacuumStationDriverConfig,
)
from integrated_control.infrastructure.transports.modbus_rtu import crc16


class FakeSpinModbusClient:
    """Group checks for fake spin modbus client."""
    def __init__(self, *, execute_position_move: bool = True) -> None:
        """Initialize fake spin modbus client dependencies and internal state."""
        self.opened = False
        self.closed = False
        self.execute_position_move = execute_position_move
        self.servo_enabled = False
        self.writes: list[tuple] = []
        self.registers = {
            0x0201: [10000, 0],
            0xD013: [0, 0],
        }

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
        self.writes.append(("single", address, value))
        if address == 0x600C:
            self.servo_enabled = value == 1
        if (
            address == 0x600A
            and value == 1
            and self.servo_enabled
            and self.execute_position_move
        ):
            low, high = self.registers[0x5305]
            delta = high * 65536 + low
            current_low, current_high = self.registers[0xD013]
            current = current_high * 65536 + current_low
            position = (current + delta) % 8388608
            self.registers[0xD013] = [
                position & 0xFFFF,
                position >> 16,
            ]

    def write_multiple_registers(
        self, address: int, values: list[int], *, slave_id: int | None = None
    ) -> None:
        """Write multiple registers."""
        data = list(values)
        self.writes.append(("multiple", address, data))
        self.registers[address] = data

    def read_holding_registers(
        self, address: int, count: int = 1, *, slave_id: int | None = None
    ) -> list[int]:
        """Read holding registers."""
        return self.registers.get(address, [0] * count)


class FakeWriteTransport:
    """Group checks for fake write transport."""
    def __init__(self) -> None:
        """Initialize fake write transport dependencies and internal state."""
        self.opened = False
        self.closed = False
        self.writes: list[bytes] = []

    def open(self) -> None:
        """Open."""
        self.opened = True

    def write(self, request: bytes, *, reset_buffers: bool = True) -> None:
        """Write."""
        self.writes.append(request)

    def close(self) -> None:
        """Close."""
        self.closed = True


def decoded_write(frame: bytes) -> tuple[int, int]:
    """Decoded write."""
    assert frame[-2:] == crc16(frame[:-2])
    assert frame[:2] == bytes([1, 0x06])
    return int.from_bytes(frame[2:4], "big"), int.from_bytes(frame[4:6], "big")


class NativeSpinCoaterDriverTests(unittest.TestCase):
    """Group checks for native spin coater driver tests."""
    def test_initializes_spins_stops_and_homes_with_legacy_registers(self) -> None:
        """Check initializes spins stops and homes with legacy registers."""
        client = FakeSpinModbusClient()
        driver = SpinCoaterDriver(
            client,  # type: ignore[arg-type]
            SpinCoaterDriverConfig(communication_compensation_s=0.0),
            sleep=lambda _seconds: None,
        )

        self.assertTrue(driver.initialize().success)
        result = driver.run([SpinStep(5000, 10.0, 5000.0)])

        self.assertTrue(result.success, result.message)
        self.assertIn(("single", 0x6001, 21), client.writes)
        self.assertIn(("single", 0x600C, 1), client.writes)
        self.assertIn(("single", 0x4103, 1000), client.writes)
        self.assertIn(("single", 0x4104, 1000), client.writes)
        self.assertIn(("single", 0x4102, 5000), client.writes)
        self.assertIn(("single", 0x4102, 0), client.writes)
        home_target = 3458608
        self.assertIn(
            (
                "multiple",
                0x5305,
                [home_target & 0xFFFF, home_target >> 16],
            ),
            client.writes,
        )
        position_write_index = client.writes.index(
            (
                "multiple",
                0x5305,
                [home_target & 0xFFFF, home_target >> 16],
            )
        )
        servo_on_index = client.writes.index(
            ("single", 0x600C, 1), position_write_index
        )
        position_trigger_index = client.writes.index(
            ("single", 0x600A, 1), position_write_index
        )
        self.assertLess(servo_on_index, position_trigger_index)
        state = driver.get_state()
        self.assertEqual("READY", state.lifecycle)
        self.assertTrue(state.measurements["homed"])
        self.assertEqual(0, state.measurements["rpm"])

    def test_home_fails_when_position_feedback_does_not_reach_origin(self) -> None:
        """Check home fails when position feedback does not reach origin."""
        client = FakeSpinModbusClient(execute_position_move=False)
        driver = SpinCoaterDriver(
            client,  # type: ignore[arg-type]
            SpinCoaterDriverConfig(
                home_motion_time_s=0.1,
                home_poll_interval_s=0.1,
            ),
            sleep=lambda _seconds: None,
        )
        self.assertTrue(driver.initialize().success)

        result = driver.home()

        self.assertFalse(result.success)
        self.assertEqual("SPIN_COATER_HOME_FAILED", result.error_code)
        self.assertIn("did not reach", result.message)
        self.assertFalse(driver.get_state().measurements["homed"])
        self.assertEqual([10000, 0], client.registers[0x0201])
        self.assertEqual(("single", 0x4101, 0), client.writes[-1])

class NativeVacuumStationDriverTests(unittest.TestCase):
    """Group checks for native vacuum station driver tests."""
    def test_open_and_close_use_old_code_timed_command_sequences(self) -> None:
        """Check open and close use old code timed command sequences."""
        transport = FakeWriteTransport()
        driver = VacuumStationDriver(
            transport,
            VacuumStationDriverConfig(command_delay_s=0.0),
            sleep=lambda _seconds: None,
        )

        self.assertTrue(driver.initialize().success)
        self.assertTrue(driver.open_cover().success)
        self.assertTrue(driver.close_cover().success)
        writes = [decoded_write(frame) for frame in transport.writes]

        self.assertEqual((0x0038, 2), writes[0])
        self.assertIn((0x0033, (-120) & 0xFFFF), writes)
        self.assertIn((0x0034, 0), writes)
        self.assertIn((0x0033, 105), writes)
        self.assertIn((0x0034, 250), writes)
        self.assertEqual((0x0038, 0), writes[-1])
        state = driver.get_state()
        self.assertFalse(state.measurements["cover_open"])
        self.assertFalse(state.measurements["position_feedback"])

    def test_pressure_operations_fail_instead_of_faking_hardware(self) -> None:
        """Check pressure operations fail instead of faking hardware."""
        driver = VacuumStationDriver(
            FakeWriteTransport(),  # type: ignore[arg-type]
            VacuumStationDriverConfig(command_delay_s=0.0),
            sleep=lambda _seconds: None,
        )
        driver.initialize()

        self.assertEqual(
            "VACUUM_PRESSURE_CONTROL_UNAVAILABLE",
            driver.evacuate(10.0).error_code,
        )
        self.assertEqual(
            "VACUUM_VENT_CONTROL_UNAVAILABLE",
            driver.vent().error_code,
        )


if __name__ == "__main__":
    unittest.main()
