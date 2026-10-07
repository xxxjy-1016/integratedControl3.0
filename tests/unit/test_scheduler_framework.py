import unittest
from integrated_control.application.scheduler import algorithm, build_scheduler
from integrated_control.application.scheduler.contracts import TaskSpec, TaskStatus
from integrated_control.domain.results import ActionResult


class SchedulerFrameworkTests(unittest.TestCase):
    """Group checks for scheduler framework tests."""
    def test_bootstrap_exposes_framework_without_running_tasks(self):
        """Check bootstrap exposes framework without running tasks."""
        from pathlib import Path
        from integrated_control.bootstrap import build_application
        application = build_application(Path(__file__).resolve().parents[2], mode="simulation")
        self.assertIsNotNone(application.scheduler)
        self.assertEqual((), application.scheduler.task_manager.snapshot())

    def test_two_step_dependency_unlocks_on_actor_result(self):
        """Check two step dependency unlocks on actor result."""
        system = build_scheduler()
        first, second = system.experiment_manager.submit("zksz", {"experiment_id": "run", "glass_ids": [0]})
        self.assertEqual([first.task_id], [r.spec.task_id for r in system.viewer.ready()])
        system.task_manager.claim(first.task_id, "request")
        system.task_manager.actor_update(first.task_id, "request", TaskStatus.RUNNING)
        system.task_manager.actor_update(first.task_id, "request", TaskStatus.SUCCEEDED, ActionResult.done())
        self.assertEqual([second.task_id], [r.spec.task_id for r in system.viewer.ready()])

    def test_claim_idempotency_and_stale_result_rejection(self):
        """Check claim idempotency and stale result rejection."""
        system = build_scheduler()
        system.task_manager.submit([TaskSpec("task", "step1")])
        first = system.task_manager.claim("task", "request")
        self.assertEqual(first, system.task_manager.claim("task", "request"))
        with self.assertRaises(ValueError):
            system.task_manager.claim("task", "other")
        with self.assertRaises(ValueError):
            system.task_manager.actor_update("task", "stale", TaskStatus.RUNNING)

    def test_cycle_rejected_without_partial_submission(self):
        """Check cycle rejected without partial submission."""
        system = build_scheduler()
        with self.assertRaises(ValueError):
            system.task_manager.submit([TaskSpec("a", "step1", dependencies=("b",)), TaskSpec("b", "step2", dependencies=("a",))])
        self.assertEqual((), system.task_manager.snapshot())


    def test_actor_confirm_can_reject_incomplete_evidence(self):
        """Check actor confirm can reject incomplete evidence."""
        system = build_scheduler()
        system.actor.register("step1", lambda task: ActionResult.done(),
            confirm=lambda task, result: ActionResult.failed("NO_EVIDENCE", "missing"))
        self.assertEqual("NO_EVIDENCE", system.actor.execute(TaskSpec("t", "step1")).error_code)

    def test_view_does_not_expose_mutable_storage(self):
        """Check view does not expose mutable storage."""
        system = build_scheduler()
        system.viewer.publish_confirmed("samples", {"glass": {"position": "heater"}})
        system.viewer.snapshot()["samples"]["glass"]["position"] = "tray"
        self.assertEqual("heater", system.viewer.snapshot()["samples"]["glass"]["position"])

