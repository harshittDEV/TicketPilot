"""
Tool discovery and health API endpoints.

Mounted under ``/api/v1/tools``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.integrations.contracts import ToolMetadata
from app.integrations.registry import IntegrationRegistry, get_registry

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get(
    "",
    response_model=dict,
    summary="List registered tools and their capabilities",
)
def list_tools(
    registry: IntegrationRegistry = Depends(get_registry),
) -> JSONResponse:
    """Return all currently registered tool adapters and their availability."""
    tools = registry.list_tools()
    tool_dicts = [
        t.model_dump(mode="json") if hasattr(t, "model_dump") else t
        for t in tools
    ]
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": tool_dicts,
            "message": f"Retrieved {len(tool_dicts)} registered tool(s)",
        },
    )


@router.get(
    "/{tool_name}/health",
    response_model=dict,
    summary="Check health and operational status of a tool",
)
async def check_tool_health(
    tool_name: str,
    registry: IntegrationRegistry = Depends(get_registry),
) -> JSONResponse:
    """Run diagnostics on a specific tool adapter."""
    if not registry.is_registered(tool_name) and not (
        hasattr(registry, "is_tool_registered") and registry.is_tool_registered(tool_name)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' is not registered",
        )

    health_info = await registry.check_tool_health(tool_name)
    status_code = status.HTTP_200_OK if health_info.get("healthy") else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "success": health_info.get("healthy", False),
            "data": health_info,
            "message": f"Tool '{tool_name}' health check completed",
        },
    )
