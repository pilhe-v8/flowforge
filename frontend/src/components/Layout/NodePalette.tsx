import { useRef } from 'react';
import { useWorkflowStore } from '../../stores/workflowStore';
import { NodeType } from '../../types';

const NODE_TYPES: { type: NodeType; label: string; icon: string; colorClass: string }[] = [
  { type: 'trigger', label: 'Trigger', icon: '⚡', colorClass: 'bg-purple-50 border-purple-300 hover:bg-purple-100' },
  { type: 'tool',    label: 'Tool',    icon: '🔧', colorClass: 'bg-green-50 border-green-300 hover:bg-green-100' },
  { type: 'agent',   label: 'Agent',   icon: '🧠', colorClass: 'bg-orange-50 border-orange-300 hover:bg-orange-100' },
  { type: 'router',  label: 'Router',  icon: '◆',  colorClass: 'bg-yellow-50 border-yellow-300 hover:bg-yellow-100' },
  { type: 'gate',    label: 'Gate',    icon: '🛡',  colorClass: 'bg-blue-50 border-blue-300 hover:bg-blue-100' },
  { type: 'output',  label: 'Output',  icon: '📤', colorClass: 'bg-red-50 border-red-300 hover:bg-red-100' },
];

export function NodePalette() {
  const addNode = useWorkflowStore(s => s.addNode);
  const offsetRef = useRef(0);

  return (
    <div className="w-44 bg-white border-r p-3 flex flex-col gap-2 overflow-y-auto">
      <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Nodes</h2>
      {NODE_TYPES.map(({ type, label, icon, colorClass }) => (
        <button
          key={type}
          className={`flex items-center gap-2 border-2 rounded p-2 text-sm cursor-pointer transition-colors ${colorClass}`}
          onClick={() => {
            offsetRef.current = (offsetRef.current + 30) % 300;
            addNode(type, { x: 250 + offsetRef.current, y: 100 + offsetRef.current });
          }}
        >
          <span>{icon}</span>
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
