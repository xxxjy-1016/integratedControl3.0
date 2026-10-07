import unittest
from integrated_control.application.scheduler import build_scheduler
from integrated_control.application.scheduler.algorithm import AlgorithmConfig
from integrated_control.application.scheduler.contracts import TaskSpec, TaskStatus
from integrated_control.domain.results import ActionResult


class OnlineDispatchTests(unittest.TestCase):
    """Group checks for online dispatch tests."""
    def setUp(self):
        """Set up."""
        self.now = 0.0
        self.system = build_scheduler(clock=lambda: self.now, algorithm_config=AlgorithmConfig("fifo"), cooldown_s=0)
        self.system.actor.configure_resources({"arm": 1, "slot": 1})

    def test_accept_publishes_state_and_resources_together(self):
        """Check accept publishes state and resources together."""
        task = TaskSpec("one", "mix", resources={"arm": 1})
        self.system.task_manager.submit([task])
        self.system.actor.register("mix", lambda task: ActionResult.done())
        request = self.system.executer.accept(task)
        snapshot = self.system.viewer.decision_snapshot()
        self.assertEqual(TaskStatus.RUNNING, snapshot["tasks"][0].status)
        self.assertEqual(0, snapshot["resources"]["arm"]["available"])
        self.system.actor.execute_accepted(task, request)
        with self.assertRaises(ValueError):
            self.system.actor.execute_accepted(task, request)

    def test_resource_reservation_prevents_overallocation(self):
        """Check resource reservation prevents overallocation."""
        one, two = TaskSpec("one", "mix", resources={"arm": 1}), TaskSpec("two", "mix", resources={"arm": 1})
        self.system.task_manager.submit([one, two])
        self.system.executer.accept(one)
        with self.assertRaises(ValueError):
            self.system.executer.accept(two)
        self.assertEqual(TaskStatus.READY, self.system.task_manager.snapshot()[1].status)

    def test_cooldown_skips_decision_until_expiry(self):
        """Check cooldown skips decision until expiry."""
        self.system.executer.cooldown_s = 0.1
        one, two = TaskSpec("one", "mix"), TaskSpec("two", "mix")
        self.system.task_manager.submit([one, two])
        self.system.actor.register("mix", lambda task: ActionResult.done())
        request = self.system.executer.accept(one)
        calls = []
        preview = lambda task, view: calls.append(task.task_id) or True
        self.assertIsNone(self.system.executer.propose(preview))
        self.assertEqual([], calls)
        # Hardware execution does not wait for the decision cooldown.
        self.assertTrue(self.system.actor.execute_accepted(one, request).success)
        self.now = 0.099
        self.assertIsNone(self.system.executer.propose(preview))
        self.now = 0.1
        self.assertEqual("two", self.system.executer.propose(preview).task_id)

    def test_failed_claim_rolls_back_only_its_own_reservation(self):
        """Check failed claim rolls back only its own reservation."""
        task = TaskSpec("one", "mix", resources={"arm": 1})
        self.system.task_manager.submit([task])
        self.system.task_manager.claim("one", "existing")
        with self.assertRaises(ValueError):
            self.system.executer.accept(task)
        resources = self.system.viewer.snapshot()["resources"]["arm"]
        self.assertEqual(1, resources["available"])
        self.assertEqual({}, resources["allocations"])
        self.assertEqual("existing", self.system.task_manager.snapshot()[0].request_id)

    def test_other_thread_cannot_observe_half_accepted_task(self):
        """Check other thread cannot observe half accepted task."""
        from threading import Event, Thread
        from unittest.mock import patch
        task = TaskSpec("one", "mix", resources={"arm": 1})
        self.system.task_manager.submit([task])
        reserved, reading, snapshots = Event(), Event(), []
        reserve = self.system.actor.reserve_resources
        def paused_reserve(owner, resources):
            """Paused reserve."""
            reserve(owner, resources)
            reserved.set()
            self.assertTrue(reading.wait(1))
        def read():
            """Read."""
            reserved.wait(1)
            reading.set()
            snapshots.append(self.system.viewer.decision_snapshot())
        reader = Thread(target=read)
        reader.start()
        with patch.object(self.system.actor, "reserve_resources", paused_reserve):
            self.system.executer.accept(task)
        reader.join(1)
        self.assertFalse(reader.is_alive())
        self.assertEqual(TaskStatus.RUNNING, snapshots[0]["tasks"][0].status)
        self.assertEqual(0, snapshots[0]["resources"]["arm"]["available"])

    def test_invalid_cooldown_rejected(self):
        """Check invalid cooldown rejected."""
        for value in (-1, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_scheduler(cooldown_s=value)

    def test_success_unlocks_dependency_but_retains_long_lived_resource(self):
        """Check success unlocks dependency but retains long lived resource."""
        one = TaskSpec("one", "mix", resources={"arm": 1, "slot": 1}, retain_resources=("slot",))
        self.system.task_manager.submit([one, TaskSpec("two", "read", dependencies=("one",))])
        self.system.actor.register("mix", lambda task: ActionResult.done())
        request = self.system.executer.accept(one)
        self.assertTrue(self.system.actor.execute_accepted(one, request).success)
        resources = self.system.viewer.snapshot()["resources"]
        self.assertEqual(1, resources["arm"]["available"])
        self.assertEqual(0, resources["slot"]["available"])
        self.assertEqual(TaskStatus.READY, self.system.task_manager.snapshot()[1].status)

    def test_uncertain_execution_retains_resource(self):
        """Check uncertain execution retains resource."""
        def fail(task):
            """Fail."""
            raise TimeoutError("reply lost")
        task = TaskSpec("one", "mix", resources={"arm": 1})
        self.system.task_manager.submit([task])
        self.system.actor.register("mix", fail)
        request = self.system.executer.accept(task)
        self.assertFalse(self.system.actor.execute_accepted(task, request).success)
        self.assertEqual(TaskStatus.UNKNOWN, self.system.task_manager.snapshot()[0].status)
        self.assertEqual(0, self.system.viewer.snapshot()["resources"]["arm"]["available"])

    def test_late_success_cannot_unlock_after_timeout(self):
        """Check late success cannot unlock after timeout."""
        task = TaskSpec("one", "mix", resources={"arm": 1})
        self.system.task_manager.submit([task])
        self.system.task_manager.configure_tolerance("mix", pending_s=1, running_s=2)
        def slow(task):
            """Slow."""
            self.now = 3
            return ActionResult.done()
        self.system.actor.register("mix", slow)
        request = self.system.executer.accept(task)
        result = self.system.actor.execute_accepted(task, request)
        self.assertEqual("TIMED_OUT", result.status)
        self.assertEqual(0, self.system.viewer.snapshot()["resources"]["arm"]["available"])

    def test_expired_running_task_never_drives_hardware(self):
        """Check expired running task never drives hardware."""
        calls = []
        task = TaskSpec("one", "mix", resources={"arm": 1})
        self.system.task_manager.submit([task])
        self.system.task_manager.configure_tolerance("mix", pending_s=1, running_s=2)
        self.system.actor.register("mix", lambda task: calls.append(task) or ActionResult.done())
        request = self.system.executer.accept(task)
        self.now = 2
        self.system.actor.execute_accepted(task, request)
        self.assertEqual([], calls)
        self.assertEqual(0, self.system.viewer.snapshot()["resources"]["arm"]["available"])
