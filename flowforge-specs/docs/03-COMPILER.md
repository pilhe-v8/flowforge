# 03 - YAML to LangGraph Compiler Specification

## Overview

The compiler transforms a validated YAML workflow definition into an executable
LangGraph CompiledStateGraph. It runs inside the control plane (at deploy time)
and inside workers (when cache is cold).

## Pipeline

```
YAML string
    |
    v
[1. Parse] -----> Raw Python dicts (via PyYAML)
    |
    v
[2. Schema Validate] -----> JSON Schema check (via jsonschema)
    |
    v
[3. Build AST] -----> Typed dataclasses (WorkflowDef, StepDef, TriggerDef, etc.)
    |
    v
[4. Validate References] -----> Check all tool/agent/step refs exist
    |
    v
[5. Validate Variables] -----> Check all {{x.y}} are produced upstream
    |
    v
[6. Build Graph] -----> LangGraph StateGraph with nodes and edges
    |
    v
[7. Compile] -----> CompiledStateGraph (ready to execute)
```

## Module: parser.py

```python
import yaml
from dataclasses import dataclass, field

@dataclass
class TriggerDef:
    type: str                  # email_received, webhook, schedule, manual
    config: dict
    output: list[str]

@dataclass
class FallbackDef:
    when: str                  # Expression string
    agent: str                 # Agent profile slug
    input: dict[str, str]
    output: list[str]

@dataclass
class GateRule:
    condition: str             # Expression string
    target: str                # Step ID
    label: str                 # Human-readable label

@dataclass
class StepDef:
    id: str
    name: str
    step_type: str             # tool, agent, router, gate, deterministic, output

    # Tool fields
    tool_uri: str | None = None
    input_mapping: dict[str, str] = field(default_factory=dict)
    output_vars: list[str] = field(default_factory=list)
    fallback: FallbackDef | None = None

    # Agent fields
    agent_slug: str | None = None
    model: str | None = None
    context_mapping: dict[str, str] = field(default_factory=dict)

    # Router fields
    route_on: str | None = None
    routes: dict[str, str] = field(default_factory=dict)

    # Gate fields
    rules: list[GateRule] = field(default_factory=list)

    # Deterministic fields
    operation: str | None = None
    template: str | None = None
    template_vars: dict[str, str] = field(default_factory=dict)

    # Output fields
    action_uri: str | None = None

    # Navigation
    next_step: str | None = None
    default_target: str | None = None

@dataclass
class WorkflowDef:
    name: str
    slug: str
    version: int
    description: str
    tenant_id: str
    trigger: TriggerDef
    steps: list[StepDef]


class WorkflowParser:
    def parse(self, yaml_string: str) -> WorkflowDef:
        raw = yaml.safe_load(yaml_string)
        wf = raw["workflow"]

        trigger = TriggerDef(
            type=wf["trigger"]["type"],
            config=wf["trigger"].get("config", {}),
            output=wf["trigger"]["output"],
        )

        steps = [self._parse_step(s) for s in wf["steps"]]

        return WorkflowDef(
            name=wf["name"],
            slug=wf.get("slug", slugify(wf["name"])),
            version=wf.get("version", 1),
            description=wf.get("description", ""),
            tenant_id=wf.get("tenant_id", ""),
            trigger=trigger,
            steps=steps,
        )

    def _parse_step(self, raw: dict) -> StepDef:
        step = StepDef(
            id=raw["id"],
            name=raw["name"],
            step_type=raw["type"],
        )

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
            step.agent_slug = raw["agent"]
            step.model = raw.get("model")
            step.context_mapping = raw.get("context", {})
            step.output_vars = raw.get("output", [])
            step.next_step = raw.get("next")

        elif raw["type"] == "router":
            step.route_on = raw["on"]
            step.routes = raw["routes"]
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
```

## Module: validator.py

```python
import re
from dataclasses import dataclass

@dataclass
class ValidationError:
    step_id: str | None
    field: str
    message: str

VAR_REF_PATTERN = re.compile(r"\{\{(\w+)\.(\w+)\}\}")

class WorkflowValidator:
    def __init__(self, tool_catalogue: dict, agent_profiles: dict):
        self.tools = tool_catalogue       # slug -> ToolSchema
        self.agents = agent_profiles      # slug -> AgentProfile

    def validate(self, wf: WorkflowDef) -> list[ValidationError]:
        errors = []
        step_ids = {s.id for s in wf.steps}

        for step in wf.steps:
            # Check tool references
            if step.tool_uri and not self._tool_exists(step.tool_uri):
                errors.append(ValidationError(
                    step.id, "tool",
                    f"Tool not found: {step.tool_uri}"
                ))

            # Check agent references
            if step.agent_slug and step.agent_slug not in self.agents:
                errors.append(ValidationError(
                    step.id, "agent",
                    f"Agent profile not found: {step.agent_slug}"
                ))

            # Check next/route/gate targets exist
            if step.next_step and step.next_step not in step_ids:
                errors.append(ValidationError(
                    step.id, "next",
                    f"Target step not found: {step.next_step}"
                ))

            for val, target in step.routes.items():
                if target not in step_ids:
                    errors.append(ValidationError(
                        step.id, f"routes.{val}",
                        f"Route target not found: {target}"
                    ))

            if step.default_target and step.default_target not in step_ids:
                errors.append(ValidationError(
                    step.id, "default",
                    f"Default target not found: {step.default_target}"
                ))

            for rule in step.rules:
                if rule.target not in step_ids:
                    errors.append(ValidationError(
                        step.id, f"rules.{rule.label}",
                        f"Rule target not found: {rule.target}"
                    ))

            # Check variable references are produced upstream
            upstream_vars = self._get_upstream_vars(step, wf)
            all_mappings = {**step.input_mapping, **step.context_mapping, **step.template_vars}
            for param, ref in all_mappings.items():
                matches = VAR_REF_PATTERN.findall(ref)
                for src_step, src_var in matches:
                    full_ref = f"{{{{{src_step}.{src_var}}}}}"
                    if full_ref not in upstream_vars:
                        errors.append(ValidationError(
                            step.id, param,
                            f"Variable {full_ref} not available (not produced upstream)"
                        ))

        return errors

    def _get_upstream_vars(self, step: StepDef, wf: WorkflowDef) -> set[str]:
        # BFS backwards through the graph to find all upstream steps
        # Collect their output variables + trigger outputs
        upstream = set()
        for var in wf.trigger.output:
            upstream.add(f"{{{{trigger.{var}}}}}")

        # Build adjacency (reverse)
        reverse_adj: dict[str, list[str]] = {}
        for s in wf.steps:
            if s.next_step:
                reverse_adj.setdefault(s.next_step, []).append(s.id)
            for target in s.routes.values():
                reverse_adj.setdefault(target, []).append(s.id)
            if s.default_target:
                reverse_adj.setdefault(s.default_target, []).append(s.id)
            for rule in s.rules:
                reverse_adj.setdefault(rule.target, []).append(s.id)

        # BFS from current step backwards
        visited = set()
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

    def _tool_exists(self, uri: str) -> bool:
        # Check if tool URI matches any registered tool
        for slug, tool in self.tools.items():
            if tool.uri == uri:
                return True
        return False
```

## Module: graph_builder.py

```python
from langgraph.graph import StateGraph, END

class GraphBuilder:
    def __init__(self, node_factory: "NodeFactory"):
        self.factory = node_factory

    def build(self, wf: WorkflowDef) -> StateGraph:
        graph = StateGraph(dict)

        # Add trigger as first node
        graph.add_node("trigger", self.factory.build_trigger(wf.trigger))
        graph.set_entry_point("trigger")

        # Add step nodes
        for step in wf.steps:
            node_fn = self.factory.build_node(step)
            graph.add_node(step.id, node_fn)

        # Wire trigger to first step
        if wf.steps:
            graph.add_edge("trigger", wf.steps[0].id)

        # Wire step edges
        for step in wf.steps:
            if step.step_type == "router":
                route_map = dict(step.routes)
                if step.default_target:
                    route_map["__default__"] = step.default_target

                def make_router_fn(s=step):
                    def router_fn(state):
                        val = self._resolve_ref(s.route_on, state)
                        return str(val) if val is not None else "__default__"
                    return router_fn

                graph.add_conditional_edges(step.id, make_router_fn(), route_map)

            elif step.step_type == "gate":
                targets = {}
                for i, rule in enumerate(step.rules):
                    targets[f"rule_{i}"] = rule.target
                if step.default_target:
                    targets["__default__"] = step.default_target

                def make_gate_fn(s=step):
                    def gate_fn(state):
                        for i, rule in enumerate(s.rules):
                            if self._evaluate_expression(rule.condition, state):
                                return f"rule_{i}"
                        return "__default__"
                    return gate_fn

                graph.add_conditional_edges(step.id, make_gate_fn(), targets)

            elif step.next_step:
                graph.add_edge(step.id, step.next_step)

            elif step.step_type == "output":
                graph.add_edge(step.id, END)

        return graph.compile()

    def _resolve_ref(self, ref: str, state: dict):
        # Parse {{step_id.var}} and look up in state
        match = re.match(r"\{\{(\w+)\.(\w+)\}\}", ref)
        if match:
            step_id, var = match.groups()
            return state.get(step_id, {}).get(var)
        return ref

    def _evaluate_expression(self, expr: str, state: dict) -> bool:
        # Safe expression evaluator (restricted operators only)
        # Uses a sandboxed evaluator, NOT eval()
        evaluator = SafeExprEvaluator(state)
        return evaluator.evaluate(expr)
```

## Module: node_factory.py

```python
class NodeFactory:
    def __init__(self, tool_executor, llm_client, template_engine, profile_loader):
        self.tool_executor = tool_executor
        self.llm = llm_client
        self.templates = template_engine
        self.profiles = profile_loader

    def build_trigger(self, trigger: TriggerDef):
        async def trigger_node(state: dict) -> dict:
            # Trigger data is already in state from the worker
            return state
        return trigger_node

    def build_node(self, step: StepDef):
        match step.step_type:
            case "tool":
                return self._build_tool_node(step)
            case "agent":
                return self._build_agent_node(step)
            case "router":
                return self._build_passthrough(step)
            case "gate":
                return self._build_passthrough(step)
            case "deterministic":
                return self._build_deterministic_node(step)
            case "output":
                return self._build_output_node(step)

    def _build_tool_node(self, step: StepDef):
        async def tool_node(state: dict) -> dict:
            # Resolve inputs from state
            inputs = self._resolve_inputs(step.input_mapping, state)

            # Call tool
            result = await self.tool_executor.execute(step.tool_uri, inputs)

            # Check fallback
            if step.fallback:
                threshold_met = self._evaluate_fallback(step.fallback.when, result)
                if threshold_met:
                    profile = await self.profiles.load(step.fallback.agent)
                    fb_inputs = self._resolve_inputs(step.fallback.input, state)
                    messages = PromptBuilder.build_messages(profile, fb_inputs)
                    llm_result = await self.llm.chat(messages)
                    for var in step.fallback.output:
                        result[var] = llm_result.content

            # Write outputs to state
            state[step.id] = {}
            for var in step.output_vars:
                state[step.id][var] = result.get(var)

            # Audit trail
            state.setdefault("_audit_trail", []).append({
                "step_id": step.id,
                "type": "tool",
                "input": inputs,
                "output": state[step.id],
            })

            return state
        return tool_node

    def _build_agent_node(self, step: StepDef):
        async def agent_node(state: dict) -> dict:
            profile = await self.profiles.load(step.agent_slug)
            context = self._resolve_inputs(step.context_mapping, state)
            messages = PromptBuilder.build_messages(profile, context)

            model = step.model or profile.default_model or "gpt-4o-mini"
            response = await self.llm.chat(messages, model=model)

            state[step.id] = {}
            for var in step.output_vars:
                state[step.id][var] = response.content

            state.setdefault("_audit_trail", []).append({
                "step_id": step.id,
                "type": "agent",
                "model": model,
                "input": context,
                "output": state[step.id],
            })

            return state
        return agent_node

    def _build_deterministic_node(self, step: StepDef):
        async def deterministic_node(state: dict) -> dict:
            if step.operation == "render_template":
                tpl_vars = self._resolve_inputs(step.template_vars, state)
                rendered = self.templates.render(step.template, tpl_vars)
                state[step.id] = {"draft_response": rendered}
                for var in step.output_vars:
                    state[step.id][var] = rendered

            elif step.operation == "parse_email":
                raw = self._resolve_single(step.input_mapping.get("raw_email", ""), state)
                parsed = parse_email_content(raw)
                state[step.id] = parsed

            elif step.operation == "format_text":
                inputs = self._resolve_inputs(step.input_mapping, state)
                state[step.id] = {"text": step.template.format(**inputs)}

            elif step.operation == "timestamp":
                state[step.id] = {"now": datetime.utcnow().isoformat()}

            state.setdefault("_audit_trail", []).append({
                "step_id": step.id, "type": "deterministic"
            })
            return state
        return deterministic_node

    def _build_output_node(self, step: StepDef):
        async def output_node(state: dict) -> dict:
            inputs = self._resolve_inputs(step.input_mapping, state)
            await self.tool_executor.execute(step.action_uri, inputs)

            state.setdefault("_audit_trail", []).append({
                "step_id": step.id, "type": "output", "input": inputs
            })
            return state
        return output_node

    def _build_passthrough(self, step: StepDef):
        async def passthrough(state: dict) -> dict:
            return state
        return passthrough

    def _resolve_inputs(self, mapping: dict[str, str], state: dict) -> dict:
        result = {}
        for param, ref in mapping.items():
            result[param] = self._resolve_single(ref, state)
        return result

    def _resolve_single(self, ref: str, state: dict):
        # Replace all {{step_id.var}} in the string
        def replacer(match):
            step_id, var = match.groups()
            return str(state.get(step_id, {}).get(var, ""))
        return VAR_REF_PATTERN.sub(replacer, ref)
```

## Safe Expression Evaluator

Gate rules and fallback conditions use a restricted expression evaluator,
NOT Python eval(). Implementation uses AST parsing with a whitelist of
allowed operations:

```python
import ast
import operator

SAFE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.Gt: operator.gt,
    ast.LtE: operator.le,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Not: operator.not_,
    ast.In: lambda a, b: a in b,
}

SAFE_FUNCTIONS = {
    "len": len,
    "contains": lambda haystack, needle: needle in str(haystack),
    "starts_with": lambda s, prefix: str(s).startswith(prefix),
    "is_empty": lambda x: x is None or x == "" or x == [],
}

class SafeExprEvaluator:
    def __init__(self, variables: dict):
        # Flatten state: {step_id: {var: val}} -> {var: val}
        self.vars = {}
        for step_id, step_data in variables.items():
            if isinstance(step_data, dict):
                self.vars.update(step_data)

    def evaluate(self, expr: str) -> bool:
        tree = ast.parse(expr, mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node):
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = self._eval_node(comp)
                if type(op) not in SAFE_OPS:
                    raise ValueError(f"Unsupported operator: {type(op)}")
                if not SAFE_OPS[type(op)](left, right):
                    return False
                left = right
            return True
        elif isinstance(node, ast.BoolOp):
            values = [self._eval_node(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            return any(values)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval_node(node.operand)
        elif isinstance(node, ast.Name):
            return self.vars.get(node.id)
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name not in SAFE_FUNCTIONS:
                raise ValueError(f"Unknown function: {func_name}")
            args = [self._eval_node(a) for a in node.args]
            return SAFE_FUNCTIONS[func_name](*args)
        elif isinstance(node, ast.List):
            return [self._eval_node(e) for e in node.elts]
        else:
            raise ValueError(f"Unsupported expression node: {type(node)}")
```

## Compiler Entry Point

```python
class Compiler:
    def __init__(self, tool_catalogue, agent_profiles, tool_executor, llm_client,
                 template_engine, profile_loader):
        self.parser = WorkflowParser()
        self.validator = WorkflowValidator(tool_catalogue, agent_profiles)
        self.node_factory = NodeFactory(tool_executor, llm_client, template_engine, profile_loader)
        self.graph_builder = GraphBuilder(self.node_factory)

    def compile(self, yaml_string: str) -> CompilationResult:
        # 1. Parse
        wf = self.parser.parse(yaml_string)

        # 2. Validate
        errors = self.validator.validate(wf)
        if errors:
            return CompilationResult(graph=None, errors=errors)

        # 3. Build graph
        graph = self.graph_builder.build(wf)

        return CompilationResult(graph=graph, errors=[])

@dataclass
class CompilationResult:
    graph: CompiledStateGraph | None
    errors: list[ValidationError]
```
