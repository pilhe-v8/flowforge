import { useWorkflowStore } from '../stores/workflowStore';
import { getAvailableVariables } from '../utils/variableResolver';
import { VariableInfo } from '../types';

export function useAvailableVariables(nodeId: string): VariableInfo[] {
  const nodes = useWorkflowStore(s => s.nodes);
  const edges = useWorkflowStore(s => s.edges);
  return getAvailableVariables(nodes, edges, nodeId);
}
