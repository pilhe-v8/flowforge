"""Prompt builder — assembles LLM message lists from agent profiles and context."""

from __future__ import annotations

import json

from flowforge.agents.profile_loader import AgentProfile, ProfileLoader


class PromptBuilder:
    """Builds OpenAI-style message lists from an :class:`AgentProfile` and context."""

    @staticmethod
    def build_messages(profile: AgentProfile, context: dict) -> list[dict]:
        """Return a ``[system, user]`` message list.

        The *system* message is built by :meth:`ProfileLoader.build_system_prompt`.
        The *user* message contains each context key/value formatted as::

            **key:** value

        Dict and list values are pretty-printed as JSON.  Scalar values are
        rendered inline.
        """
        system = ProfileLoader.build_system_prompt(profile)

        user_parts: list[str] = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                user_parts.append(f"**{key}:** {json.dumps(value, indent=2)}")
            else:
                user_parts.append(f"**{key}:** {value}")

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]
