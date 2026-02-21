from fastapi import Request

from src.api.app_runtime import ApiRuntime


def get_runtime(request: Request) -> ApiRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeError("ApiRuntime is not initialized.")
    return runtime
