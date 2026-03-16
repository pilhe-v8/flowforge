import { WorkflowNode, WorkflowEdge, ValidationError, ToolNodeData, AgentNodeData, RouterNodeData, GateNodeData, OutputNodeData, ToolSchema, AgentProfile } from '../types';

export function validateWorkflow(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
  toolCatalogue: ToolSchema[],
  agentProfiles: AgentProfile[],
): ValidationError[] {
  const errors: ValidationError[] = [];

  // 1. Exactly one trigger node
  const triggerNodes = nodes.filter(n => n.type === 'trigger');
  if (triggerNodes.length === 0) {
    errors.push({ nodeId: '', field: 'trigger', message: 'Workflow must have exactly one trigger node', severity: 'error' });
  } else if (triggerNodes.length > 1) {
    triggerNodes.slice(1).forEach(n => {
      errors.push({ nodeId: n.id, field: 'trigger', message: 'Only one trigger node allowed', severity: 'error' });
    });
  }

  // 2. At least one output node
  const outputNodes = nodes.filter(n => n.type === 'output');
  if (outputNodes.length === 0) {
    errors.push({ nodeId: '', field: 'output', message: 'Workflow must have at least one output node', severity: 'warning' });
  }

  // 3. Build reachability from trigger
  const triggerNode = triggerNodes[0];
  if (triggerNode) {
    const reachable = new Set<string>();
    const queue = [triggerNode.id];
    while (queue.length > 0) {
      const nodeId = queue.shift()!;
      if (reachable.has(nodeId)) continue;
      reachable.add(nodeId);
      edges.filter(e => e.source === nodeId).forEach(e => queue.push(e.target));
    }
    nodes.forEach(n => {
      if (!reachable.has(n.id)) {
        errors.push({ nodeId: n.id, field: 'connection', message: 'Node is not reachable from trigger', severity: 'warning' });
      }
    });
  }

  // 4. Tool references valid
  const toolUris = new Set(toolCatalogue.map(t => t.uri));
  nodes.filter(n => n.type === 'tool').forEach(n => {
    const d = n.data as ToolNodeData;
    if (!d.toolUri) {
      errors.push({ nodeId: n.id, field: 'toolUri', message: 'Tool must be selected', severity: 'error' });
    } else if (!toolUris.has(d.toolUri)) {
      errors.push({ nodeId: n.id, field: 'toolUri', message: `Tool "${d.toolUri}" not found in catalogue`, severity: 'warning' });
    }
  });

  // 5. Agent references valid
  const agentSlugs = new Set(agentProfiles.map(a => a.slug));
  nodes.filter(n => n.type === 'agent').forEach(n => {
    const d = n.data as AgentNodeData;
    if (!d.agentSlug) {
      errors.push({ nodeId: n.id, field: 'agentSlug', message: 'Agent profile must be selected', severity: 'error' });
    } else if (!agentSlugs.has(d.agentSlug)) {
      errors.push({ nodeId: n.id, field: 'agentSlug', message: `Agent "${d.agentSlug}" not found`, severity: 'warning' });
    }
  });

  // 6. Router targets exist
  const nodeStepIds = new Set(nodes.map(n => (n.data as { stepId?: string }).stepId ?? n.id));
  nodes.filter(n => n.type === 'router').forEach(n => {
    const d = n.data as RouterNodeData;
    d.routes.forEach(r => {
      if (r.target && !nodeStepIds.has(r.target)) {
        errors.push({ nodeId: n.id, field: 'routes', message: `Route target "${r.target}" does not exist`, severity: 'error' });
      }
    });
    if (d.defaultTarget && !nodeStepIds.has(d.defaultTarget)) {
      errors.push({ nodeId: n.id, field: 'defaultTarget', message: `Default target "${d.defaultTarget}" does not exist`, severity: 'error' });
    }
  });

  // 7. Gate targets exist
  nodes.filter(n => n.type === 'gate').forEach(n => {
    const d = n.data as GateNodeData;
    d.rules.forEach(r => {
      if (r.then && !nodeStepIds.has(r.then)) {
        errors.push({ nodeId: n.id, field: 'rules', message: `Gate target "${r.then}" does not exist`, severity: 'error' });
      }
    });
  });

  // 8. All required fields populated
  nodes.filter(n => n.type === 'output').forEach(n => {
    const d = n.data as OutputNodeData;
    if (!d.action) {
      errors.push({ nodeId: n.id, field: 'action', message: 'Output action must be set', severity: 'error' });
    }
  });

  return errors;
}
