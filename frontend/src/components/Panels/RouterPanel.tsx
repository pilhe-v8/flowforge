import { useWorkflowStore } from '../../stores/workflowStore';
import { RouterNodeData, RouterRoute } from '../../types';
import { VariableSelector } from '../shared/VariableSelector';
import { useAvailableVariables } from '../../hooks/useAvailableVariables';

interface Props { nodeId: string }

export function RouterPanel({ nodeId }: Props) {
  const nodes = useWorkflowStore(s => s.nodes);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const node = nodes.find(n => n.id === nodeId);
  const availableVars = useAvailableVariables(nodeId);

  if (!node) return null;
  const d = node.data as RouterNodeData;

  const update = (patch: Partial<RouterNodeData>) => updateNodeData(nodeId, patch as Parameters<typeof updateNodeData>[1]);

  const otherNodes = nodes.filter(n => n.id !== nodeId && n.type !== 'trigger');

  const addRoute = () => update({ routes: [...d.routes, { value: '', target: '' }] });
  const updateRoute = (i: number, patch: Partial<RouterRoute>) => {
    const updated = d.routes.map((r, idx) => idx === i ? { ...r, ...patch } : r);
    update({ routes: updated });
  };
  const removeRoute = (i: number) => update({ routes: d.routes.filter((_, idx) => idx !== i) });

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-gray-700 uppercase tracking-wide">Router</h3>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Label</label>
        <input
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.label}
          onChange={e => update({ label: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Route On Variable</label>
        <VariableSelector
          value={d.routeOn}
          variables={availableVars}
          onChange={val => update({ routeOn: val })}
          placeholder="Select variable to route on..."
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs text-gray-500">Routes</label>
        {d.routes.map((route, i) => (
          <div key={i} className="flex gap-1 items-center">
            <input
              className="border rounded px-1 py-1 text-sm w-24"
              value={route.value}
              onChange={e => updateRoute(i, { value: e.target.value })}
              placeholder="value"
            />
            <span className="text-gray-400">→</span>
            <select
              className="flex-1 border rounded px-1 py-1 text-sm"
              value={route.target}
              onChange={e => updateRoute(i, { target: e.target.value })}
            >
              <option value="">Select target...</option>
              {otherNodes.map(n => (
                <option key={n.id} value={(n.data as { stepId?: string }).stepId ?? n.id}>
                  {(n.data as { label?: string }).label ?? n.id}
                </option>
              ))}
            </select>
            <button onClick={() => removeRoute(i)} className="text-red-400 text-xs">✕</button>
          </div>
        ))}
        <button onClick={addRoute} className="text-blue-500 text-xs hover:underline">+ Add Route</button>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Default Target</label>
        <select
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.defaultTarget}
          onChange={e => update({ defaultTarget: e.target.value })}
        >
          <option value="">Select default target...</option>
          {otherNodes.map(n => (
            <option key={n.id} value={(n.data as { stepId?: string }).stepId ?? n.id}>
              {(n.data as { label?: string }).label ?? n.id}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
