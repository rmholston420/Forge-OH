"""GPU thermal guard (Slice F.16).

PRE-tool hook that blocks a turn when the hottest GPU is at or above
:envvar:`FORGE_GPU_TEMP_CUTOFF_C` (default 83 C for the Blackwell
5090, well below the ~90 C throttle floor). Reads live state from
the BFF ``GET /api/gpu`` route, so the poller in
``bff.services.gpu_monitor`` is the single source of truth.
"""
