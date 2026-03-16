import { useWorkflowStore } from '../../stores/workflowStore';
import { useModelsStore } from '../../stores/modelsStore';
import { AgentNodeData } from '../../types';
import { VariableSelector } from '../shared/VariableSelector';
import { useAvailableVariables } from '../../hooks/useAvailableVariables';

interface Props { nodeId: string }

const DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.';

export function AgentPanel({ nodeId }: Props) {
  const nodes = useWorkflowStore(s => s.nodes);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const models = useModelsStore(s => s.models);
  const node = nodes.find(n => n.id === nodeId);
  const availableVars = useAvailableVariables(nodeId);

  if (!node) return null;
  const d = node.data as AgentNodeData;

  const update = (patch: Partial<AgentNodeData>) => updateNodeData(nodeId, patch as Parameters<typeof updateNodeData>[1]);

  const addContextKey = () => update({ context: { ...d.context, '': '' } });
  const updateContextKey = (oldKey: string, newKey: string) => {
    const newContext: Record<string, string> = {};
    Object.entries(d.context).forEach(([k, v]) => {
      newContext[k === oldKey ? newKey : k] = v;
    });
    update({ context: newContext });
  };
  const updateContextValue = (key: string, value: string) => {
    update({ context: { ...d.context, [key]: value } });
  };
  const removeContextKey = (key: string) => {
    const newContext = { ...d.context };
    delete newContext[key];
    update({ context: newContext });
  };

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-gray-700 uppercase tracking-wide">Agent</h3>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Label</label>
        <input
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.label}
          onChange={e => update({ label: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">System Prompt</label>
        <textarea
          className="w-full border rounded px-2 py-1 text-sm h-24 resize-none"
          value={d.systemPrompt ?? DEFAULT_SYSTEM_PROMPT}
          onChange={e => update({ systemPrompt: e.target.value })}
          placeholder="You are a helpful assistant."
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Model</label>
        <select
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.modelOverride ?? 'default'}
          onChange={e => update({ modelOverride: e.target.value })}
        >
          {models.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-gray-500">Context Variables</label>
        {Object.entries(d.context).map(([key, value]) => (
          <div key={key} className="flex gap-1 items-center">
            <input
              className="border rounded px-1 py-1 text-sm w-24"
              value={key}
              onChange={e => updateContextKey(key, e.target.value)}
              placeholder="key"
            />
            <span className="text-gray-400">→</span>
            <div className="flex-1">
              <VariableSelector
                value={value}
                variables={availableVars}
                onChange={val => updateContextValue(key, val)}
                placeholder="Select variable..."
              />
            </div>
            <button onClick={() => removeContextKey(key)} className="text-red-400 text-xs">✕</button>
          </div>
        ))}
        <button onClick={addContextKey} className="text-blue-500 text-xs hover:underline">+ Add Context</button>
      </div>

      <div className="text-xs text-gray-400 italic">Output: reply</div>
    </div>
  );
}
