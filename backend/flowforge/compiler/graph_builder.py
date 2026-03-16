from typing import Any
from langgraph.graph import StateGraph, END
from .parser import WorkflowDef, StepDef
from .safe_eval import SafeExprEvaluator
from .constants import VAR_REF_PATTERN


class GraphBuilder:
    def __init__(self, node_factory: "NodeFactory"):
        self.factory = node_factory

    def build(self, wf: WorkflowDef):
        """Build and compile a LangGraph CompiledStateGraph from a WorkflowDef."""
        graph = StateGraph(dict)

        # Trigger node
        graph.add_node("trigger", self.factory.build_trigger(wf.trigger))
        graph.set_entry_point("trigger")

        # Step nodes
        for step in wf.steps:
            graph.add_node(step.id, self.factory.build_node(step))

        # Trigger → first step
        if wf.steps:
            graph.add_edge("trigger", wf.steps[0].id)

        # Step edges
        for step in wf.steps:
            if step.step_type == "router":
                route_map = dict(step.routes)
                if step.default_target:
                    route_map["__default__"] = step.default_target

                def make_router_fn(s: StepDef = step):
                    def router_fn(state: dict) -> str:
                        val = self._resolve_ref(s.route_on or "", state)
                        return (
                            str(val) if val is not None and str(val) in route_map else "__default__"
                        )

                    return router_fn

                graph.add_conditional_edges(step.id, make_router_fn(), route_map)

            elif step.step_type == "gate":
                targets: dict[str, Any] = {}
                for i, rule in enumerate(step.rules):
                    targets[f"rule_{i}"] = rule.target
                # Always include __default__ so gate_fn can safely return it.
                # If no default_target is set, route to END to avoid KeyError.
                targets["__default__"] = step.default_target if step.default_target else END

                def make_gate_fn(s: StepDef = step):
                    def gate_fn(state: dict) -> str:
                        for i, rule in enumerate(s.rules):
                            try:
                                if self._evaluate_expression(rule.condition, state):
                                    return f"rule_{i}"
                            except ValueError:
                                pass
                        return "__default__"

                    return gate_fn

                graph.add_conditional_edges(step.id, make_gate_fn(), targets)

            elif step.next_step:
                graph.add_edge(step.id, step.next_step)

            elif step.step_type == "output":
                graph.add_edge(step.id, END)

        return graph.compile()

    def _resolve_ref(self, ref: str, state: dict) -> Any:
        match = VAR_REF_PATTERN.match(ref.strip())
        if match:
            step_id, var = match.groups()
            return state.get(step_id, {}).get(var)
        return ref

    def _evaluate_expression(self, expr: str, state: dict) -> bool:
        """Evaluate a boolean expression string against the current graph state."""
        evaluator = SafeExprEvaluator(state)
        return evaluator.evaluate(expr)
