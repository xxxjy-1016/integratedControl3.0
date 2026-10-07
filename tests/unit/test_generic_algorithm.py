import itertools
import unittest

from integrated_control.application.scheduler import algorithm as A, build_scheduler
from integrated_control.application.scheduler.contracts import TaskSpec


class GenericAlgorithmTests(unittest.TestCase):
    """Group checks for generic algorithm tests."""
    def test_all_methods_handle_non_glass_tasks(self):
        """Check all methods handle non glass tasks."""
        tasks = [A.SchedulingTask("mix", 2, resources={"robot": 1}),
                 A.SchedulingTask("scan", 1, ("mix",), resources={"robot": 1}),
                 A.SchedulingTask("wash", 3, resources={"robot": 1})]
        for method in ("fifo", "greedy", "exact", "beam", "auto"):
            with self.subTest(method=method):
                plan = A.schedule(tasks, {"robot": 1}, A.AlgorithmConfig(method, time_limit_s=1))
                self.assertTrue(plan.feasible, plan.errors)
                self.assertEqual(6, plan.makespan)
                ends = {e.task_id: e.end for e in plan.commands}
                starts = {e.task_id: e.start for e in plan.commands}
                self.assertGreaterEqual(starts["scan"], ends["mix"])

    def test_search_is_complete_by_default_and_depth_can_be_limited(self):
        """Check default full search and the optional positive-depth override."""
        tasks = [A.SchedulingTask(f"task-{index}", 1) for index in range(5)]
        complete = A.schedule(tasks, {}, A.AlgorithmConfig("fifo"))
        limited = A.schedule(tasks, {}, A.AlgorithmConfig("fifo", lookahead_depth=2),
                             horizon=2)
        self.assertEqual(5, len(complete.commands))
        self.assertEqual(2, len(limited.commands))
        self.assertFalse(limited.proven_optimal)

    def test_max_lag_can_require_idle_before_predecessor(self):
        """Check max lag can require idle before predecessor."""
        tasks = [A.SchedulingTask("prepare", 1), A.SchedulingTask("read", 1, ("prepare",),
                 release_at=10, time_links=(A.TimeLink("prepare", 0, 0),))]
        plan = A.schedule(tasks, {}, A.AlgorithmConfig("exact", time_limit_s=1))
        self.assertTrue(plan.feasible)
        self.assertTrue(plan.proven_optimal)
        self.assertEqual([(9, 10), (10, 11)], [(c.start, c.end) for c in plan.commands])


    def test_resource_hold_and_return_between_tasks(self):
        """Check resource hold and return between tasks."""
        tasks = [A.SchedulingTask("load", 1, resources={"slot": 1}, retain_resources=("slot",)),
                 A.SchedulingTask("unload", 1, ("load",), resource_returns={"slot": 1}),
                 A.SchedulingTask("next", 1, resources={"slot": 1})]
        plan = A.schedule(tasks, {"slot": 1}, A.AlgorithmConfig("exact", time_limit_s=1))
        self.assertTrue(plan.feasible)
        self.assertEqual(3, plan.makespan)


    def test_impossible_graph_is_not_claimed_optimal(self):
        """Check impossible graph is not claimed optimal."""
        plan = A.schedule([A.SchedulingTask("impossible", 3, deadline_at=2)], {}, A.AlgorithmConfig("exact"))
        self.assertFalse(plan.feasible)
        self.assertFalse(plan.proven_optimal)

    def test_invalid_configuration_and_cycles_are_rejected(self):
        """Check invalid configuration and cycles are rejected."""
        self.assertIsNone(A.AlgorithmConfig("fifo").lookahead_depth)
        with self.assertRaises(ValueError):
            A.AlgorithmConfig("unknown")
        with self.assertRaises(ValueError):
            A.AlgorithmConfig("beam", beam_width=0)
        for invalid_depth in (0, -1, 1.5, True):
            with self.subTest(invalid_depth=invalid_depth), self.assertRaises(ValueError):
                A.AlgorithmConfig("fifo", lookahead_depth=invalid_depth)
        with self.assertRaises(ValueError):
            A.schedule([A.SchedulingTask("a", 1, ("b",)), A.SchedulingTask("b", 1, ("a",))],
                       {}, A.AlgorithmConfig("exact"))

    def test_executer_requires_manual_algorithm_and_configuration_changes_selection(self):
        """Check executer requires manual algorithm and configuration changes selection."""
        system = build_scheduler(clock=lambda: 0)
        system.task_manager.submit([TaskSpec("first", "mix", {"scheduling": {"duration_s": 5}}),
                                   TaskSpec("second", "measure", {"scheduling": {"duration_s": 1, "priority": 2}})])
        with self.assertRaises(ValueError):
            system.executer.propose(lambda task, view: True)
        system.executer.configure(A.AlgorithmConfig("fifo"))
        self.assertEqual("first", system.executer.propose(lambda task, view: True).task_id)
        system.executer.configure(A.AlgorithmConfig("greedy"))
        self.assertEqual("second", system.executer.propose(lambda task, view: True).task_id)

    def test_executer_searches_general_dependencies(self):
        """Check executer searches general dependencies."""
        for method in ("exact", "beam", "auto"):
            system = build_scheduler(clock=lambda: 0, algorithm_config=A.AlgorithmConfig(method, time_limit_s=1))
            system.task_manager.submit([TaskSpec("slow", "any", {"scheduling": {"duration_s": 5}}),
                TaskSpec("urgent", "other", {"scheduling": {"duration_s": 1, "deadline_at": 2}})])
            self.assertEqual("urgent", system.executer.propose(lambda task, view: True).task_id)

    def test_online_search_calls_schedule_once_after_preview(self):
        """Check online search calls schedule once after preview."""
        from unittest.mock import patch
        for method in ("fifo", "greedy", "exact", "beam", "auto"):
            with self.subTest(method=method):
                system = build_scheduler(clock=lambda: 0,
                    algorithm_config=A.AlgorithmConfig(method, time_limit_s=1))
                system.task_manager.submit([
                    TaskSpec("rejected", "any", {"scheduling": {"duration_s": 1, "priority": 10}}),
                    TaskSpec("allowed", "any", {"scheduling": {"duration_s": 2}}),
                    TaskSpec("later", "any", {"scheduling": {"duration_s": 1}}, ("rejected",))])
                checked = []
                def preview(task, snapshot):
                    """Preview."""
                    checked.append(task.task_id)
                    return task.task_id != "rejected"
                with patch.object(A, "schedule", wraps=A.schedule) as search:
                    best = system.executer.propose(preview)
                self.assertEqual(["rejected", "allowed"], checked)
                search.assert_called_once()
                self.assertEqual("allowed", best.task_id)
                self.assertIsNone(search.call_args.kwargs["horizon"])
                self.assertEqual({"allowed"}, set(search.call_args.kwargs["first_candidates"]))
                self.assertEqual({"rejected", "allowed", "later"},
                                 {t.task_id for t in search.call_args.args[0]})

    def test_no_preview_candidates_skips_search(self):
        """Check no preview candidates skips search."""
        from unittest.mock import patch
        system = build_scheduler(clock=lambda: 0, algorithm_config=A.AlgorithmConfig("exact"))
        system.task_manager.submit([TaskSpec("one", "any", {"scheduling": {"duration_s": 1}})])
        with patch.object(A, "schedule", wraps=A.schedule) as search:
            self.assertIsNone(system.executer.propose(lambda task, snapshot: False))
        search.assert_not_called()

    def test_first_candidate_restriction_does_not_exclude_future_tasks(self):
        """Check first candidate restriction does not exclude future tasks."""
        tasks = [A.SchedulingTask("excluded_now", 1), A.SchedulingTask("allowed", 2),
                 A.SchedulingTask("future", 1, ("excluded_now",))]
        for method in ("exact", "beam", "auto"):
            with self.subTest(method=method):
                plan = A.schedule(tasks, {}, A.AlgorithmConfig(method, time_limit_s=1),
                                  first_candidates={"allowed"})
                self.assertTrue(plan.feasible, plan.errors)
                self.assertEqual(["allowed", "excluded_now", "future"],
                                 [c.task_id for c in plan.commands])

    def test_online_search_cannot_delay_first_action_to_satisfy_later_max_lag(self):
        """Check online search cannot delay first action to satisfy later max lag."""
        tasks = [A.SchedulingTask("prepare", 1, priority=10), A.SchedulingTask("idle_work", 9),
                 A.SchedulingTask("read", 1, ("prepare",), release_at=10,
                                  time_links=(A.TimeLink("prepare", 0, 0),))]
        for method in ("exact", "beam", "auto"):
            with self.subTest(method=method):
                plan = A.schedule(tasks, {}, A.AlgorithmConfig(method, time_limit_s=1),
                                  first_candidates={"prepare", "idle_work"})
                self.assertTrue(plan.feasible, plan.errors)
                self.assertEqual("idle_work", plan.commands[0].task_id)
                self.assertEqual(0, plan.commands[0].start)
        rejected = A.schedule(tasks, {}, A.AlgorithmConfig("exact", time_limit_s=1),
                              first_candidates={"prepare"})
        self.assertFalse(rejected.feasible)

    def test_search_uses_prepared_candidate_spec(self):
        """Check search uses prepared candidate spec."""
        from dataclasses import replace
        system = build_scheduler(clock=lambda: 0,
                                 algorithm_config=A.AlgorithmConfig("exact", time_limit_s=1))
        system.actor.configure_resources({"robot": 1})
        system.task_manager.submit([TaskSpec("one", "any", {"scheduling": {"duration_s": 1}})])
        def prepare(task, snapshot):
            """Prepare."""
            return replace(task, parameters={**task.parameters, "slot": 3}, resources={"robot": 1})
        best = system.executer.propose(lambda task, view: True, prepare)
        self.assertEqual(3, best.parameters["slot"])
        self.assertEqual({"robot": 1}, best.resources)

    def test_exact_matches_independent_enumeration_of_serial_orders(self):
        """Check exact matches independent enumeration of serial orders."""
        tasks = [A.SchedulingTask("a", 2, release_at=3), A.SchedulingTask("b", 1, deadline_at=4),
                 A.SchedulingTask("c", 3)]
        best = float("inf")
        for order in itertools.permutations(tasks):
            now = 0
            for task in order:
                now = max(now, task.release_at) + task.duration_s
                if task.deadline_at is not None and now > task.deadline_at:
                    break
            else:
                best = min(best, now)
        plan = A.schedule(tasks, {}, A.AlgorithmConfig("exact", time_limit_s=1))
        self.assertTrue(plan.proven_optimal)
        self.assertEqual(best, plan.makespan)
