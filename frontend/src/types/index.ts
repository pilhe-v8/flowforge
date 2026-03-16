import { Node, Edge } from '@xyflow/react';

// Trigger types
export type TriggerType = 'email_received' | 'webhook' | 'schedule' | 'manual';

// Node types
export type NodeType = 'trigger' | 'tool' | 'agent' | 'router' | 'gate' | 'output';

// Gate rule
export interface GateRule {
  if: string;       // expression string
  then: string;     // target step id
  label?: string;
}

// Router route
export interface RouterRoute {
  value: string;
  target: string;
}

// Node data variants
export interface TriggerNodeData {
  stepId: string;
  label: string;
  triggerType: TriggerType;
  triggerConfig?: Record<string, string>;
  outputVars: string[];
  [key: string]: unknown;
}

export interface ToolNodeData {
  stepId: string;
  label: string;
  toolUri: string;
  toolName?: string;
  inputMapping: Record<string, string>;
  outputVars: string[];
  fallbackEnabled?: boolean;
  fallbackCondition?: string;
  fallbackAgent?: string;
  [key: string]: unknown;
}

export interface AgentNodeData {
  stepId: string;
  label: string;
  agentSlug: string;
  modelOverride?: string;
  context: Record<string, string>;
  outputVars: string[];
  [key: string]: unknown;
}

export interface RouterNodeData {
  stepId: string;
  label: string;
  routeOn: string;        // variable ref like "{{classify.intent}}"
  routes: RouterRoute[];
  defaultTarget: string;
  [key: string]: unknown;
}

export interface GateNodeData {
  stepId: string;
  label: string;
  rules: GateRule[];
  defaultTarget: string;
  [key: string]: unknown;
}

export interface OutputNodeData {
  stepId: string;
  label: string;
  action: string;
  inputMapping: Record<string, string>;
  [key: string]: unknown;
}

export type NodeData = TriggerNodeData | ToolNodeData | AgentNodeData | RouterNodeData | GateNodeData | OutputNodeData;
export type WorkflowNode = Node<NodeData>;
export type WorkflowEdge = Edge;

// Variable info (for dropdowns)
export interface VariableInfo {
  stepId: string;
  stepName: string;
  variableName: string;
  fullRef: string;    // "{{step_id.variable_name}}"
  type?: string;
}

// Tool catalogue
export interface ToolSchema {
  slug: string;
  name: string;
  uri: string;
  protocol: string;
  description?: string;
  inputSchema: {
    type: string;
    properties: Record<string, { type: string; description?: string }>;
    required?: string[];
  };
  outputSchema: {
    type: string;
    properties: Record<string, { type: string; description?: string }>;
  };
}

// Agent profile
export interface AgentProfile {
  slug: string;
  name: string;
  content?: string;
}

// Validation
export interface ValidationError {
  nodeId: string;
  field: string;
  message: string;
  severity: 'error' | 'warning';
}

// Workflow meta
export interface WorkflowMeta {
  name: string;
  slug: string;
  version: number;
  description?: string;
}

// API types
export interface WorkflowVersion {
  id: string;
  version: number;
  status: 'draft' | 'active' | 'archived';
  yaml_definition: string;
  created_at: string;
}

export interface Execution {
  id: string;
  workflow_slug: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  trigger_data: Record<string, unknown>;
  created_at: string;
}

export interface ExecutionStep {
  id: string;
  step_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  created_at: string;
}
