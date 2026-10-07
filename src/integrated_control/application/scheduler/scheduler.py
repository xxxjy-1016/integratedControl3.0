"""Composition entry used by bootstrap; construction performs no hardware I/O."""
from dataclasses import dataclass
from threading import RLock
import time

from .actor import Actor
from .executer import Executer
from .experiment_manager import ExperimentManager
from .task_manager import TaskManager
from .viewer import Viewer


@dataclass(frozen=True)
class Scheduler:
    """Group the assembled scheduling roles sharing task state, Views, and a synchronization lock."""
    task_manager: TaskManager
    executer: Executer
    actor: Actor
    viewer: Viewer
    experiment_manager: ExperimentManager


def build_scheduler(*, clock=time.monotonic, algorithm_config=None, cooldown_s=0.1) -> Scheduler:
    """Assemble scheduling roles around a shared lock without starting hardware."""
    lock = RLock()
    tasks = TaskManager(lock=lock, clock=clock)
    viewer = Viewer(tasks, lock=lock)
    actor = Actor(viewer, tasks=tasks)
    return Scheduler(tasks, Executer(viewer, tasks=tasks, actor=actor,
                     config=algorithm_config, clock=clock, cooldown_s=cooldown_s), actor,
                     viewer, ExperimentManager(tasks))
