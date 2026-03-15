import re
from typing import Any, Callable
from .parser import StepDef, TriggerDef

VAR_REF_PATTERN = re.compile(r"\{\{(\w+)\.(\w+)\}\}")


class NodeFactory:
    """
    Builds async LangGraph node callables for each step type.
    Dependencies (tool_executor, llm_client, etc.) are injected at runtime.
    For the compiler task, we build placeholder callables that will be
    wired with real clients in Task 5.
    """

    def __init__(
        self,
        tool_executor=None,
        llm_client=None,
        template_engine=None,
        profile_loader=None,
    ):
        self.tool_executor = tool_executor
        self.llm = llm_client
        self.templates = template_engine
        self.profiles = profile_loader

    def build_trigger(self, trigger: TriggerDef) -> Callable:
        async def trigger_node(state: dict) -> dict:
            return state

        return trigger_node

    def build_node(self, step: StepDef) -> Callable:
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
            case _:
                return self._build_passthrough(step)

    def _build_tool_node(self, step: StepDef) -> Callable:
        async def tool_node(state: dict) -> dict:
            inputs = self._resolve_inputs(step.input_mapping, state)
            result = {}
            if self.tool_executor:
                result = await self.tool_executor.execute(step.tool_uri, inputs)
            state[step.id] = {var: result.get(var) for var in step.output_vars}
            state.setdefault("_audit_trail", []).append(
                {"step_id": step.id, "type": "tool", "input": inputs, "output": state[step.id]}
            )
            return state

        return tool_node

    def _build_agent_node(self, step: StepDef) -> Callable:
        async def agent_node(state: dict) -> dict:
            context = self._resolve_inputs(step.context_mapping, state)
            response_content = ""
            if self.profiles and self.llm:
                profile = await self.profiles.load(step.agent_slug)
                from flowforge.agents.prompt_builder import PromptBuilder

                messages = PromptBuilder.build_messages(profile, context)
                model = step.model or getattr(profile, "default_model", None) or "gpt-4o-mini"
                response = await self.llm.chat(messages, model=model)
                response_content = response.content
            state[step.id] = {var: response_content for var in step.output_vars}
            state.setdefault("_audit_trail", []).append(
                {"step_id": step.id, "type": "agent", "input": context, "output": state[step.id]}
            )
            return state

        return agent_node

    def _build_deterministic_node(self, step: StepDef) -> Callable:
        async def deterministic_node(state: dict) -> dict:
            if step.operation == "render_template" and self.templates:
                tpl_vars = self._resolve_inputs(step.template_vars, state)
                rendered = self.templates.render(step.template, tpl_vars)
                state[step.id] = {var: rendered for var in step.output_vars}
            elif step.operation == "timestamp":
                from datetime import datetime, timezone

                state[step.id] = {"now": datetime.now(timezone.utc).isoformat()}
            elif step.operation == "format_text":
                inputs = self._resolve_inputs(step.input_mapping, state)
                template_str = step.template or ""
                state[step.id] = {"text": template_str.format(**inputs)}
            else:
                inputs = self._resolve_inputs(step.input_mapping, state)
                state[step.id] = inputs
            state.setdefault("_audit_trail", []).append(
                {"step_id": step.id, "type": "deterministic"}
            )
            return state

        return deterministic_node

    def _build_output_node(self, step: StepDef) -> Callable:
        async def output_node(state: dict) -> dict:
            inputs = self._resolve_inputs(step.input_mapping, state)
            if self.tool_executor:
                await self.tool_executor.execute(step.action_uri, inputs)
            state.setdefault("_audit_trail", []).append(
                {"step_id": step.id, "type": "output", "input": inputs}
            )
            return state

        return output_node

    def _build_passthrough(self, step: StepDef) -> Callable:
        async def passthrough(state: dict) -> dict:
            return state

        return passthrough

    def _resolve_inputs(self, mapping: dict[str, str], state: dict) -> dict:
        return {k: self._resolve_single(v, state) for k, v in mapping.items()}

    def _resolve_single(self, ref: str, state: dict) -> Any:
        def replacer(match):
            step_id, var = match.groups()
            val = state.get(step_id, {})
            if isinstance(val, dict):
                return str(val.get(var, ""))
            return ""

        return VAR_REF_PATTERN.sub(replacer, str(ref))
