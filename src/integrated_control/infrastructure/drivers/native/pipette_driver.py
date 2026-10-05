from dataclasses import dataclass

from integrated_control.devices.pipette import Pipette
from integrated_control.domain.errors import IntegratedControlError, ProtocolError
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult
from integrated_control.infrastructure.transports.ascii_motion import (
    AsciiSerialTransport,
    signed_hex_command,
    wait_for_ascii_status,
)


@dataclass(frozen=True)
class PipetteDriverConfig:
    minimum_z: float = 0.0
    maximum_z: float = 100.0
    z_pulses_per_100: int = 150000
    capacity_ul: float = 1000.0
    movement_timeout_s: float = 10.0
    poll_interval_s: float = 0.1


class PipetteDriver(Pipette):
    """Native ASCII driver migrated from ``old/mouth.py``."""

    Z_INIT = b">01G6158"
    Z_QUERY = b">01dB819"
    Z_ARRIVED = b">01d0136DE"
    ADP_INIT = b">02G9158"
    ADP_QUERY = b">02g4959"
    ADP_ARRIVED = b">02g01722E"
    EJECT = b">02Q5FD9"
    LIQUID_QUERY = b">02d4819"

    def __init__(
        self,
        transport: AsciiSerialTransport,
        config: PipetteDriverConfig | None = None,
    ) -> None:
        self._transport = transport
        self._config = config or PipetteDriverConfig()
        self._initialized = False
        self._activity = "IDLE"
        self._fault: str | None = None
        self._z: float | None = None
        self._tip_id: str | None = None
        self._liquid_ul = 0.0

    @property
    def device_id(self) -> str:
        return "pipette"

    def initialize(self) -> ActionResult:
        self._activity = "INITIALIZING"
        try:
            self._transport.open()
            self._transport.write(self.ADP_INIT)
            self._wait_adp()
            self._transport.write(self.Z_INIT)
            self._wait_z()
        except IntegratedControlError as exc:
            self._close_after_failure()
            return self._failure("PIPETTE_INITIALIZATION_FAILED", exc)
        self._initialized = True
        self._fault = None
        self._activity = "IDLE"
        self._z = 0.0
        self._tip_id = None
        self._liquid_ul = 0.0
        return ActionResult.done("Native pipette initialized")

    def move_z(self, height: float) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        if not self._config.minimum_z <= height <= self._config.maximum_z:
            return ActionResult.failed(
                "PIPETTE_Z_LIMIT",
                f"Pipette Z target {height} is outside "
                f"{self._config.minimum_z}..{self._config.maximum_z}",
            )
        pulses = int(height / 100.0 * self._config.z_pulses_per_100)
        self._activity = "MOVING_Z"
        try:
            self._transport.write(signed_hex_command(b">01D", pulses, width=4))
            self._wait_z()
        except (IntegratedControlError, ValueError) as exc:
            return self._failure("PIPETTE_Z_MOVE_FAILED", exc)
        self._z = height
        self._activity = "IDLE"
        return ActionResult.done("Pipette Z movement completed", {"z": height})

    def attach_tip(self, tip_id: str) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        if not tip_id.strip():
            return ActionResult.failed("INVALID_TIP_ID", "Tip id must not be empty")
        if self._tip_id is not None:
            return ActionResult.failed("TIP_ALREADY_ATTACHED", "A tip is already attached")
        self._tip_id = tip_id
        return ActionResult.done(
            "Pipette tip recorded as attached", {"tip_id": tip_id}
        )

    def eject_tip(self) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        self._activity = "EJECTING_TIP"
        try:
            self._transport.write(self.EJECT)
            self._wait_adp()
        except IntegratedControlError as exc:
            return self._failure("PIPETTE_EJECT_FAILED", exc)
        old_tip = self._tip_id
        self._tip_id = None
        self._liquid_ul = 0.0
        self._activity = "IDLE"
        return ActionResult.done("Pipette tip ejected", {"tip_id": old_tip})

    def aspirate(
        self,
        volume_ul: float,
        *,
        require_liquid_detection: bool = True,
    ) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        if self._tip_id is None:
            return ActionResult.failed("TIP_REQUIRED", "Attach a tip before aspiration")
        if volume_ul <= 0 or self._liquid_ul + volume_ul > self._config.capacity_ul:
            return ActionResult.failed("PIPETTE_CAPACITY", "Requested volume is invalid")
        amount = round(volume_ul)
        if amount <= 0 or amount > 0xFFFF:
            return ActionResult.failed("PIPETTE_VOLUME_LIMIT", "Volume must fit 1..65535")
        self._activity = "ASPIRATING"
        liquid_detected = True
        try:
            self._transport.write(signed_hex_command(b">02n", amount, width=2))
            self._wait_adp()
            response = self._transport.transact(
                self.LIQUID_QUERY, response_size=40
            ).strip()
            if len(response) < 6 or not response.startswith(b">02"):
                raise ProtocolError(f"Invalid pipette liquid response: {response!r}")
            if response[4:6] in {b"09", b"0A"}:
                liquid_detected = False
                if require_liquid_detection:
                    self._activity = "IDLE"
                    return ActionResult.failed(
                        "PIPETTE_NO_LIQUID",
                        "Pipette did not detect aspirated liquid",
                    )
        except IntegratedControlError as exc:
            return self._failure("PIPETTE_ASPIRATE_FAILED", exc)
        self._liquid_ul += amount
        self._activity = "IDLE"
        return ActionResult.done(
            (
                "Aspiration completed"
                if liquid_detected
                else "Dry-run aspiration completed without liquid detection"
            ),
            {
                "liquid_ul": self._liquid_ul,
                "liquid_detected": liquid_detected,
            },
        )

    def dispense(self, volume_ul: float | None = None) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        if self._tip_id is None:
            return ActionResult.failed("TIP_REQUIRED", "Attach a tip before dispensing")
        requested = self._liquid_ul if volume_ul is None else volume_ul
        if requested <= 0 or requested > self._liquid_ul:
            return ActionResult.failed("INSUFFICIENT_LIQUID", "Volume is unavailable")
        amount = round(requested)
        if amount <= 0 or amount > 0xFFFF:
            return ActionResult.failed("PIPETTE_VOLUME_LIMIT", "Volume must fit 1..65535")
        self._activity = "DISPENSING"
        try:
            self._transport.write(signed_hex_command(b">02p", amount, width=2))
            self._wait_adp()
        except IntegratedControlError as exc:
            return self._failure("PIPETTE_DISPENSE_FAILED", exc)
        self._liquid_ul -= amount
        self._activity = "IDLE"
        return ActionResult.done(
            "Dispense completed",
            {"dispensed_ul": amount, "remaining_ul": self._liquid_ul},
        )

    def stop(self) -> ActionResult:
        try:
            self._transport.close()
        except IntegratedControlError as exc:
            return self._failure("PIPETTE_CLOSE_FAILED", exc)
        self._initialized = False
        self._activity = "IDLE"
        return ActionResult.done(
            "Native pipette connection closed; no undocumented motion-stop command "
            "was sent"
        )

    def get_state(self) -> DeviceState:
        lifecycle = "FAULT" if self._fault else (
            "READY" if self._initialized else "OFFLINE"
        )
        return DeviceState(
            self.device_id,
            lifecycle,
            self._activity,
            {
                "z": self._z,
                "tip_id": self._tip_id,
                "liquid_ul": self._liquid_ul,
                "capacity_ul": self._config.capacity_ul,
                "backend": "native",
            },
            self._fault,
        )

    def _wait_z(self) -> None:
        wait_for_ascii_status(
            self._transport,
            self.Z_QUERY,
            self.Z_ARRIVED,
            timeout_s=self._config.movement_timeout_s,
            poll_interval_s=self._config.poll_interval_s,
        )

    def _wait_adp(self) -> None:
        wait_for_ascii_status(
            self._transport,
            self.ADP_QUERY,
            self.ADP_ARRIVED,
            timeout_s=self._config.movement_timeout_s,
            poll_interval_s=self._config.poll_interval_s,
            response_size=20,
        )

    def _ready_failure(self) -> ActionResult | None:
        if not self._initialized:
            return ActionResult.failed("DEVICE_NOT_READY", "Pipette is not initialized")
        return None

    def _close_after_failure(self) -> None:
        try:
            self._transport.close()
        except IntegratedControlError:
            pass

    def _failure(self, code: str, exc: Exception) -> ActionResult:
        self._fault = str(exc) or type(exc).__name__
        self._activity = "FAULT"
        return ActionResult.failed(code, self._fault)
