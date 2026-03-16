import { NodeProps, Handle, Position } from '@xyflow/react';
import { OutputNodeData } from '../../types';
import { useWorkflowStore } from '../../stores/workflowStore';

export function OutputNode({ data, selected, id }: NodeProps) {
  const errors = useWorkflowStore(s => s.errors);
  const hasError = errors.some(e => e.nodeId === id && e.severity === 'error');
  const d = data as unknown as OutputNodeData;
  return (
    <div className={[
      'rounded-lg border-2 p-3 min-w-[180px] bg-red-50 border-red-300',
      selected ? 'ring-2 ring-blue-500' : '',
      hasError ? 'border-red-500 bg-red-100' : '',
    ].join(' ')}>
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <span className="text-red-600">📤</span>
        <span className="font-medium text-sm">{d.label || 'Output'}</span>
      </div>
      <div className="text-xs text-gray-500 mt-1">{d.action || 'No action set'}</div>
    </div>
  );
}
