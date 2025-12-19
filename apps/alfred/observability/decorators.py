from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Optional

from .config import ObservabilityConfig
from .tracer import get_tracer


def trace(
    name: Optional[str] = None,
    *,
    span_type: str = "function",
    capture_args: bool = True,
    capture_result: bool = True,
):
    """
    Decorator to trace function execution.

    Usage:
        @trace()
        def my_function(x, y):
            return x + y

        @trace(name="custom_name", span_type="llm_call")
        async def my_async_function():
            pass
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):
            tracer = get_tracer()
            config = ObservabilityConfig()

            # Prepare metadata
            metadata: dict[str, Any] = {
                "function": func.__qualname__,
                "module": func.__module__,
            }

            if capture_args and config.capture_input:
                try:
                    sig = inspect.signature(func)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    metadata["args"] = str(bound.arguments)[: config.max_payload_size]
                except Exception:  # noqa: BLE001
                    pass

            with tracer.span(span_name, span_type=span_type, metadata=metadata):
                result = func(*args, **kwargs)

                if capture_result and config.capture_output:
                    try:
                        result_str = str(result)[: config.max_payload_size]
                        tracer.log_event("function_result", result=result_str)
                    except Exception:  # noqa: BLE001
                        pass

                return result

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any):
            tracer = get_tracer()
            config = ObservabilityConfig()

            metadata: dict[str, Any] = {
                "function": func.__qualname__,
                "module": func.__module__,
            }

            if capture_args and config.capture_input:
                try:
                    sig = inspect.signature(func)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    metadata["args"] = str(bound.arguments)[: config.max_payload_size]
                except Exception:  # noqa: BLE001
                    pass

            with tracer.span(span_name, span_type=span_type, metadata=metadata):
                result = await func(*args, **kwargs)

                if capture_result and config.capture_output:
                    try:
                        result_str = str(result)[: config.max_payload_size]
                        tracer.log_event("function_result", result=result_str)
                    except Exception:  # noqa: BLE001
                        pass

                return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator

