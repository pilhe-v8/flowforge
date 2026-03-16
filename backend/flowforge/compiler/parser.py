from dataclasses import dataclass, field
from typing import Optional
import re
import yaml


@dataclass
class TriggerDef:
    type: str  # email_received | webhook | schedule | manual
    config: dict
    output: list[str]


@dataclass
class FallbackDef:
    when: str  # Expression string
    agent: str  # Agent profile slug
    input: dict[str, str]
    output: list[str]


@dataclass
class GateRule:
    condition: str  # Expression string
    target: str  # Step ID
    label: str


@dataclass
class StepDef:
    id: str
    name: str
    step_type: str  # tool | agent | router | gate | deterministic | output

    # Tool fields
    tool_uri: Optional[str] = None
    input_mapping: dict[str, str] = field(default_factory=dict)
    output_vars: list[str] = field(default_factory=list)
    fallback: Optional[FallbackDef] = None

    # Agent fields
    agent_slug: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    context_mapping: dict[str, str] = field(default_factory=dict)

    # Router fields
    route_on: Optional[str] = None
    routes: dict[str, str] = field(default_factory=dict)

    # Gate fields
    rules: list[GateRule] = field(default_factory=list)

    # Deterministic fields
    operation: Optional[str] = None
    template: Optional[str] = None
    template_vars: dict[str, str] = field(default_factory=dict)

    # Output fields
    action_uri: Optional[str] = None

    # Navigation
    next_step: Optional[str] = None
    default_target: Optional[str] = None


@dataclass
class WorkflowDef:
    name: str
    slug: str
    version: int
    description: str
    tenant_id: str
    trigger: TriggerDef
    steps: list[StepDef]


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class WorkflowParser:
    def parse(self, yaml_string_or_dict) -> WorkflowDef:
        if isinstance(yaml_string_or_dict, str):
            raw = yaml.safe_load(yaml_string_or_dict)
        else:
            raw = yaml_string_or_dict
        wf = raw["workflow"]

        trigger = TriggerDef(
            type=wf["trigger"]["type"],
            config=wf["trigger"].get("config", {}),
            output=wf["trigger"].get("output", []),
        )

        steps = [self._parse_step(s) for s in wf.get("steps", [])]

        return WorkflowDef(
            name=wf["name"],
            slug=wf.get("slug") or _slugify(wf["name"]),
            version=wf.get("version", 1),
            description=wf.get("description", ""),
            tenant_id=wf.get("tenant_id", ""),
            trigger=trigger,
            steps=steps,
        )

    def _parse_step(self, raw: dict) -> StepDef:
        step = StepDef(id=raw["id"], name=raw["name"], step_type=raw["type"])

        if raw["type"] == "tool":
            step.tool_uri = raw["tool"]
            step.input_mapping = raw.get("input", {})
            step.output_vars = raw.get("output", [])
            step.next_step = raw.get("next")
            if "fallback" in raw:
                fb = raw["fallback"]
                step.fallback = FallbackDef(
                    when=fb["when"],
                    agent=fb["agent"],
                    input=fb.get("input", {}),
                    output=fb.get("output", []),
                )

        elif raw["type"] == "agent":
            step.agent_slug = raw.get("agent")
            step.system_prompt = raw.get("system_prompt")
            step.model = raw.get("model")
            step.context_mapping = raw.get("context", {})
            step.output_vars = raw.get("output", [])
            step.next_step = raw.get("next")

        elif raw["type"] == "router":
            # YAML 1.1 parses bare `on:` as True — check both True and "on"
            step.route_on = raw.get("on") or raw.get(True)
            step.routes = raw.get("routes", {})
            step.default_target = raw.get("default")

        elif raw["type"] == "gate":
            step.rules = [
                GateRule(
                    condition=r["if"],
                    target=r["then"],
                    label=r.get("label", ""),
                )
                for r in raw["rules"]
            ]
            step.default_target = raw.get("default")

        elif raw["type"] == "deterministic":
            step.operation = raw["operation"]
            step.template = raw.get("template")
            step.template_vars = raw.get("template_vars", {})
            step.input_mapping = raw.get("input", {})
            step.output_vars = raw.get("output", [])
            step.next_step = raw.get("next")

        elif raw["type"] == "output":
            step.action_uri = raw["action"]
            step.input_mapping = raw.get("input", {})

        return step
