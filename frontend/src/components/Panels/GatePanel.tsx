import { useWorkflowStore } from '../../stores/workflowStore';
import { GateNodeData } from '../../types';
import { ConditionBuilder } from '../shared/ConditionBuilder';
import { useAvailableVariables } from '../../hooks/useAvailableVariables';

interface Props { nodeId: string }

export function GatePanel({ nodeId }: Props) {
  const nodes = useWorkflowStore(s => s.nodes);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const node = nodes.find(n => n.id === nodeId);
  const availableVars = useAvailableVariables(nodeId);

  if (!node) return null;
  const d = node.data as GateNodeData;

  const update = (patch: Partial<GateNodeData>) => updateNodeData(nodeId, patch as Parameters<typeof updateNodeData>[1]);

  const otherNodes = nodes
    .filter(n => n.id !== nodeId && n.type !== 'trigger')
    .map(n => ({
      id: (n.data as { stepId?: string }).stepId ?? n.id,
      label: (n.data as { label?: string }).label ?? n.id,
    }));

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-gray-700 uppercase tracking-wide">Gate</h3>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Label</label>
        <input
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.label}
          onChange={e => update({ label: e.target.value })}
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs text-gray-500">Rules</label>
        <ConditionBuilder
          rules={d.rules}
          onUpdate={rules => update({ rules })}
          availableVars={availableVars}
          availableTargets={otherNodes}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Default Target (no rule matched)</label>
        <select
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.defaultTarget}
          onChange={e => update({ defaultTarget: e.target.value })}
        >
          <option value="">Select default target...</option>
          {otherNodes.map(n => (
            <option key={n.id} value={n.id}>{n.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
