"""Jinja2-backed template engine."""

from jinja2 import Environment, BaseLoader


class TemplateEngine:
    """Renders Jinja2 template strings with variable substitution."""

    def __init__(self):
        self.env = Environment(loader=BaseLoader())

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
