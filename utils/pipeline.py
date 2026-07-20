from typing import Any, Callable, TypeVar

from utils.analysis_log import log_stage_failure, log_stage_info

T = TypeVar("T")


def run_stage(
    name: str,
    func: Callable[..., T],
    *args: Any,
    failures: list[dict] | None = None,
    job_post_id: int | None = None,
    stage_key: str | None = None,
    fallback_model: str | None = None,
    model_pos: int | None = 1,
    **kwargs: Any,
) -> T | None:
    """Run a pipeline stage, returning None (instead of crashing) on failure.

    Retry policy for LLM stages (when model_pos points at the model arg):
      1) primary model
      2) primary model again
      3) FALLBACK_MODEL once, if configured and different from primary

    When `failures` is provided, appends a structured record so the UI/CLI can
    notify the user and offer retry from that stage.
    """
    key = stage_key or name
    where = f" (job #{job_post_id})" if job_post_id is not None else ""
    log_stage_info(f"Starting stage '{key}'{where}")

    attempts: list[tuple[str, tuple[Any, ...]]] = [("primary", args)]
    # LLM stages: retry primary once, then optional FALLBACK_MODEL.
    if model_pos is not None:
        attempts.append(("primary-retry", args))
        if (
            fallback_model
            and 0 <= model_pos < len(args)
            and isinstance(args[model_pos], str)
            and args[model_pos] != fallback_model
        ):
            fb_args = list(args)
            fb_args[model_pos] = fallback_model
            attempts.append(("fallback", tuple(fb_args)))

    last_error: Exception | None = None
    for label, call_args in attempts:
        try:
            if label == "primary-retry":
                print(f"  (Retrying '{name}' with primary model...)")
                log_stage_info(f"Retrying stage '{key}' with primary model")
            elif label == "fallback":
                print(f"  (Trying '{name}' with FALLBACK_MODEL={fallback_model}...)")
                log_stage_info(
                    f"Retrying stage '{key}' with FALLBACK_MODEL={fallback_model}"
                )
            result = func(*call_args, **kwargs)
            if label != "primary":
                log_stage_info(f"Finished stage '{key}' via {label}")
            else:
                log_stage_info(f"Finished stage '{key}'")
            return result
        except Exception as e:
            last_error = e
            log_stage_failure(key, e, job_post_id=job_post_id)
            continue

    print(
        f"\n⚠️  {name} failed after retries"
        + (f" (incl. FALLBACK_MODEL)" if fallback_model else "")
        + f": {last_error}\n   Skipping this step and continuing."
    )
    if failures is not None and last_error is not None:
        failures.append(
            {
                "stage": key,
                "name": name,
                "error": str(last_error),
            }
        )
    return None
