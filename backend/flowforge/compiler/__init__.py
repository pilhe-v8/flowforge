from dataclasses import dataclass, field
from typing import Optional
import json
import jsonschema
from pathlib import Path

from .parser import WorkflowParser, WorkflowDef
from .validator import WorkflowValidator, ValidationError
from .graph_builder import GraphBuilder
from .node_factory import NodeFactory

_SCHEMA_PATH = Path(__file__).parent / "schema.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text())


@dataclass
class CompilationResult:
    graph: object  # CompiledStateGraph or None
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class Compiler:
    def __init__(
        self,
        tool_catalogue: dict,
        agent_profiles: dict,
        tool_executor=None,
        llm_client=None,
        template_engine=None,
        profile_loader=None,
    ):
        self.parser = WorkflowParser()
        self.validator = WorkflowValidator(tool_catalogue, agent_profiles)
        self.node_factory = NodeFactory(tool_executor, llm_client, template_engine, profile_loader)
        self.graph_builder = GraphBuilder(self.node_factory)

    def compile(self, yaml_string: str) -> CompilationResult:
        # 1. Parse YAML
        try:
            wf = self.parser.parse(yaml_string)
        except Exception as e:
            return CompilationResult(
                graph=None, errors=[ValidationError(step_id=None, field="yaml", message=str(e))]
            )

        # 2. JSON Schema validation
        try:
            jsonschema.validate(
                {
                    "workflow": {
                        "name": wf.name,
                        "slug": wf.slug,
                        "version": wf.version,
                        "trigger": {"type": wf.trigger.type, "output": wf.trigger.output},
                        "steps": [
                            {"id": s.id, "name": s.name, "type": s.step_type} for s in wf.steps
                        ],
                    }
                },
                _SCHEMA,
            )
        except jsonschema.ValidationError as e:
            return CompilationResult(
                graph=None,
                errors=[ValidationError(step_id=None, field="schema", message=e.message)],
            )

        # 3. Reference + variable validation
        errors = self.validator.validate(wf)
        if errors:
            return CompilationResult(graph=None, errors=errors)

        # 4. Build + compile graph
        try:
            graph = self.graph_builder.build(wf)
        except Exception as e:
            return CompilationResult(
                graph=None, errors=[ValidationError(step_id=None, field="graph", message=str(e))]
            )

        return CompilationResult(graph=graph, errors=[])
