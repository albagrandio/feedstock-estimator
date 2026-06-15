"""Pipeline package for the CR & NR estimator.

Each pipeline takes a `PipelineInput` and returns a `PipelineResult`. The router
maps (country, module, optimize) to the right pipeline function. Only the Spain
NR (SIGPAC) pipeline is fully implemented in this first vertical slice; the rest
are stubs that raise `NotImplementedYet` with a clear message.
"""

from src.pipelines.router import (
    PipelineInput,
    PipelineResult,
    NotImplementedYet,
    get_pipeline,
    run,
)

__all__ = [
    "PipelineInput",
    "PipelineResult",
    "NotImplementedYet",
    "get_pipeline",
    "run",
]
