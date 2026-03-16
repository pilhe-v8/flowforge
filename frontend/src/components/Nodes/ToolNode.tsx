import { NodeProps, Handle, Position } from '@xyflow/react';
import { ToolNodeData } from '../../types';
import { useWorkflowStore } from '../../stores/workflowStore';

export function ToolNode({ data, selected, id }: NodeProps) {
  const errors = useWorkflowStore(s => s.errors);
  const hasError = errors.some(e => e.nodeId === id && e.severity === 'error');
  const d = data as unknown as ToolNodeData;
  return (
    <div className={[
      'rounded-lg border-2 p-3 min-w-[180px] bg-green-50 border-green-300',
      selected ? 'ring-2 ring-blue-500' : '',
      hasError ? 'border-red-500 bg-red-50' : '',
    ].join(' ')}>
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <span className="text-green-600">🔧</span>
        <span className="font-medium text-sm">{d.label || 'Tool'}</span>
      </div>
      <div className="text-xs text-gray-500 mt-1 truncate">{d.toolName || d.toolUri || 'No tool selected'}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
