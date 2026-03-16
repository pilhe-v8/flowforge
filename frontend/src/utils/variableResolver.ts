import { WorkflowNode, WorkflowEdge, VariableInfo, TriggerNodeData } from '../types';

export function getAvailableVariables(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
  currentNodeId: string,
): VariableInfo[] {
  // 1. Build adjacency map (reverse edges: child → parents)
  const parents = new Map<string, string[]>();
  nodes.forEach(n => parents.set(n.id, []));
  edges.forEach(e => {
    const list = parents.get(e.target) ?? [];
    list.push(e.source);
    parents.set(e.target, list);
  });

  // 2. BFS backwards from currentNodeId
  const visited = new Set<string>();
  const queue = [currentNodeId];
  while (queue.length > 0) {
    const nodeId = queue.shift()!;
    if (visited.has(nodeId)) continue;
    visited.add(nodeId);
    (parents.get(nodeId) ?? []).forEach(p => queue.push(p));
  }
  visited.delete(currentNodeId); // exclude self

  // 3. Collect variables from upstream nodes
  const variables: VariableInfo[] = [];
  nodes.forEach(node => {
    if (!visited.has(node.id)) return;
    const data = node.data;
    const outputVars: string[] = (data as { outputVars?: string[] }).outputVars ?? [];
    const stepId: string = (data as { stepId?: string }).stepId ?? node.id;
    const stepName: string = (data as { label?: string }).label ?? node.id;
    outputVars.forEach(varName => {
      variables.push({
        stepId,
        stepName,
        variableName: varName,
        fullRef: `{{${stepId}.${varName}}}`,
      });
    });
    // Trigger node: add trigger.* variables
    if (node.type === 'trigger') {
      const trigData = data as TriggerNodeData;
      trigData.outputVars.forEach(varName => {
        variables.push({
          stepId: 'trigger',
          stepName: 'Trigger',
          variableName: varName,
          fullRef: `{{trigger.${varName}}}`,
        });
      });
    }
  });

  return variables;
}

export function groupBy<T>(items: T[], key: keyof T): Record<string, T[]> {
  const result: Record<string, T[]> = {};
  items.forEach(item => {
    const k = String(item[key]);
    if (!result[k]) result[k] = [];
    result[k].push(item);
  });
  return result;
}
