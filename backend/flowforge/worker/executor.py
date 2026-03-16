from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExecutionResult:
    """Result of a single graph execution."""

    session_id: str
    final_state: dict
    steps_executed: list = field(default_factory=list)


class Executor:
    """Stateless executor that runs a compiled LangGraph workflow graph."""

    @staticmethod
    async def run(graph, session, input_data: dict) -> ExecutionResult:
        state = {**session.state, "trigger": input_data}
        config = {"configurable": {"session_id": session.id}}

        result_state = await graph.ainvoke(state, config=config)

        session.state = result_state
        session.step_count += 1
        session.updated_at = datetime.utcnow()

        return ExecutionResult(
            session_id=session.id,
            final_state=result_state,
            steps_executed=result_state.get("_audit_trail", []),
        )
