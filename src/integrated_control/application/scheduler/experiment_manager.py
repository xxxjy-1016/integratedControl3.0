"""Register experiment compilers without coupling scheduling to device protocols."""
from typing import Any, Mapping

from .contracts import ExperimentCompiler, TaskSpec
from .task_manager import TaskManager


class ExperimentManager:
    """Compile experiment parameters into registered task specifications."""
    def __init__(self, tasks: TaskManager) -> None:
        """Initialize experiment manager dependencies and internal state."""
        self._tasks = tasks
        self._compilers: dict[str, ExperimentCompiler] = {}
        self.register("zksz", self._compile_zksz)

    def register(self, name: str, compiler: ExperimentCompiler) -> None:
        """Register the compiler for an experiment kind, rejecting duplicate kinds."""
        if name in self._compilers:
            raise ValueError("Experiment compiler already registered")
        self._compilers[name] = compiler

    def submit(self, name: str, parameters: Mapping[str, Any]) -> tuple[TaskSpec, ...]:
        """Compile experiment parameters and submit the resulting task graph to TaskManager."""
        specs = tuple(self._compilers[name](parameters))
        self._tasks.submit(specs)
        return specs

    @staticmethod
    def _compile_zksz(parameters: Mapping[str, Any]) -> tuple[TaskSpec, ...]:
        """Compile each glass into dependent preparation/loading and pickup/return tasks."""
        experiment_id = str(parameters["experiment_id"])
        glasses = tuple(parameters["glass_ids"])
        if not experiment_id or len(set(glasses)) != len(glasses):
            raise ValueError("Unique glass ids and experiment id are required")
        if any(type(n) is not int or n < 0 for n in glasses):
            raise ValueError("Glass ids must be nonnegative integers")
        specs = []
        for n in glasses:
            first = f"{experiment_id}:{n}:step1"
            second = f"{experiment_id}:{n}:step2"
            specs.extend((
                TaskSpec(first, "step1", {"n": n}),
                TaskSpec(second, "step2", {"n": n}, (first,)),
            ))
        return tuple(specs)
