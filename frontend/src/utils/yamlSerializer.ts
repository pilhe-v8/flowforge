import yaml from 'js-yaml';
import dagre from 'dagre';
import { WorkflowNode, WorkflowEdge, WorkflowMeta, TriggerNodeData, ToolNodeData, AgentNodeData, RouterNodeData, GateNodeData, OutputNodeData } from '../types';

// ---- Canvas → YAML ----

export function canvasToYaml(nodes: WorkflowNode[], edges: WorkflowEdge[], meta: WorkflowMeta): string {
  const triggerNode = nodes.find(n => n.type === 'trigger');
  if (!triggerNode) throw new Error('No trigger node found');

  const triggerData = triggerNode.data as TriggerNodeData;

  const workflow: Record<string, unknown> = {
    name: meta.name,
    slug: meta.slug,
    version: meta.version,
    description: meta.description,
    trigger: {
      type: triggerData.triggerType,
      config: triggerData.triggerConfig ?? {},
      output: triggerData.outputVars,
    },
    steps: nodes
      .filter(n => n.type !== 'trigger')
      .map(node => serializeStep(node, edges, nodes)),
  };

  return yaml.dump({ workflow }, { lineWidth: 120 });
}

function serializeStep(node: WorkflowNode, edges: WorkflowEdge[], allNodes: WorkflowNode[]): Record<string, unknown> {
  const outEdges = edges.filter(e => e.source === node.id);
  const nextNodeId = outEdges.length === 1 ? outEdges[0].target : undefined;
  const nextNode = nextNodeId ? allNodes.find(n => n.id === nextNodeId) : undefined;
  const nextStepId = nextNode ? (nextNode.data as { stepId?: string }).stepId ?? nextNode.id : undefined;

  const base = {
    id: (node.data as { stepId?: string }).stepId ?? node.id,
    name: (node.data as { label?: string }).label ?? node.id,
    type: node.type,
  };

  switch (node.type) {
    case 'tool': {
      const d = node.data as ToolNodeData;
      return {
        ...base,
        tool: d.toolUri,
        input: d.inputMapping,
        output: d.outputVars,
        ...(d.fallbackEnabled ? {
          fallback: {
            when: d.fallbackCondition,
            agent: d.fallbackAgent,
          }
        } : {}),
        ...(nextStepId ? { next: nextStepId } : {}),
      };
    }
    case 'agent': {
      const d = node.data as AgentNodeData;
      return {
        ...base,
        agent: d.agentSlug,
        ...(d.modelOverride ? { model: d.modelOverride } : {}),
        context: d.context,
        output: d.outputVars,
        ...(nextStepId ? { next: nextStepId } : {}),
      };
    }
    case 'router': {
      const d = node.data as RouterNodeData;
      const routes: Record<string, string> = {};
      d.routes.forEach(r => { routes[r.value] = r.target; });
      return {
        ...base,
        on: d.routeOn,
        routes,
        default: d.defaultTarget,
      };
    }
    case 'gate': {
      const d = node.data as GateNodeData;
      return {
        ...base,
        rules: d.rules,
        default: d.defaultTarget,
      };
    }
    case 'output': {
      const d = node.data as OutputNodeData;
      return {
        ...base,
        action: d.action,
        input: d.inputMapping,
      };
    }
    default:
      return base;
  }
}

// ---- YAML → Canvas ----

export function yamlToCanvas(yamlString: string): { nodes: WorkflowNode[]; edges: WorkflowEdge[]; meta: WorkflowMeta } {
  const doc = yaml.load(yamlString) as { workflow: Record<string, unknown> };
  const wf = doc.workflow;

  const meta: WorkflowMeta = {
    name: wf.name as string,
    slug: wf.slug as string,
    version: wf.version as number,
    description: wf.description as string | undefined,
  };

  const nodes: WorkflowNode[] = [];
  const edges: WorkflowEdge[] = [];
  let edgeCounter = 0;

  // Create trigger node
  const triggerRaw = wf.trigger as Record<string, unknown>;
  const triggerId = 'trigger-node';
  nodes.push({
    id: triggerId,
    type: 'trigger',
    position: { x: 0, y: 0 }, // will be laid out by dagre
    data: {
      stepId: 'trigger',
      label: 'Trigger',
      triggerType: triggerRaw.type as TriggerNodeData['triggerType'],
      triggerConfig: triggerRaw.config as Record<string, string>,
      outputVars: (triggerRaw.output as string[]) ?? [],
    } as TriggerNodeData,
  });

  // Map step_id → node_id (for edge creation)
  const stepIdToNodeId = new Map<string, string>();
  stepIdToNodeId.set('trigger', triggerId);

  // Create step nodes
  const steps = (wf.steps as Record<string, unknown>[]) ?? [];
  steps.forEach(step => {
    const stepId = step.id as string;
    const nodeId = `node-${stepId}`;
    stepIdToNodeId.set(stepId, nodeId);

    let nodeData: WorkflowNode['data'];
    const nodeType = step.type as string;

    switch (nodeType) {
      case 'tool':
        nodeData = {
          stepId,
          label: step.name as string,
          toolUri: step.tool as string,
          inputMapping: (step.input as Record<string, string>) ?? {},
          outputVars: (step.output as string[]) ?? [],
          fallbackEnabled: !!step.fallback,
        } as ToolNodeData;
        break;
      case 'agent':
        nodeData = {
          stepId,
          label: step.name as string,
          agentSlug: step.agent as string,
          modelOverride: step.model as string | undefined,
          context: (step.context as Record<string, string>) ?? {},
          outputVars: (step.output as string[]) ?? [],
        } as AgentNodeData;
        break;
      case 'router': {
        const routes = step.routes as Record<string, string>;
        nodeData = {
          stepId,
          label: step.name as string,
          routeOn: step.on as string,
          routes: Object.entries(routes ?? {}).map(([value, target]) => ({ value, target })),
          defaultTarget: step.default as string,
        } as RouterNodeData;
        break;
      }
      case 'gate':
        nodeData = {
          stepId,
          label: step.name as string,
          rules: (step.rules as Array<{ if: string; then: string; label?: string }>) ?? [],
          defaultTarget: step.default as string,
        } as GateNodeData;
        break;
      case 'output':
        nodeData = {
          stepId,
          label: step.name as string,
          action: step.action as string,
          inputMapping: (step.input as Record<string, string>) ?? {},
        } as OutputNodeData;
        break;
      default:
        nodeData = { stepId, label: step.name as string, outputVars: [] } as unknown as TriggerNodeData;
    }

    nodes.push({
      id: nodeId,
      type: nodeType === 'deterministic' ? 'tool' : nodeType,
      position: { x: 0, y: 0 },
      data: nodeData,
    });
  });

  // Create edges from next/routes/default/rules
  steps.forEach(step => {
    const sourceNodeId = stepIdToNodeId.get(step.id as string);
    if (!sourceNodeId) return;

    if (step.next) {
      const targetNodeId = stepIdToNodeId.get(step.next as string);
      if (targetNodeId) {
        edges.push({ id: `e${edgeCounter++}`, source: sourceNodeId, target: targetNodeId });
      }
    }
    if (step.routes) {
      Object.values(step.routes as Record<string, string>).forEach(targetStepId => {
        const targetNodeId = stepIdToNodeId.get(targetStepId);
        if (targetNodeId) {
          edges.push({ id: `e${edgeCounter++}`, source: sourceNodeId, target: targetNodeId });
        }
      });
    }
    if (step.default) {
      const targetNodeId = stepIdToNodeId.get(step.default as string);
      if (targetNodeId) {
        edges.push({ id: `e${edgeCounter++}`, source: sourceNodeId, target: targetNodeId });
      }
    }
    if (step.rules) {
      (step.rules as Array<{ then: string }>).forEach(rule => {
        const targetNodeId = stepIdToNodeId.get(rule.then);
        if (targetNodeId) {
          edges.push({ id: `e${edgeCounter++}`, source: sourceNodeId, target: targetNodeId });
        }
      });
    }
  });

  // Dagre auto-layout
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80 });
  g.setDefaultEdgeLabel(() => ({}));

  nodes.forEach(n => g.setNode(n.id, { width: 200, height: 60 }));
  edges.forEach(e => g.setEdge(e.source, e.target));
  dagre.layout(g);

  nodes.forEach(n => {
    const pos = g.node(n.id);
    if (pos) {
      n.position = { x: pos.x - 100, y: pos.y - 30 };
    }
  });

  return { nodes, edges, meta };
}
