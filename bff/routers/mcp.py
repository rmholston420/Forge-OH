"""MCP + integrations router stub."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/integrations/mcp")
async def list_mcp_servers() -> dict:
    return {"data": [], "stub": True}


@router.get("/mcp/{server_id}")
async def get_mcp_server(server_id: str) -> dict:
    return {"data": None, "stub": True}
