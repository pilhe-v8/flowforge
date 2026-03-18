import { create } from 'zustand';
import { XYPosition, addEdge as rfAddEdge, Connection } from '@xyflow/react';
import { WorkflowNode, WorkflowEdge, ValidationError, WorkflowMeta, NodeType, TriggerNodeData, ToolNodeData, AgentNodeData, RouterNodeData, GateNodeData, OutputNodeData, NodeData, ToolSchema, AgentProfile } from '../types';
import { validateWorkflow } from '../utils/validation';
import { canvasToYaml, yamlToCanvas } from '../utils/yamlSerializer';
import { saveWorkflow as apiSave, deployWorkflow as apiDeploy, fetchWorkflow as apiFetch } from '../api/workflows';

// ---- Undo/Redo history ----
interface HistoryEntry {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

function makeDefaultNodeData(type: NodeType, id: string): NodeData {
  const stepId = `${type}-${id.slice(0, 6)}`;
  switch (type) {
    case 'trigger':
      return { stepId, label: 'Trigger', triggerType: 'manual', outputVars: [] } as TriggerNodeData;
    case 'tool':
      return { stepId, label: 'Tool', toolUri: '', inputMapping: {}, outputVars: [] } as ToolNodeData;
    case 'agent':
      return { stepId, label: 'Agent', systemPrompt: 'You are a helpful assistant.', context: {}, outputVars: ['reply'] } as AgentNodeData;
    case 'router':
      return { stepId, label: 'Router', routeOn: '', routes: [], defaultTarget: '' } as RouterNodeData;
    case 'gate':
      return { stepId, label: 'Gate', rules: [], defaultTarget: '' } as GateNodeData;
    case 'output':
      return { stepId, label: 'Output', action: '', inputMapping: {} } as OutputNodeData;
  }
}

interface WorkflowState {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedNodeId: string | null;
  meta: WorkflowMeta;
  isDirty: boolean;
  errors: ValidationError[];
  history: HistoryEntry[];
  historyIndex: number;

  // React Flow setters (for controlled flow)
  setNodes: (nodes: WorkflowNode[]) => void;
  setEdges: (edges: WorkflowEdge[]) => void;

  // Actions
  addNode: (type: NodeType, position: XYPosition) => void;
  removeNode: (id: string) => void;
  updateNodeData: (id: string, data: Partial<NodeData>) => void;
  connectNodes: (connection: Connection) => void;
  removeEdge: (id: string) => void;
  selectNode: (id: string | null) => void;
  updateMeta: (meta: Partial<WorkflowMeta>) => void;
  save: () => Promise<void>;
  deploy: () => Promise<void>;
  loadWorkflow: (slug: string) => Promise<void>;
  loadYaml: (yamlString: string) => void;
  undo: () => void;
  redo: () => void;
  revalidate: (toolCatalogue: ToolSchema[], agentProfiles: AgentProfile[]) => void;
  pushHistory: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  meta: { name: 'Untitled Workflow', slug: 'untitled', version: 1 },
  isDirty: false,
  errors: [],
  history: [],
  historyIndex: -1,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  pushHistory: () => {
    const { nodes, edges, history, historyIndex } = get();
    const entry: HistoryEntry = { nodes: [...nodes], edges: [...edges] };
    const newHistory = history.slice(0, historyIndex + 1).concat(entry);
    set({ history: newHistory, historyIndex: newHistory.length - 1 });
  },

  addNode: (type, position) => {
    get().pushHistory();
    const id = `${type}-${Date.now()}`;
    const newNode: WorkflowNode = {
      id,
      type,
      position,
      data: makeDefaultNodeData(type, id),
    };
    set(s => ({ nodes: [...s.nodes, newNode], isDirty: true }));
  },

  removeNode: (id) => {
    get().pushHistory();
    set(s => ({
      nodes: s.nodes.filter(n => n.id !== id),
      edges: s.edges.filter(e => e.source !== id && e.target !== id),
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
      isDirty: true,
    }));
  },

  updateNodeData: (id, data) => {
    set(s => ({
      nodes: s.nodes.map(n => n.id === id ? { ...n, data: { ...n.data, ...data } } : n),
      isDirty: true,
    }));
  },

  connectNodes: (connection) => {
    get().pushHistory();
    set(s => ({
      edges: rfAddEdge(connection, s.edges) as WorkflowEdge[],
      isDirty: true,
    }));
  },

  removeEdge: (id) => {
    get().pushHistory();
    set(s => ({ edges: s.edges.filter(e => e.id !== id), isDirty: true }));
  },

  selectNode: (id) => set({ selectedNodeId: id }),

  updateMeta: (meta) => set(s => ({ meta: { ...s.meta, ...meta }, isDirty: true })),

  save: async () => {
    const { nodes, edges, meta } = get();
    const yamlStr = canvasToYaml(nodes, edges, meta);
    await apiSave(meta.slug, yamlStr);
    set({ isDirty: false });
  },

  deploy: async () => {
    const { meta } = get();
    await apiDeploy(meta.slug);
  },

  loadWorkflow: async (slug) => {
    const version = await apiFetch(slug);
    const { nodes, edges, meta } = yamlToCanvas(version.yaml_definition);
    set({ nodes, edges, meta: { ...meta, slug }, isDirty: false, history: [], historyIndex: -1 });
  },

  loadYaml: (yamlString) => {
    try {
      const { nodes, edges, meta } = yamlToCanvas(yamlString);
      set({ nodes, edges, meta, isDirty: false, history: [], historyIndex: -1 });
    } catch (e) {
      console.error('Failed to parse YAML:', e);
    }
  },

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex <= 0) return;
    const entry = history[historyIndex - 1];
    set({ nodes: entry.nodes, edges: entry.edges, historyIndex: historyIndex - 1, isDirty: true });
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex >= history.length - 1) return;
    const entry = history[historyIndex + 1];
    set({ nodes: entry.nodes, edges: entry.edges, historyIndex: historyIndex + 1, isDirty: true });
  },

  revalidate: (toolCatalogue, agentProfiles) => {
    const { nodes, edges } = get();
    const errors = validateWorkflow(nodes, edges, toolCatalogue, agentProfiles);
    set({ errors });
  },
}));
