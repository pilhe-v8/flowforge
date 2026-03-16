"""Agent profile loader — parses markdown profiles and loads them from the database."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select


# ---------------------------------------------------------------------------
# Dataclass (NOT the SQLAlchemy model)
# ---------------------------------------------------------------------------


@dataclass
class AgentProfile:
    """In-memory representation of an agent profile (parsed from markdown)."""

    name: str
    role_prompt: str
    context_description: str = ""
    guidelines: list[str] = field(default_factory=list)
    output_description: str = ""
    examples: list[dict] = field(default_factory=list)
    default_model: str | None = None


# ---------------------------------------------------------------------------
# Markdown helper functions
# ---------------------------------------------------------------------------


def extract_h1(content: str) -> str:
    """Return the text of the first `# Title` line, or empty string."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return ""


def split_by_h2(content: str) -> dict[str, str]:
    """Split *content* by `## Section` headers.

    Returns a dict mapping section name → section body (stripped).
    Text before the first `##` is ignored.
    """
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = stripped[3:].strip()
            current_lines = []
        else:
            if current_name is not None:
                current_lines.append(line)

    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()

    return sections


def parse_bullets(text: str) -> list[str]:
    """Return bullet items from *text* (lines starting with `- ` or `* `)."""
    bullets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            bullets.append(stripped[2:].strip())
    return bullets


def parse_examples(text: str) -> list[dict]:
    """Extract Input/Output pairs from *text*.

    Expected format (within a section body)::

        Input: some input text
        Output: some output text

    Returns a list of dicts with keys ``"input"`` and ``"output"``.
    """
    examples: list[dict] = []
    current: dict[str, str] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Input:"):
            if "output" in current:
                examples.append(current)
                current = {}
            current["input"] = stripped[len("Input:") :].strip()
        elif stripped.startswith("Output:"):
            current["output"] = stripped[len("Output:") :].strip()
            if "input" in current:
                examples.append(current)
                current = {}

    # Handle trailing pair without a following Input:
    if "input" in current and "output" in current:
        examples.append(current)

    return examples


# ---------------------------------------------------------------------------
# ProfileLoader
# ---------------------------------------------------------------------------


class ProfileLoader:
    """Loads and parses agent profiles from markdown or the database."""

    @staticmethod
    def parse_markdown(content: str) -> AgentProfile:
        """Parse a markdown string into an :class:`AgentProfile`."""
        sections = split_by_h2(content)
        return AgentProfile(
            name=extract_h1(content),
            role_prompt=sections.get("Role", ""),
            context_description=sections.get("Context", ""),
            guidelines=parse_bullets(sections.get("Guidelines", "")),
            output_description=sections.get("Output", ""),
            examples=parse_examples(sections.get("Examples", "")),
        )

    @staticmethod
    def build_system_prompt(profile: AgentProfile) -> str:
        """Build a plain-text system prompt from an :class:`AgentProfile`."""
        parts = [profile.role_prompt]

        if profile.guidelines:
            parts.append("Guidelines:")
            parts.extend(f"- {g}" for g in profile.guidelines)

        if profile.output_description:
            parts.append(f"Expected output: {profile.output_description}")

        if profile.examples:
            parts.append("Examples:")
            for ex in profile.examples:
                parts.append(f"Input: {ex['input']}")
                parts.append(f"Output: {ex['output']}")

        return "\n\n".join(parts)

    @staticmethod
    async def load_from_db(slug: str, tenant_id: str) -> AgentProfile:
        """Load an agent profile from the database by slug and tenant."""
        from flowforge.db.session import AsyncSessionLocal
        from flowforge.models import AgentProfile as AgentProfileModel

        async with AsyncSessionLocal() as db:
            row = await db.execute(
                select(AgentProfileModel).where(
                    AgentProfileModel.slug == slug,
                    AgentProfileModel.tenant_id == tenant_id,  # type: ignore[arg-type]
                )
            )
            model = row.scalar_one_or_none()
            if model is None:
                raise ValueError(f"Agent profile not found: {slug}")
            return ProfileLoader.parse_markdown(model.content)

    async def load(self, slug: str, tenant_id: str = "") -> AgentProfile:
        """Load by slug; delegates to :meth:`load_from_db`."""
        return await self.load_from_db(slug, tenant_id)
