"""Application workflows."""

from integrated_control.application.workflows.zksz import ZkszWorkflow, run_zksz


def __getattr__(name):
    """Resolve a missing attribute through the wrapped dependency."""
    if name in ("BatchParams", "run_batch_zksz"):
        from . import batch_zksz
        return getattr(batch_zksz, name)
    raise AttributeError(name)

__all__ = ["BatchParams", "ZkszWorkflow", "run_batch_zksz", "run_zksz"]
