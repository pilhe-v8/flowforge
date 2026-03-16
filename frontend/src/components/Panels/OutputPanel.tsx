import { useWorkflowStore } from '../../stores/workflowStore';
import { useToolCatalogueStore } from '../../stores/toolCatalogueStore';
import { OutputNodeData } from '../../types';
import { VariableSelector } from '../shared/VariableSelector';
import { useAvailableVariables } from '../../hooks/useAvailableVariables';

interface Props { nodeId: string }

const COMMON_ACTIONS = [
  'send_email',
  'send_slack_message',
  'create_ticket',
  'update_record',
  'webhook_response',
  'log',
];

export function OutputPanel({ nodeId }: Props) {
  const nodes = useWorkflowStore(s => s.nodes);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const tools = useToolCatalogueStore(s => s.tools);
  const node = nodes.find(n => n.id === nodeId);
  const availableVars = useAvailableVariables(nodeId);

  if (!node) return null;
  const d = node.data as OutputNodeData;

  const update = (patch: Partial<OutputNodeData>) => updateNodeData(nodeId, patch as Parameters<typeof updateNodeData>[1]);

  // Collect action options from tool catalogue + common actions
  const toolActions = tools.map(t => t.slug);
  const allActions = [...new Set([...COMMON_ACTIONS, ...toolActions])];

  const addMapping = () => update({ inputMapping: { ...d.inputMapping, '': '' } });
  const updateMappingKey = (oldKey: string, newKey: string) => {
    const newMapping: Record<string, string> = {};
    Object.entries(d.inputMapping).forEach(([k, v]) => {
      newMapping[k === oldKey ? newKey : k] = v;
    });
    update({ inputMapping: newMapping });
  };
  const updateMappingValue = (key: string, value: string) => {
    update({ inputMapping: { ...d.inputMapping, [key]: value } });
  };
  const removeMappingKey = (key: string) => {
    const newMapping = { ...d.inputMapping };
    delete newMapping[key];
    update({ inputMapping: newMapping });
  };

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-gray-700 uppercase tracking-wide">Output</h3>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Label</label>
        <input
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.label}
          onChange={e => update({ label: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Action</label>
        <select
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.action}
          onChange={e => update({ action: e.target.value })}
        >
          <option value="">Select action...</option>
          {allActions.map(a => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-gray-500">Input Mapping</label>
        {Object.entries(d.inputMapping).map(([key, value]) => (
          <div key={key} className="flex gap-1 items-center">
            <input
              className="border rounded px-1 py-1 text-sm w-24"
              value={key}
              onChange={e => updateMappingKey(key, e.target.value)}
              placeholder="param"
            />
            <span className="text-gray-400">→</span>
            <div className="flex-1">
              <VariableSelector
                value={value}
                variables={availableVars}
                onChange={val => updateMappingValue(key, val)}
                placeholder="Select variable..."
              />
            </div>
            <button onClick={() => removeMappingKey(key)} className="text-red-400 text-xs">✕</button>
          </div>
        ))}
        <button onClick={addMapping} className="text-blue-500 text-xs hover:underline">+ Add Mapping</button>
      </div>
    </div>
  );
}
