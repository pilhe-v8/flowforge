import { NodeProps, Handle, Position } from '@xyflow/react';
import { TriggerNodeData } from '../../types';
import { useWorkflowStore } from '../../stores/workflowStore';

export function TriggerNode({ data, selected, id }: NodeProps) {
  const errors = useWorkflowStore(s => s.errors);
  const hasError = errors.some(e => e.nodeId === id && e.severity === 'error');
  const removeNode = useWorkflowStore(s => s.removeNode);
  const d = data as unknown as TriggerNodeData;
  return (
    <div className={[
      'relative rounded-lg border-2 p-3 min-w-[180px] bg-purple-50 border-purple-300',
      selected ? 'ring-2 ring-blue-500' : '',
      hasError ? 'border-red-500 bg-red-50' : '',
    ].join(' ')}>
      {selected && (
        <button
          onClick={e => { e.stopPropagation(); removeNode(id); }}
          className="absolute -top-2 -right-2 z-10 w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center hover:bg-red-600 shadow"
          title="Delete node"
        >
          ×
        </button>
      )}
      <div className="flex items-center gap-2">
        <span className="text-purple-600">⚡</span>
        <span className="font-medium text-sm">{d.label || 'Trigger'}</span>
      </div>
      <div className="text-xs text-gray-500 mt-1">{d.triggerType}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
