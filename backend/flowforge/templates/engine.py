"""Jinja2-backed template engine."""

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment


class TemplateEngine:
    """Renders Jinja2 template strings with variable substitution."""

    def __init__(self):
        self.env = SandboxedEnvironment(loader=BaseLoader())

    def render(self, template_str: str, variables: dict) -> str:
        """Render *template_str* with the given *variables*.

        Args:
            template_str: A Jinja2 template string, e.g.
                          ``"Hello, {{ name }}!"``
            variables:    Dict of variable names to their values.

        Returns:
            The rendered string.
        """
        template = self.env.from_string(template_str)
        return template.render(**variables)
