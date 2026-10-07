import unittest
from integrated_control.application.scheduler import build_scheduler
from integrated_control.application.scheduler.feedback import FeedbackPolicy, FeedbackTolerance
from integrated_control.application.scheduler.contracts import TaskSpec
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult


class FeedbackToleranceTests(unittest.TestCase):
    """Group checks for feedback tolerance tests."""
    def setUp(self):
        """Set up."""
        self.now = 0.0
        self.monitor = FeedbackTolerance(FeedbackPolicy(3.0, 3.0), clock=lambda: self.now)

    def test_incomplete_observation_is_valid(self):
        """Check incomplete observation is valid."""
        state = self.monitor.observe(DeviceState("stage", "READY", "IDLE", {}))
        self.assertTrue(state.valid)
        self.assertEqual({}, state.measurements)
        self.assertEqual(0.0, state.updated_at)

    def test_isolated_error_keeps_cache_without_refreshing_timestamp(self):
        """Check isolated error keeps cache without refreshing timestamp."""
        self.monitor.observe(DeviceState("stage", "READY", "IDLE", {"x": 1}))
        self.now = 1.0
        state = self.monitor.communication_failed("stage", "bad CRC")
        self.assertTrue(state.valid)
        self.assertEqual(0.0, state.updated_at)
        self.assertEqual(1, state.measurements["x"])

    def test_continuous_errors_expire_and_success_resets_window(self):
        """Check continuous errors expire and success resets window."""
        self.monitor = FeedbackTolerance(FeedbackPolicy(3.0, 10.0), clock=lambda: self.now)
        self.monitor.observe(DeviceState("stage", "READY", "IDLE"))
        self.monitor.communication_failed("stage", "timeout")
        self.now = 3.0
        self.assertFalse(self.monitor.communication_failed("stage", "timeout").valid)
        self.now = 3.1
        self.assertTrue(self.monitor.observe(DeviceState("stage", "READY", "IDLE")).valid)
        self.now = 3.2
        self.assertTrue(self.monitor.communication_failed("stage", "one bad frame").valid)

    def test_old_cache_is_not_usable_even_during_first_error(self):
        """Check old cache is not usable even during first error."""
        self.monitor.observe(DeviceState("stage", "READY", "IDLE"))
        self.now = 5.0
        self.assertFalse(self.monitor.communication_failed("stage", "timeout").valid)

    def test_explicit_fault_bypasses_grace(self):
        """Check explicit fault bypasses grace."""
        self.monitor.observe(DeviceState("stage", "READY", "IDLE"))
        faulted = self.monitor.observe(DeviceState("stage", "FAULT", "JAMMED", fault="jam"))
        self.assertFalse(faulted.valid)
        self.assertFalse(self.monitor.communication_failed("stage", "timeout").valid)

    def test_without_good_cache_link_error_is_not_success(self):
        """Check without good cache link error is not success."""
        self.assertFalse(self.monitor.communication_failed("stage", "timeout").valid)

    def test_actor_publishes_partial_state_and_accepts_result_without_measurements(self):
        """Check actor publishes partial state and accepts result without measurements."""
        system = build_scheduler()
        state = system.actor.observe_device(DeviceState("camera", "READY", "IDLE"))
        self.assertTrue(system.viewer.snapshot()["devices"]["camera"].valid)
        system.actor.register("step1", lambda task: ActionResult.done())
        result = system.actor.execute(TaskSpec("t", "step1"))
        self.assertTrue(result.success)
        self.assertEqual({}, result.measurements)
        self.assertIsNotNone(state.updated_at)

    def test_default_confirmation_preserves_failure(self):
        """Check default confirmation preserves failure."""
        system = build_scheduler()
        system.actor.register("step1", lambda task: ActionResult.failed("ERROR", "failed"))
        self.assertFalse(system.actor.execute(TaskSpec("t", "step1")).success)

    def test_activity_fault_is_invalid_even_without_fault_message(self):
        """Check activity fault is invalid even without fault message."""
        self.assertFalse(DeviceState("stage", "READY", "FAULT").valid)

    def test_fault_in_one_device_does_not_invalidate_another(self):
        """Check fault in one device does not invalidate another."""
        system = build_scheduler()
        system.actor.observe_device(DeviceState("camera", "READY", "IDLE"))
        system.actor.observe_device(DeviceState("stage", "FAULT", "IDLE"))
        states = system.viewer.snapshot()["devices"]
        self.assertTrue(states["camera"].valid)
        self.assertFalse(states["stage"].valid)

