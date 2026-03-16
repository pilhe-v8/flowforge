import { useWorkflowStore } from '../../stores/workflowStore';
import { useToolCatalogueStore } from '../../stores/toolCatalogueStore';
import { ToolNodeData } from '../../types';
import { VariableSelector } from '../shared/VariableSelector';
import { useAvailableVariables } from '../../hooks/useAvailableVariables';

interface Props { nodeId: string }

export function ToolPanel({ nodeId }: Props) {
  const nodes = useWorkflowStore(s => s.nodes);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const tools = useToolCatalogueStore(s => s.tools);
  const node = nodes.find(n => n.id === nodeId);
  const availableVars = useAvailableVariables(nodeId);

  if (!node) return null;
  const d = node.data as ToolNodeData;
  const selectedTool = tools.find(t => t.uri === d.toolUri);

  const update = (patch: Partial<ToolNodeData>) => updateNodeData(nodeId, patch as Parameters<typeof updateNodeData>[1]);

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-gray-700 uppercase tracking-wide">Tool</h3>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Label</label>
        <input
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.label}
          onChange={e => update({ label: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Tool</label>
        <select
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.toolUri}
          onChange={e => {
            const t = tools.find(t => t.uri === e.target.value);
            update({ toolUri: e.target.value, toolName: t?.name });
          }}
        >
          <option value="">Select tool...</option>
          {tools.map(t => (
            <option key={t.uri} value={t.uri}>{t.name}</option>
          ))}
        </select>
      </div>

      {selectedTool?.inputSchema?.properties && (
        <div className="space-y-2">
          <label className="text-xs text-gray-500">Input Mapping</label>
          {Object.entries(selectedTool.inputSchema.properties).map(([param, schema]) => (
            <div key={param} className="space-y-1">
              <label className="text-xs text-gray-400">{param}{schema.description ? ` — ${schema.description}` : ''}</label>
              <VariableSelector
                value={d.inputMapping[param] ?? ''}
                variables={availableVars}
                onChange={val => update({ inputMapping: { ...d.inputMapping, [param]: val } })}
                placeholder={`Map ${param}...`}
              />
            </div>
          ))}
        </div>
      )}

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Output Variables (comma-separated)</label>
        <input
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.outputVars.join(', ')}
          onChange={e => update({ outputVars: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
          placeholder="e.g. result, status"
        />
      </div>

      <div className="space-y-2">
        <label className="flex items-center gap-2 text-xs text-gray-500">
          <input
            type="checkbox"
            checked={d.fallbackEnabled ?? false}
            onChange={e => update({ fallbackEnabled: e.target.checked })}
          />
          Enable Fallback
        </label>
        {d.fallbackEnabled && (
          <div className="pl-4 space-y-2">
            <div className="space-y-1">
              <label className="text-xs text-gray-400">Fallback Condition</label>
              <input
                className="w-full border rounded px-2 py-1 text-sm"
                value={d.fallbackCondition ?? ''}
                onChange={e => update({ fallbackCondition: e.target.value })}
                placeholder="e.g. error == true"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-gray-400">Fallback Agent</label>
              <input
                className="w-full border rounded px-2 py-1 text-sm"
                value={d.fallbackAgent ?? ''}
                onChange={e => update({ fallbackAgent: e.target.value })}
                placeholder="Agent slug..."
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
