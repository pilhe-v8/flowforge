import { NodeProps, Handle, Position } from '@xyflow/react';
import { TriggerNodeData } from '../../types';
import { useWorkflowStore } from '../../stores/workflowStore';

export function TriggerNode({ data, selected, id }: NodeProps) {
  const errors = useWorkflowStore(s => s.errors);
  const hasError = errors.some(e => e.nodeId === id && e.severity === 'error');
  const d = data as unknown as TriggerNodeData;
  return (
    <div className={[
      'rounded-lg border-2 p-3 min-w-[180px] bg-purple-50 border-purple-300',
      selected ? 'ring-2 ring-blue-500' : '',
      hasError ? 'border-red-500 bg-red-50' : '',
    ].join(' ')}>
      <div className="flex items-center gap-2">
        <span className="text-purple-600">⚡</span>
        <span className="font-medium text-sm">{d.label || 'Trigger'}</span>
      </div>
      <div className="text-xs text-gray-500 mt-1">{d.triggerType}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
