from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from threading import RLock

from integrated_control.domain.errors import PersistenceError


@dataclass(frozen=True)
class StagePersistentState:
    stage_at_origin: bool = False
    offset_x: float = 0.0
    offset_y: float = 0.0


class StageStateStore:
    """Persist the stage position flag and operator-calibrated offsets."""

    def __init__(
        self,
        path: Path,
        *,
        default_offset_x: float = 0.0,
        default_offset_y: float = 0.0,
    ) -> None:
        self._path = path
        self._lock = RLock()
        self._default = StagePersistentState(
            stage_at_origin=False,
            offset_x=float(default_offset_x),
            offset_y=float(default_offset_y),
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> StagePersistentState:
        with self._lock:
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("state root must be an object")
                stage_at_origin = data["stage_at_origin"]
                if not isinstance(stage_at_origin, bool):
                    raise ValueError("stage_at_origin must be a boolean")
                return StagePersistentState(
                    stage_at_origin=stage_at_origin,
                    offset_x=float(data["offset_x"]),
                    offset_y=float(data["offset_y"]),
                )
            except FileNotFoundError:
                return self._default
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                # An unreadable state can never safely prove that the stage is at zero.
                return self._default
            except OSError as exc:
                raise PersistenceError(
                    f"Cannot read stage state from {self._path}: {exc}"
                ) from exc

    def save_origin(self, stage_at_origin: bool) -> StagePersistentState:
        with self._lock:
            state = replace(self.load(), stage_at_origin=bool(stage_at_origin))
            self._write(state)
            return state

    def save_offsets(self, offset_x: float, offset_y: float) -> StagePersistentState:
        with self._lock:
            state = replace(
                self.load(),
                offset_x=float(offset_x),
                offset_y=float(offset_y),
            )
            self._write(state)
            return state

    def _write(self, state: StagePersistentState) -> None:
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self._path)
        except OSError as exc:
            raise PersistenceError(
                f"Cannot write stage state to {self._path}: {exc}"
            ) from exc
