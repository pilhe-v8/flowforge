import re
from dataclasses import dataclass
from typing import Optional
from .parser import WorkflowDef, StepDef

VAR_REF_PATTERN = re.compile(r"\{\{(\w+)\.(\w+)\}\}")


@dataclass
class ValidationError:
    step_id: Optional[str]
    field: str
    message: str


class WorkflowValidator:
    def __init__(self, tool_catalogue: dict, agent_profiles: dict):
        # tool_catalogue: {uri_string -> any} or {slug -> {uri: ...}}
        # agent_profiles: {slug -> any}
        self.tools = tool_catalogue
        self.agents = agent_profiles

    def validate(self, wf: WorkflowDef) -> list[ValidationError]:
        errors = []
        step_ids = {s.id for s in wf.steps}

        for step in wf.steps:
            # Check tool references
            if step.tool_uri and not self._tool_exists(step.tool_uri):
                errors.append(ValidationError(step.id, "tool", f"Tool not found: {step.tool_uri}"))

            # Check agent references
            if step.agent_slug and step.agent_slug not in self.agents:
                errors.append(
                    ValidationError(step.id, "agent", f"Agent profile not found: {step.agent_slug}")
                )

            # Check fallback agent references
            if step.fallback and step.fallback.agent not in self.agents:
                errors.append(
                    ValidationError(
                        step.id,
                        "fallback.agent",
                        f"Fallback agent not found: {step.fallback.agent}",
                    )
                )

            # Check next_step
            if step.next_step and step.next_step not in step_ids:
                errors.append(
                    ValidationError(step.id, "next", f"Target step not found: {step.next_step}")
                )

            # Check route targets
            for val, target in step.routes.items():
                if target not in step_ids:
                    errors.append(
                        ValidationError(
                            step.id, f"routes.{val}", f"Route target not found: {target}"
                        )
                    )

            # Check default_target
            if step.default_target and step.default_target not in step_ids:
                errors.append(
                    ValidationError(
                        step.id, "default", f"Default target not found: {step.default_target}"
                    )
                )

            # Check gate rule targets
            for rule in step.rules:
                if rule.target not in step_ids:
                    errors.append(
                        ValidationError(
                            step.id, f"rules.{rule.label}", f"Rule target not found: {rule.target}"
                        )
                    )

            # Check variable references are produced upstream
            upstream = self._get_upstream_vars(step, wf)
            all_mappings = {
                **step.input_mapping,
                **step.context_mapping,
                **step.template_vars,
            }
            for param, ref in all_mappings.items():
                for src_step, src_var in VAR_REF_PATTERN.findall(str(ref)):
                    full_ref = f"{{{{{src_step}.{src_var}}}}}"
                    if full_ref not in upstream:
                        errors.append(
                            ValidationError(
                                step.id,
                                param,
                                f"Variable {full_ref} not available (not produced upstream)",
                            )
                        )

        return errors

    def _get_upstream_vars(self, step: StepDef, wf: WorkflowDef) -> set[str]:
        upstream: set[str] = set()
        for var in wf.trigger.output:
            upstream.add(f"{{{{trigger.{var}}}}}")

        # Build reverse adjacency
        reverse_adj: dict[str, list[str]] = {}
        for s in wf.steps:
            for target in self._get_targets(s):
                reverse_adj.setdefault(target, []).append(s.id)

        # BFS backwards from current step
        visited: set[str] = set()
        queue = list(reverse_adj.get(step.id, []))
        while queue:
            sid = queue.pop(0)
            if sid in visited:
                continue
            visited.add(sid)
            src = next((s for s in wf.steps if s.id == sid), None)
            if src:
                for var in src.output_vars:
                    upstream.add(f"{{{{{src.id}.{var}}}}}")
                queue.extend(reverse_adj.get(sid, []))

        return upstream

    def _get_targets(self, step: StepDef) -> list[str]:
        targets = []
        if step.next_step:
            targets.append(step.next_step)
        targets.extend(step.routes.values())
        if step.default_target:
            targets.append(step.default_target)
        for rule in step.rules:
            targets.append(rule.target)
        return targets

    def _tool_exists(self, uri: str) -> bool:
        # Accept both {uri: any} and {slug: {uri: uri_str}} formats
        if uri in self.tools:
            return True
        for v in self.tools.values():
            if isinstance(v, dict) and v.get("uri") == uri:
                return True
        return False
