"""
Skill discovery and metadata API endpoints.

Mounted under ``/api/v1/skills``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.skills.loader import SkillLoader, SkillNotFoundError, get_skill_loader

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get(
    "",
    response_model=dict,
    summary="List available declarative skills",
)
def list_skills(
    loader: SkillLoader = Depends(get_skill_loader),
) -> JSONResponse:
    """Return all discovered and validated skill definitions."""
    skills = loader.list_skills()
    skill_dicts = [s.model_dump(mode="json") for s in skills]
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": skill_dicts,
            "message": f"Retrieved {len(skill_dicts)} available skill(s)",
        },
    )


@router.get(
    "/{skill_name}",
    response_model=dict,
    summary="Retrieve detailed skill definition and metadata",
)
def get_skill(
    skill_name: str,
    loader: SkillLoader = Depends(get_skill_loader),
) -> JSONResponse:
    """Return the full declarative definition and input schema of a skill."""
    try:
        skill = loader.get_skill(skill_name)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": skill.model_dump(mode="json"),
                "message": f"Skill '{skill_name}' retrieved successfully",
            },
        )
    except SkillNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' was not found",
        )
