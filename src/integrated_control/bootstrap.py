from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from integrated_control.application.calibration.homing_service import HomingService
from integrated_control.application.device_diagnostics import (
    DeviceDiagnosticsController,
)
from integrated_control.application.controller import SystemController
from integrated_control.application.scheduler.scheduler import Scheduler, build_scheduler
from integrated_control.application.scheduler.feedback import FeedbackPolicy
from integrated_control.application.scheduler.algorithm import AlgorithmConfig
from integrated_control.application.device_manager import DeviceManager
from integrated_control.devices.position_sensor import PositionSensor
from integrated_control.devices.stage import Stage
from integrated_control.devices.gripper import Gripper
from integrated_control.devices.pipette import Pipette
from integrated_control.devices.spin_coater import SpinCoater
from integrated_control.devices.vacuum_station import VacuumStation
from integrated_control.devices.valve import Valve
from integrated_control.domain.errors import ConfigurationError
from integrated_control.domain.models import HomingConfig, Pose2D
from integrated_control.infrastructure.drivers.native import (
    GripperDriver,
    PipetteDriver,
    PositionSensorDriver,
    SpinCoaterDriver,
    StageDriver,
    VacuumStationDriver,
    ValveDriver,
)
from integrated_control.infrastructure.drivers.native.gripper_driver import (
    GripperDriverConfig,
)
from integrated_control.infrastructure.drivers.native.pipette_driver import (
    PipetteDriverConfig,
)
from integrated_control.infrastructure.drivers.native.stage_driver import (
    StageDriverConfig,
)
from integrated_control.infrastructure.drivers.native.spin_coater_driver import (
    SpinCoaterDriverConfig,
)
from integrated_control.infrastructure.drivers.native.vacuum_station_driver import (
    VacuumStationDriverConfig,
)
from integrated_control.infrastructure.simulation import (
    SimulatedCamera,
    SimulatedGripper,
    SimulatedHeater,
    SimulatedPipette,
    SimulatedPositionSensor,
    SimulatedSpinCoater,
    SimulatedStage,
    SimulatedVacuumStation,
    SimulatedValve,
)
from integrated_control.infrastructure.transports.modbus_rtu import ModbusRtuClient
from integrated_control.infrastructure.transports.serial_transport import (
    SerialSettings,
    SerialTransport,
)
from integrated_control.infrastructure.persistence import StageStateStore


@dataclass(frozen=True)
class ApplicationContext:
    """Expose the assembled controller, devices, coordinates, diagnostics, and scheduler."""
    controller: SystemController
    project_root: Path
    coordinates: dict[str, Any]
    scheduler: Scheduler | None = None


def _load_json_yaml(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON-compatible YAML configuration file and report invalid input."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Missing configuration file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid configuration in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration root must be an object: {path}")
    return data


def build_application(
    project_root: Path | None = None,
    *,
    mode: str | None = None,
) -> ApplicationContext:
    """Load configuration and assemble devices, controller, diagnostics, and scheduler."""
    root = project_root or Path(__file__).resolve().parents[2]
    system_config = _load_json_yaml(root / "config" / "system.yaml")
    device_config = _load_json_yaml(root / "config" / "devices.yaml")
    coordinate_config = _load_json_yaml(root / "config" / "coordinates.yaml")
    safety_config = _load_json_yaml(root / "config" / "safety_limits.yaml")

    selected_mode = system_config.get("mode") if mode is None else mode
    if selected_mode not in {"simulation", "native_hardware", "hardware"}:
        raise ConfigurationError(
            "mode must be simulation, native_hardware, or hardware; "
            f"received {selected_mode!r}"
        )

    stage_values = device_config.get("stage", {})
    sensor_values = device_config.get("position_sensor", {})
    spin_values = device_config.get("spin_coater", {})
    heater_values = device_config.get("heater", {})
    vacuum_values = device_config.get("vacuum_station", {})
    gripper_values = device_config.get("gripper", {})
    pipette_values = device_config.get("pipette", {})
    valve_values = device_config.get("valve", {})
    offsets = coordinate_config.get("stage_origin_offset", {})
    stage_state_store = StageStateStore(
        root / "runtime_data" / "stage_state.json",
        default_offset_x=float(offsets.get("x", 0.0)),
        default_offset_y=float(offsets.get("y", 0.0)),
    )

    try:
        if selected_mode in {"native_hardware", "hardware"}:
            (
                stage,
                sensor,
                gripper,
                pipette,
                spin_coater,
                vacuum_station,
                valve,
            ) = build_native_devices(
                device_config, stage_state_store=stage_state_store
            )
        else:
            stage, sensor = _build_simulated_motion_devices(
                stage_values, sensor_values
            )
            gripper, pipette, valve = _build_simulated_handling_devices(
                gripper_values, pipette_values, valve_values
            )
            spin_coater = SimulatedSpinCoater(
                max_rpm=int(spin_values.get("max_rpm", 10000))
            )
            vacuum_station = SimulatedVacuumStation()
        if selected_mode == "simulation":
            stage.set_offset("x", float(offsets.get("x", 0.0)))
            stage.set_offset("y", float(offsets.get("y", 0.0)))
        homing_config = HomingConfig(
            step=float(safety_config["homing_step"]),
            max_steps=int(safety_config["homing_max_steps"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid device or safety configuration: {exc}") from exc

    spin_coater_pose = (
        coordinate_config.get("stations", {})
        .get("spin_coater", {})
        .get("gripper", {})
    )
    devices = DeviceManager(
        [
            stage,
            sensor,
            gripper,
            pipette,
            spin_coater,
            SimulatedHeater(
                slots=int(heater_values.get("slots", 8)),
                maximum_temperature_c=float(
                    heater_values.get("maximum_temperature_c", 200.0)
                ),
            ),
            vacuum_station,
            valve,
            SimulatedCamera(
                {
                    ("spin_coater", "groove"): Pose2D(
                        float(spin_coater_pose.get("x", 48.5)),
                        float(spin_coater_pose.get("y", 64.5)),
                        0.0,
                    )
                }
            ),
        ]
    )
    controller = SystemController(
        devices,
        HomingService(stage, sensor, homing_config),
    )
    scheduler_settings = _load_json_yaml(root / "config" / "scheduler.yaml")
    try:
        executer_settings = dict(scheduler_settings["executer"])
        cooldown_s = executer_settings.pop("cooldown_s", 0.1)
        scheduler_algorithm = AlgorithmConfig(**executer_settings)
        scheduler = build_scheduler(algorithm_config=scheduler_algorithm, cooldown_s=cooldown_s)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid Executer algorithm configuration: {exc}") from exc
    for device_id, values in device_config.items():
        if isinstance(values, dict) and "continuous_failure_timeout_s" in values:
            timeout = float(values["continuous_failure_timeout_s"])
            scheduler.actor.configure_feedback(device_id, FeedbackPolicy(timeout, timeout))
    return ApplicationContext(controller, root, coordinate_config, scheduler)


def build_device_diagnostics(
    project_root: Path | None = None,
    *,
    mode: str | None = None,
) -> DeviceDiagnosticsController:
    """Build every implemented native device for attended debugging."""
    root = project_root or Path(__file__).resolve().parents[2]
    system_config = _load_json_yaml(root / "config" / "system.yaml")
    device_config = _load_json_yaml(root / "config" / "devices.yaml")
    coordinate_config = _load_json_yaml(root / "config" / "coordinates.yaml")
    safety_config = _load_json_yaml(root / "config" / "safety_limits.yaml")
    selected_mode = mode or system_config.get("mode")
    if selected_mode not in {
        "simulation",
        "native_hardware",
        "hardware",
    }:
        raise ConfigurationError(
            f"Unsupported device diagnostics mode: {selected_mode!r}"
        )

    offsets = coordinate_config.get("stage_origin_offset", {})
    stage_state_store = StageStateStore(
        root / "runtime_data" / "stage_state.json",
        default_offset_x=float(offsets.get("x", 0.0)),
        default_offset_y=float(offsets.get("y", 0.0)),
    )

    try:
        if selected_mode in {"native_hardware", "hardware"}:
            (
                stage,
                sensor,
                gripper,
                pipette,
                spin_coater,
                vacuum_station,
                valve,
            ) = build_native_devices(
                device_config, stage_state_store=stage_state_store
            )
        else:
            stage, sensor = _build_simulated_motion_devices(
                device_config.get("stage", {}),
                device_config.get("position_sensor", {}),
            )
            gripper, pipette, valve = _build_simulated_handling_devices(
                device_config.get("gripper", {}),
                device_config.get("pipette", {}),
                device_config.get("valve", {}),
            )
            spin_coater = SimulatedSpinCoater(
                max_rpm=int(
                    device_config.get("spin_coater", {}).get("max_rpm", 10000)
                )
            )
            vacuum_station = SimulatedVacuumStation()
        if selected_mode not in {"native_hardware", "hardware"}:
            stage.set_offset("x", float(offsets.get("x", 0.0)))
            stage.set_offset("y", float(offsets.get("y", 0.0)))
        homing_config = HomingConfig(
            step=float(safety_config["homing_step"]),
            max_steps=int(safety_config["homing_max_steps"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"Invalid device diagnostics configuration: {exc}"
        ) from exc

    devices = DeviceManager(
        [
            stage,
            sensor,
            gripper,
            pipette,
            spin_coater,
            vacuum_station,
            valve,
        ]
    )
    return DeviceDiagnosticsController(
        devices,
        HomingService(stage, sensor, homing_config),
    )


def _build_simulated_motion_devices(
    stage_values: dict[str, Any],
    sensor_values: dict[str, Any],
) -> tuple[Stage, PositionSensor]:
    """Assemble simulated stage and sensor devices using the configured limits and offsets."""
    stage = SimulatedStage(
        initial_x=float(stage_values["initial_x"]),
        initial_y=float(stage_values["initial_y"]),
        minimum=float(stage_values["minimum_x"]),
        maximum=float(stage_values["maximum_x"]),
    )
    sensor = SimulatedPositionSensor(
        stage,
        trigger_x=float(sensor_values["trigger_x"]),
        trigger_y=float(sensor_values["trigger_y"]),
    )
    return stage, sensor


def _serial_transport(values: dict[str, Any]) -> SerialTransport:
    """Create a transport using the non-blocking serial mode from old drivers."""
    return SerialTransport(
        SerialSettings(
            port=str(values["port"]),
            baudrate=int(values["baudrate"]),
            timeout_s=float(values.get("serial_timeout_s", 0.0)),
            response_delay_s=float(values["response_delay_s"]),
        )
    )


def _build_native_motion_devices(
    stage_values: dict[str, Any],
    sensor_values: dict[str, Any],
    stage_state_store: StageStateStore | None = None,
) -> tuple[Stage, PositionSensor]:
    """Assemble serial stage and position-sensor drivers using native communication settings."""
    stage_transport = _serial_transport(stage_values)
    sensor_transport = _serial_transport(sensor_values)
    stage = StageDriver(
        ModbusRtuClient(stage_transport),
        StageDriverConfig(
            minimum_x=float(stage_values["minimum_x"]),
            maximum_x=float(stage_values["maximum_x"]),
            minimum_y=float(stage_values["minimum_y"]),
            maximum_y=float(stage_values["maximum_y"]),
            pulses_x=int(stage_values["pulses_x"]),
            pulses_y=int(stage_values["pulses_y"]),
            speed_x=int(stage_values["speed_x"]),
            acceleration_x=int(stage_values["acceleration_x"]),
            deceleration_x=int(stage_values["deceleration_x"]),
            speed_y=int(stage_values["speed_y"]),
            acceleration_y=int(stage_values["acceleration_y"]),
            deceleration_y=int(stage_values["deceleration_y"]),
            movement_timeout_s=float(stage_values["timeout_s"]),
            hardware_zero_tolerance_pulses=int(
                stage_values.get("hardware_zero_tolerance_pulses", 10)
            ),
        ),
        state_store=stage_state_store,
    )
    sensor = PositionSensorDriver(ModbusRtuClient(sensor_transport))
    return stage, sensor


def _build_simulated_handling_devices(
    gripper_values: dict[str, Any],
    pipette_values: dict[str, Any],
    valve_values: dict[str, Any],
) -> tuple[Gripper, Pipette, Valve]:
    """Assemble simulated gripper and pipette devices."""
    return (
        SimulatedGripper(max_z=float(gripper_values.get("maximum_z", 100.0))),
        SimulatedPipette(
            capacity_ul=float(pipette_values.get("capacity_ul", 1000.0)),
            max_z=float(pipette_values.get("maximum_z", 100.0)),
        ),
        SimulatedValve(),
    )


def _build_native_handling_devices(
    gripper_values: dict[str, Any],
    pipette_values: dict[str, Any],
    valve_values: dict[str, Any],
) -> tuple[Gripper, Pipette, Valve]:
    """Assemble native gripper and pipette drivers with configured transports."""
    gripper_transport = _serial_transport(gripper_values)
    pipette_transport = _serial_transport(pipette_values)
    valve_transport = _serial_transport(valve_values)
    return (
        GripperDriver(
            gripper_transport,
            GripperDriverConfig(
                minimum_z=float(gripper_values["minimum_z"]),
                maximum_z=float(gripper_values["maximum_z"]),
                z_pulses_per_100=int(gripper_values["z_pulses_per_100"]),
                movement_timeout_s=float(gripper_values["timeout_s"]),
                poll_interval_s=float(gripper_values.get("poll_interval_s", 0.1)),
            ),
        ),
        PipetteDriver(
            pipette_transport,
            PipetteDriverConfig(
                minimum_z=float(pipette_values["minimum_z"]),
                maximum_z=float(pipette_values["maximum_z"]),
                z_pulses_per_100=int(pipette_values["z_pulses_per_100"]),
                capacity_ul=float(pipette_values["capacity_ul"]),
                movement_timeout_s=float(pipette_values["timeout_s"]),
                poll_interval_s=float(pipette_values.get("poll_interval_s", 0.1)),
            ),
        ),
        ValveDriver(ModbusRtuClient(valve_transport)),
    )


def _build_native_process_devices(
    spin_values: dict[str, Any],
    vacuum_values: dict[str, Any],
) -> tuple[SpinCoater, VacuumStation]:
    """Assemble native spin, lid, and valve drivers and the available heater/camera implementations."""
    spin_transport = _serial_transport(spin_values)
    vacuum_transport = _serial_transport(vacuum_values)
    return (
        SpinCoaterDriver(
            ModbusRtuClient(
                spin_transport,
                continuous_failure_timeout_s=float(
                    spin_values.get("continuous_failure_timeout_s", 0.8)
                ),
                retry_interval_s=float(
                    spin_values.get("retry_interval_s", 0.1)
                ),
            ),
            SpinCoaterDriverConfig(
                max_rpm=int(spin_values["max_rpm"]),
                electronic_gear_ratio=int(
                    spin_values["electronic_gear_ratio"]
                ),
                maximum_single_revolution_position=int(
                    spin_values["maximum_single_revolution_position"]
                ),
                glass_origin_position=int(spin_values["glass_origin_position"]),
                home_motion_time_s=float(spin_values["home_motion_time_s"]),
                home_poll_start_delay_s=float(
                    spin_values.get("home_poll_start_delay_s", 1.5)
                ),
                home_poll_interval_s=float(
                    spin_values.get("home_poll_interval_s", 0.25)
                ),
                home_position_tolerance_counts=int(
                    spin_values.get("home_position_tolerance_counts", 10000)
                ),
                communication_compensation_s=float(
                    spin_values["communication_compensation_s"]
                ),
            ),
        ),
        VacuumStationDriver(
            vacuum_transport,
            VacuumStationDriverConfig(
                open_position=int(vacuum_values["open_position"]),
                close_position=int(vacuum_values["close_position"]),
                initial_speed=int(vacuum_values["initial_speed"]),
                open_speed=int(vacuum_values["open_speed"]),
                close_speed=int(vacuum_values["close_speed"]),
                acceleration_time=int(vacuum_values["acceleration_time"]),
                deceleration_time=int(vacuum_values["deceleration_time"]),
                command_delay_s=float(vacuum_values["command_delay_s"]),
                open_motion_time_s=float(vacuum_values["open_motion_time_s"]),
                close_motion_time_s=float(vacuum_values["close_motion_time_s"]),
            ),
        ),
    )


def build_native_devices(
    device_config: dict[str, Any],
    *,
    stage_state_store: StageStateStore | None = None,
) -> tuple[
    Stage,
    PositionSensor,
    Gripper,
    Pipette,
    SpinCoater,
    VacuumStation,
    Valve,
]:
    """Build every native device currently supported by the PC application."""
    stage, sensor = _build_native_motion_devices(
        device_config["stage"],
        device_config["position_sensor"],
        stage_state_store,
    )
    gripper, pipette, valve = _build_native_handling_devices(
        device_config["gripper"],
        device_config["pipette"],
        device_config["valve"],
    )
    spin_coater, vacuum_station = _build_native_process_devices(
        device_config["spin_coater"],
        device_config["vacuum_station"],
    )
    return (
        stage,
        sensor,
        gripper,
        pipette,
        spin_coater,
        vacuum_station,
        valve,
    )
