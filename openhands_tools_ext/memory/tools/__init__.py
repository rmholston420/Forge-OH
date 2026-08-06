"""OpenHands SDK tools that surface Forge-OH's memory subsystem to the agent.

Each submodule registers exactly one tool via ``register_tool`` at import
time. To make a tool available inside the agent-server:

    python -m openhands.agent_server \
        --import-modules openhands_tools_ext.memory.tools.consult_memory ...

Stage 5.6b (ADR-024 follow-up) introduces ``consult_memory``; further
tiers (temporal, procedural writes) are deferred until their DoD arrives.
"""
