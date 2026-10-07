"""Generic scheduling framework and offline visualization CLI."""
def build_scheduler(**kwargs):
    """Lazily construct the framework; keep algorithm CLI imports independent."""
    from .scheduler import build_scheduler as build
    return build(**kwargs)


def __getattr__(name):
    """Resolve a missing attribute through the wrapped dependency."""
    if name == "Scheduler":
        from .scheduler import Scheduler
        return Scheduler
    raise AttributeError(name)

__all__ = ["algorithm", "cli", "Scheduler", "build_scheduler"]
