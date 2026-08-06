"""Stage 6.7 — code-execution invocation mode + progressive disclosure.

Three SDK-registered tools plus one routing helper.  See
``.openhands/decisions/013-code-execution-invocation-mode.md`` for the
architectural rationale (short version: the four illustrative snippets in
the spec don't have wire points in Forge-OH; we ship SDK tools the model
calls explicitly, and route ``code_execute`` through the same
``BashCommand``-based sandbox tier the agent-server already uses for every
``bash`` action).

Import any of the submodules at agent-server startup to register the tools:

    --import-modules openhands_tools_ext.tool_invocation.code_exec_mode
    --import-modules openhands_tools_ext.tool_invocation.progressive_disclosure

``router`` is not a tool; it's a pure helper the system-prompt hint
references.
"""

__all__: list[str] = []
