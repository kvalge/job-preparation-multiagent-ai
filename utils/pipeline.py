from typing import Callable, TypeVar

T = TypeVar("T")


def run_stage(name: str, func: Callable[..., T], *args, **kwargs) -> T | None:
    """Run a pipeline stage, returning None (instead of crashing) on failure.

    Keeps earlier results/DB writes intact if a later stage fails.
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"\n⚠️  {name} failed: {e}\n   Skipping this step and continuing.")
        return None
