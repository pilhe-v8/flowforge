import { useWorkflowStore } from '../../stores/workflowStore';
import { TriggerNodeData, TriggerType } from '../../types';

interface Props { nodeId: string }

const TRIGGER_TYPES: { value: TriggerType; label: string }[] = [
  { value: 'manual', label: 'Manual' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'schedule', label: 'Schedule' },
  { value: 'email_received', label: 'Email Received' },
];

// Default output vars per trigger type — applied automatically on type change
const TRIGGER_OUTPUTS: Record<string, string[]> = {
  email_received: ['sender', 'subject', 'body', 'attachments', 'received_at'],
  webhook: ['payload', 'headers', 'received_at'],
  schedule: ['scheduled_at', 'run_id'],
  manual: ['input_data'],
};

export function TriggerPanel({ nodeId }: Props) {
  const nodes = useWorkflowStore(s => s.nodes);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const node = nodes.find(n => n.id === nodeId);
  if (!node) return null;
  const d = node.data as TriggerNodeData;

  const update = (patch: Partial<TriggerNodeData>) => updateNodeData(nodeId, patch as Parameters<typeof updateNodeData>[1]);

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm text-gray-700 uppercase tracking-wide">Trigger</h3>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Label</label>
        <input
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.label}
          onChange={e => update({ label: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-gray-500">Trigger Type</label>
        <select
          className="w-full border rounded px-2 py-1 text-sm"
          value={d.triggerType}
          onChange={e => {
            const newType = e.target.value as TriggerType;
            update({ triggerType: newType, outputVars: TRIGGER_OUTPUTS[newType] ?? [] });
          }}
        >
          {TRIGGER_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {d.triggerType === 'schedule' && (
        <div className="space-y-1">
          <label className="text-xs text-gray-500">Cron Expression</label>
          <input
            className="w-full border rounded px-2 py-1 text-sm"
            value={d.triggerConfig?.cron ?? ''}
            onChange={e => update({ triggerConfig: { ...d.triggerConfig, cron: e.target.value } })}
            placeholder="e.g. 0 9 * * 1-5"
          />
        </div>
      )}
    </div>
  );
}
