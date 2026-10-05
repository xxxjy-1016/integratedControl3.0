import unittest

from integrated_control.infrastructure.transports.ascii_motion import (
    append_ascii_crc,
    signed_hex_command,
)
from integrated_control.infrastructure.drivers.native.gripper_driver import (
    GripperDriver,
    GripperDriverConfig,
)
from integrated_control.infrastructure.drivers.native.pipette_driver import (
    PipetteDriver,
    PipetteDriverConfig,
)
from integrated_control.infrastructure.drivers.native.valve_driver import ValveDriver
from integrated_control.infrastructure.transports.modbus_rtu import (
    ModbusRtuClient,
    crc16,
)


class FakeHandlingTransport:
    def __init__(self, *, liquid_detected: bool = True) -> None:
        self.opened = False
        self.closed = False
        self.writes: list[bytes] = []
        self.registers: dict[int, int] = {
            0x0202: 1,
            0x0203: 1,
            0x0204: 0,
        }
        self.liquid_detected = liquid_detected

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def write(self, request: bytes, *, reset_buffers: bool = True) -> None:
        self.writes.append(request)

    def transact(
        self,
        request: bytes,
        *,
        response_size: int = 256,
        reset_buffers: bool = True,
    ) -> bytes:
        self.writes.append(request)
        if request.startswith(b">"):
            if request == b">02d4819":
                # The gripper uses this query for Z arrival; after the pipette's
                # Z controller was initialized, the same bytes query liquid state.
                if b">01G6158" in self.writes:
                    return b">02d0100" if self.liquid_detected else b">02d0900"
                return b">02d0172DE"
            responses = {
                b">02g4959": b">02g01722E",
                b">01dB819": b">01d0136DE",
            }
            return responses[request]

        payload = request[:-2]
        if request[-2:] != crc16(payload):
            return b""
        function = payload[1]
        address = int.from_bytes(payload[2:4], "big")
        if function == 0x06:
            value = int.from_bytes(payload[4:6], "big")
            self.registers[address] = value
            if address == 0x0100:
                self.registers[0x0202] = 1
            elif address == 0x0101:
                self.registers[0x0203] = 1
            elif address == 0x0105:
                if value == 100:
                    self.registers[0x0202] = 2
                    self.registers[0x0204] = 30
                else:
                    self.registers[0x0202] = 1
                    self.registers[0x0204] = value
            return request
        if function == 0x03:
            value = self.registers.get(address, 0)
            response = bytes([1, 0x03, 2]) + value.to_bytes(2, "big")
            return response + crc16(response)
        raise AssertionError(f"Unexpected request: {request!r}")

    def transact_exact(self, request: bytes, *, response_size: int) -> bytes:
        response = self.transact(request, response_size=response_size)
        return response[:response_size]


class NativeGripperDriverTests(unittest.TestCase):
    def test_initializes_and_controls_all_three_axes(self) -> None:
        transport = FakeHandlingTransport()
        driver = GripperDriver(
            transport,
            GripperDriverConfig(movement_timeout_s=0.1, poll_interval_s=0.0),
        )

        self.assertTrue(driver.initialize().success)
        self.assertTrue(driver.move_z(20.0).success)
        close_result = driver.close(60.0)
        self.assertTrue(close_result.success)
        self.assertTrue(close_result.measurements["holding_object"])
        self.assertEqual(70.0, close_result.measurements["opening"])
        self.assertTrue(driver.rotate(-90).success)
        state = driver.get_state()

        self.assertEqual("READY", state.lifecycle)
        self.assertEqual(20.0, state.measurements["z"])
        self.assertEqual(-90.0, state.measurements["rotation_deg"])
        self.assertIn(b">02G9158", transport.writes)
        self.assertTrue(any(command.startswith(b">02D") for command in transport.writes))

    def test_rejects_out_of_range_requests_without_writing(self) -> None:
        transport = FakeHandlingTransport()
        driver = GripperDriver(transport)
        driver.initialize()
        before = len(transport.writes)

        self.assertEqual("GRIPPER_Z_LIMIT", driver.move_z(101).error_code)
        self.assertEqual("GRIPPER_FORCE_LIMIT", driver.close(5).error_code)
        self.assertEqual(before, len(transport.writes))


class NativePipetteDriverTests(unittest.TestCase):
    def test_tip_liquid_and_z_state_are_tracked(self) -> None:
        transport = FakeHandlingTransport()
        driver = PipetteDriver(
            transport,
            PipetteDriverConfig(movement_timeout_s=0.1, poll_interval_s=0.0),
        )

        self.assertTrue(driver.initialize().success)
        self.assertTrue(driver.move_z(25.0).success)
        self.assertTrue(driver.attach_tip("tip-1").success)
        self.assertTrue(driver.aspirate(100).success)
        dispense = driver.dispense(40)
        self.assertTrue(dispense.success)
        self.assertEqual(60.0, dispense.measurements["remaining_ul"])
        self.assertTrue(driver.eject_tip().success)
        self.assertIsNone(driver.get_state().measurements["tip_id"])
        self.assertIn(b">02Q5FD9", transport.writes)

    def test_requires_tip_and_enforces_capacity(self) -> None:
        transport = FakeHandlingTransport()
        driver = PipetteDriver(transport)
        driver.initialize()

        self.assertEqual("TIP_REQUIRED", driver.aspirate(1).error_code)
        driver.attach_tip("tip-1")
        self.assertEqual("PIPETTE_CAPACITY", driver.aspirate(1001).error_code)

    def test_dry_run_can_continue_without_real_liquid(self) -> None:
        transport = FakeHandlingTransport(liquid_detected=False)
        driver = PipetteDriver(
            transport,
            PipetteDriverConfig(movement_timeout_s=0.1, poll_interval_s=0.0),
        )
        driver.initialize()
        driver.attach_tip("tip-1")

        strict_result = driver.aspirate(100)
        self.assertFalse(strict_result.success)
        self.assertEqual("PIPETTE_NO_LIQUID", strict_result.error_code)

        dry_result = driver.aspirate(100, require_liquid_detection=False)
        self.assertTrue(dry_result.success)
        self.assertFalse(dry_result.measurements["liquid_detected"])
        self.assertEqual(100.0, dry_result.measurements["liquid_ul"])
        self.assertTrue(driver.dispense().success)
        self.assertTrue(any(command.startswith(b">02p") for command in transport.writes))


class NativeValveDriverTests(unittest.TestCase):
    def test_initialization_and_stop_leave_valve_closed(self) -> None:
        transport = FakeHandlingTransport()
        driver = ValveDriver(ModbusRtuClient(transport))

        self.assertTrue(driver.initialize().success)
        self.assertTrue(driver.open().success)
        self.assertTrue(driver.get_state().measurements["is_open"])
        self.assertTrue(driver.stop().success)
        self.assertFalse(driver.get_state().measurements["is_open"])
        self.assertTrue(transport.closed)
        self.assertEqual(0, transport.registers[0])


class AsciiProtocolTests(unittest.TestCase):
    def test_known_initialization_crc_matches_legacy_protocol(self) -> None:
        self.assertEqual(b">02G9158", append_ascii_crc(b">02G"))

    def test_motion_data_preserves_legacy_lower_case_hex_format(self) -> None:
        self.assertEqual(
            b">02D00000bb82C60",
            signed_hex_command(b">02D", 3000, width=4),
        )


if __name__ == "__main__":
    unittest.main()
