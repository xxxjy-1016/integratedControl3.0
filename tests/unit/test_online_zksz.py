import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from integrated_control.bootstrap import build_application
from integrated_control.application.scheduler import build_scheduler
from integrated_control.application.scheduler.algorithm import AlgorithmConfig
from integrated_control.application.workflows.batch_zksz import BatchParams
from integrated_control.application.scheduler.contracts import TaskStatus
from integrated_control.application.scheduler.decision_preview import OnlineTiming
from integrated_control.application.workflows.batch_zksz import run_batch_zksz


class OnlineZkszTests(unittest.TestCase):
    """Group checks for online zksz tests."""
    def setUp(self):
        """Set up."""
        self.now = 0.0
        self.app = build_application(Path(__file__).resolve().parents[2], mode="simulation")
        self.app.controller.start()
        system = build_scheduler(clock=lambda: self.now,
                                 algorithm_config=AlgorithmConfig("greedy", time_limit_s=1))
        self.app = replace(self.app, scheduler=system)
        self.timing = OnlineTiming(2, 1, 5, 8, 1.5, 1.5, 0.5, 0.5)

    def tearDown(self):
        """Tear down."""
        self.app.controller.shutdown()

    def sleep(self, seconds):
        """Sleep."""
        self.now += seconds

    def workflow_type(self, fail=False):
        """Workflow type."""
        advance = self.sleep
        class Workflow:
            """Group checks for workflow."""
            def __init__(self, app, *, sleep, checkpoint, clock):
                """Initialize workflow dependencies and internal state."""
                self.checkpoint, self.clock = checkpoint, clock
            def step1(self, n, m):
                """Step1."""
                advance(1.5)
                self.checkpoint("placed", n, m, self.clock())
                advance(0.5)
                if fail:
                    raise TimeoutError("communication lost after placement")
            def step2(self, n, m):
                """Step2."""
                advance(0.5)
                self.checkpoint("picked", n, m, self.clock())
                advance(0.5)
        return Workflow

    def test_complete_online_loop_and_heater_reuse(self):
        """Check complete online loop and heater reuse."""
        with patch("integrated_control.application.workflows.batch_zksz.ZkszWorkflow", self.workflow_type()):
            report = run_batch_zksz(self.app, batch=BatchParams(2, 1, 5, 8, 2, 3), online_timing=self.timing,
                                     clock=lambda: self.now, sleep=self.sleep)
        self.assertTrue(report.success, report.errors)
        self.assertEqual(6, len(report.records))
        self.assertTrue(all(r.status == TaskStatus.SUCCEEDED for r in report.records))
        view = self.app.scheduler.viewer.snapshot()
        self.assertTrue(all(s["position"] == "tray" for s in view["samples"].values()))
        self.assertTrue(all(r["available"] == r["capacity"] for r in view["resources"].values()))

    def test_partial_failure_preserves_actual_placement_and_claims(self):
        """Check partial failure preserves actual placement and claims."""
        with patch("integrated_control.application.workflows.batch_zksz.ZkszWorkflow", self.workflow_type(fail=True)):
            report = run_batch_zksz(self.app, batch=BatchParams(2, 1, 5, 8, 2, 1), online_timing=self.timing,
                                     clock=lambda: self.now, sleep=self.sleep)
        self.assertFalse(report.success)
        self.assertEqual(TaskStatus.UNKNOWN, report.records[0].status)
        self.assertEqual(TaskStatus.BLOCKED, report.records[1].status)
        view = self.app.scheduler.viewer.snapshot()
        self.assertEqual("heater", view["samples"]["0"]["position"])
        self.assertEqual(0, view["resources"]["arm"]["available"])

    def test_nested_log_directory_is_created_before_dispatch(self):
        """Check a missing parent directory is created before tasks are claimed."""
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "runtime_data" / "batch_events.jsonl"
            with patch("integrated_control.application.workflows.batch_zksz.ZkszWorkflow",
                       self.workflow_type()):
                report = run_batch_zksz(
                    self.app, batch=BatchParams(2, 1, 5, 8, 1, 1),
                    online_timing=self.timing, clock=lambda: self.now,
                    sleep=self.sleep, log_path=str(log_path))
            events = [json.loads(line)["event"]
                      for line in log_path.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(report.success, report.errors)
        self.assertEqual(["sent", "placed", "finished", "sent", "picked", "finished"], events)
