# 07 - Visual Builder Frontend Specification

## Overview

The visual builder is a React application providing a constrained drag-and-drop
interface for designing workflows. It produces YAML workflow definitions consumed
by the backend compiler.

## Technology

- React 18, TypeScript (strict mode)
- React Flow v12 for the node graph canvas
- Zustand for state management
- Vite for build tooling
- Tailwind CSS for styling
- js-yaml for YAML serialization
- dagre for auto-layout

## Layout

```
+------------------------------------------------------------------+
|  Toolbar: [Save] [Deploy] [Test] [Version: v3 ▼] [Undo] [Redo]  |
+--------+-----------------------------------------+---------------+
|        |                                         |               |
| Node   |          Canvas                         | Properties   |
| Palette|          (React Flow)                   | Panel        |
|        |                                         |               |
| [Trigger]         +----------+                   | (context-    |
| [Tool]            | Classify |---+               |  sensitive   |
| [Agent]           +----------+   |               |  config for  |
| [Router]                  +------+-----+         |  selected    |
| [Gate]                    | Route      |         |  node)       |
| [Output]                  +---+---+----+         |               |
|                               |   |              |               |
+--------+-----------------------------------------+---------------+
|  Validation bar: [All checks passed] or [2 errors - click to see]|
+------------------------------------------------------------------+
```

## Node Palette (6 Types)

### 1. Trigger Node (exactly 1 per workflow)
- Icon: Lightning bolt, Color: Purple
- Config: type dropdown (email_received, webhook, schedule, manual)
- Type-specific config fields appear based on selection
- Output variables auto-populated based on trigger type

### 2. Tool Node
- Icon: Wrench, Color: Green (signifies deterministic/no LLM)
- Config:
  - Tool dropdown (populated from GET /api/v1/tools/catalogue)
  - On selection: input fields auto-generated from tool input_schema
  - Each input has a VariableSelector dropdown (upstream variables)
  - Output checkboxes from tool output_schema
  - Optional: fallback toggle (enables agent fallback section)
    - Fallback condition field (e.g., "confidence < 0.85")
    - Agent dropdown for fallback

### 3. Agent Node
- Icon: Brain, Color: Orange (signifies LLM cost)
- Config:
  - Agent profile dropdown (from GET /api/v1/agents)
  - Model override dropdown (optional)
  - Context: list of VariableSelector dropdowns
  - Output variable names (text inputs)

### 4. Router Node
- Icon: Diamond/fork, Color: Yellow
- Config:
  - "Route on" variable selector
  - Route table: [value field] -> [target node dropdown]
  - [+ Add Route] button
  - Default route: [target node dropdown]
  - Target dropdowns only show existing nodes

### 5. Gate Node
- Icon: Shield/checkmark, Color: Blue
- Config:
  - Condition builder (visual, no code):
    - Row: [variable dropdown] [operator dropdown] [value field] -> [target dropdown]
    - Operators: equals, not equals, less than, greater than, contains,
      starts with, is empty, length less than, length greater than
    - AND/OR combinators for multi-condition rules
    - Label field per rule
  - Default target: [node dropdown]

### 6. Output Node
- Icon: Send arrow, Color: Red
- Config:
  - Action dropdown (from tool catalogue, filtered to output-type tools)
  - Input mapping (same as Tool node)

## Variable Tracking System

The frontend maintains a real-time map of available variables at each node position.

```typescript
// utils/variableResolver.ts

interface VariableInfo {
  stepId: string;
  stepName: string;
  variableName: string;
  fullRef: string;    // "{{step_id.variable_name}}"
  type?: string;      // from tool schema if available
}

function getAvailableVariables(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
  currentNodeId: string,
): VariableInfo[] {
  // 1. Build directed graph from edges
  // 2. BFS backwards from currentNodeId to find all upstream nodes
  // 3. Collect output variables from upstream nodes + trigger outputs
  // 4. Return sorted list for dropdown
}
```

Recalculated every time graph changes. Properties panels re-render dropdowns.

## YAML Serializer

```typescript
// utils/yamlSerializer.ts

function canvasToYaml(nodes, edges, meta): string {
  const workflow = {
    name: meta.name,
    slug: meta.slug,
    version: meta.version,
    trigger: serializeTrigger(findTriggerNode(nodes)),
    steps: nodes
      .filter(n => n.type !== "trigger")
      .map(node => serializeStep(node, edges, nodes)),
  };
  return yaml.dump({ workflow }, { lineWidth: 120 });
}
```

## YAML Deserializer

Loading existing workflow YAML back into canvas:

```typescript
function yamlToCanvas(yamlString: string): { nodes, edges } {
  const { workflow } = yaml.load(yamlString);
  // Create trigger node
  // Create step nodes with dagre auto-layout
  // Create edges from next/routes/default/rules references
}
```

## Real-Time Validation

```typescript
interface ValidationError {
  nodeId: string;
  field: string;
  message: string;
  severity: "error" | "warning";
}

function validateWorkflow(nodes, edges, toolCatalogue, agentProfiles): ValidationError[] {
  // 1. Exactly one trigger node
  // 2. All nodes reachable from trigger
  // 3. At least one output node
  // 4. Tool references valid (exist in catalogue)
  // 5. Agent references valid (exist in profiles)
  // 6. Variable references valid (produced by upstream steps)
  // 7. Router targets exist as node IDs
  // 8. No infinite loops without a gate
  // 9. All required fields populated
}
```

Errors show as red borders on nodes and in the bottom validation bar.

## Zustand Store

```typescript
// stores/workflowStore.ts

interface WorkflowState {
  nodes: ReactFlowNode[];
  edges: ReactFlowEdge[];
  selectedNodeId: string | null;
  workflowSlug: string;
  workflowName: string;
  version: number;
  isDirty: boolean;
  errors: ValidationError[];

  // Actions
  addNode: (type: NodeType, position: XYPosition) => void;
  removeNode: (id: string) => void;
  updateNodeData: (id: string, data: Partial<NodeData>) => void;
  addEdge: (source: string, target: string) => void;
  removeEdge: (id: string) => void;
  selectNode: (id: string | null) => void;
  save: () => Promise<void>;       // PUT /api/v1/workflows/{slug}
  deploy: () => Promise<void>;     // POST /api/v1/workflows/{slug}/deploy
  loadWorkflow: (slug: string) => Promise<void>;
  undo: () => void;
  redo: () => void;
}
```

```typescript
// stores/toolCatalogueStore.ts

interface ToolCatalogueState {
  tools: ToolSchema[];
  agents: AgentProfile[];
  loading: boolean;
  fetchCatalogue: () => Promise<void>;   // GET /api/v1/tools/catalogue
  fetchAgents: () => Promise<void>;       // GET /api/v1/agents
}
```

## Node Component Example

```tsx
// components/Nodes/ToolNode.tsx

function ToolNode({ data, selected }: NodeProps<ToolNodeData>) {
  const hasError = useWorkflowStore(s =>
    s.errors.some(e => e.nodeId === data.stepId && e.severity === "error")
  );

  return (
    <div className={cn(
      "rounded-lg border-2 p-3 min-w-[180px]",
      "bg-green-50 border-green-300",
      selected && "ring-2 ring-blue-500",
      hasError && "border-red-500 bg-red-50",
    )}>
      <div className="flex items-center gap-2">
        <WrenchIcon className="w-4 h-4 text-green-600" />
        <span className="font-medium text-sm">{data.label || "Tool"}</span>
      </div>
      {data.toolName && (
        <div className="text-xs text-gray-500 mt-1">{data.toolName}</div>
      )}
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

## Properties Panel Example

```tsx
// components/Panels/ToolPanel.tsx

function ToolPanel({ nodeId }: { nodeId: string }) {
  const node = useWorkflowStore(s => s.nodes.find(n => n.id === nodeId));
  const tools = useToolCatalogueStore(s => s.tools);
  const updateNode = useWorkflowStore(s => s.updateNodeData);
  const availableVars = useAvailableVariables(nodeId);

  const selectedTool = tools.find(t => t.uri === node.data.toolUri);

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold">Tool Node</h3>

      {/* Tool selector */}
      <label>Tool</label>
      <select
        value={node.data.toolUri || ""}
        onChange={e => updateNode(nodeId, { toolUri: e.target.value })}
      >
        <option value="">Select a tool...</option>
        {tools.map(t => (
          <option key={t.uri} value={t.uri}>{t.name}</option>
        ))}
      </select>

      {/* Auto-generated input mapping */}
      {selectedTool && (
        <>
          <h4>Inputs</h4>
          {Object.entries(selectedTool.inputSchema.properties).map(([param, schema]) => (
            <div key={param}>
              <label>{param} {schema.required && "*"}</label>
              <VariableSelector
                value={node.data.inputMapping?.[param]}
                variables={availableVars}
                onChange={val => updateNode(nodeId, {
                  inputMapping: { ...node.data.inputMapping, [param]: val }
                })}
              />
            </div>
          ))}

          <h4>Outputs</h4>
          {Object.keys(selectedTool.outputSchema.properties).map(varName => (
            <label key={varName} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={node.data.outputVars?.includes(varName)}
                onChange={...}
              />
              {varName}
            </label>
          ))}
        </>
      )}
    </div>
  );
}
```

## VariableSelector Component

```tsx
// components/shared/VariableSelector.tsx

function VariableSelector({ value, variables, onChange }) {
  return (
    <select value={value || ""} onChange={e => onChange(e.target.value)}>
      <option value="">Select variable...</option>
      {/* Group by source step */}
      {Object.entries(groupBy(variables, "stepName")).map(([stepName, vars]) => (
        <optgroup key={stepName} label={stepName}>
          {vars.map(v => (
            <option key={v.fullRef} value={v.fullRef}>
              {v.variableName} {v.type && `(${v.type})`}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
```

## ConditionBuilder Component

```tsx
// components/shared/ConditionBuilder.tsx

function ConditionBuilder({ rules, onUpdate, availableVars, availableTargets }) {
  return (
    <div className="space-y-3">
      {rules.map((rule, i) => (
        <div key={i} className="border rounded p-2 space-y-2">
          <div className="flex gap-2 items-center">
            <VariableSelector variables={availableVars} ... />
            <select>{/* operators: equals, not equals, less than, etc. */}</select>
            <input type="text" placeholder="value" />
          </div>
          <div className="flex gap-2 items-center">
            <span>then go to</span>
            <select>
              {availableTargets.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <input type="text" placeholder="Label (e.g., VIP escalation)" />
        </div>
      ))}
      <button onClick={addRule}>+ Add Rule</button>
    </div>
  );
}
```

## Test Runner

The toolbar Test button allows running a workflow with sample input:

1. User clicks Test, enters sample input data (JSON)
2. Frontend calls POST /api/v1/executions/trigger with the data
3. Frontend opens WebSocket to WS /ws/executions/{execution_id}
4. As each step completes, the corresponding node on canvas highlights
5. Step outputs shown in a side panel
6. On completion, full trace displayed
