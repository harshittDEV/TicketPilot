"""
Skill definition loading and validation engine.

Parses declarative YAML workflow definitions from the configured skills
directory, enforces strict validation, detects duplicate skill names,
and provides deterministic in-memory lookup.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
import yaml

from app.core.config import get_settings
from app.skills.models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillLoaderError(Exception):
    """Base error for skill loading operations."""


class SkillNotFoundError(SkillLoaderError):
    """Raised when a requested skill name is not found."""


class DuplicateSkillError(SkillLoaderError):
    """Raised when two files define a skill with the same name."""


class SkillValidationError(SkillLoaderError):
    """Raised when a skill definition fails schema validation or YAML parsing."""


class SkillLoader:
    """
    Loads and validates declarative skill definitions from YAML files.

    Ensures zero arbitrary code execution and deterministic registration.
    """

    def __init__(self, definitions_dir: Optional[str | Path] = None) -> None:
        settings = get_settings()
        self._dir = Path(definitions_dir or settings.skills_dir).resolve()
        self._skills: dict[str, SkillDefinition] = {}
        self._loaded = False

    @property
    def definitions_dir(self) -> Path:
        return self._dir

    def load_all(self, *, force_reload: bool = False) -> dict[str, SkillDefinition]:
        """
        Load all YAML skill definitions from the configured directory.

        Raises:
            DuplicateSkillError: If multiple files declare the same skill name.
            SkillValidationError: If any file contains malformed YAML or invalid fields.
        """
        if self._loaded and not force_reload:
            return self._skills

        self._skills.clear()

        if not self._dir.exists():
            self._dir.mkdir(parents=True, exist_ok=True)
            self._loaded = True
            return self._skills

        # Find all YAML files
        yaml_files = sorted(list(self._dir.glob("*.yaml")) + list(self._dir.glob("*.yml")))
        logger.info("Loading skill definitions from %s (found %d files)", self._dir, len(yaml_files))

        for file_path in yaml_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                raw_data = yaml.safe_load(content)
                if not raw_data or not isinstance(raw_data, dict):
                    raise SkillValidationError(
                        f"Skill file '{file_path.name}' is empty or does not contain a YAML mapping"
                    )

                skill_def = SkillDefinition.model_validate(raw_data)
                skill_name = skill_def.name

                if skill_name in self._skills:
                    raise DuplicateSkillError(
                        f"Duplicate skill name '{skill_name}' defined in '{file_path.name}'. "
                        "Skill names must be globally unique."
                    )

                self._skills[skill_name] = skill_def
                logger.debug("Loaded skill: %s v%s", skill_name, skill_def.version)

            except DuplicateSkillError:
                raise
            except Exception as exc:
                raise SkillValidationError(
                    f"Failed to load skill from '{file_path.name}': {exc!s}"
                ) from exc

        self._loaded = True
        return self._skills

    def get_skill(self, name: str) -> SkillDefinition:
        """
        Retrieve a loaded skill definition by unique name.

        Raises:
            SkillNotFoundError: If no skill matches *name*.
        """
        if not self._loaded:
            self.load_all()

        if name not in self._skills:
            raise SkillNotFoundError(f"Skill '{name}' was not found in {self._dir}")
        return self._skills[name]

    def list_skills(self) -> list[SkillDefinition]:
        """Return a sorted list of all currently loaded skill definitions."""
        if not self._loaded:
            self.load_all()
        return [self._skills[k] for k in sorted(self._skills.keys())]

    def reload(self) -> None:
        """Force reloading all definitions from disk."""
        self.load_all(force_reload=True)


# Module-level singleton helper
_skill_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    """Return the application-wide skill loader."""
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
        _skill_loader.load_all()
    return _skill_loader
