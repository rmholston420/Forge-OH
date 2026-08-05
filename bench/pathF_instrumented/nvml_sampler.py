"""Compat shim. The canonical NVML sampler is now at bench._common.nvml_sampler.

Existing F.1b harness (bench/pathF_instrumented/bench_pathF.py) does
    `from nvml_sampler import GpuSampler`
via sys.path insertion, so this re-export keeps it working unchanged.
"""
from bench._common.nvml_sampler import (  # noqa: F401
    GpuSampler,
    GpuStats,
)
