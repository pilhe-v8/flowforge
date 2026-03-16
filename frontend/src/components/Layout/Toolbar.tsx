import { useRef } from 'react';
import { useWorkflowStore } from '../../stores/workflowStore';
import { TestRunner } from '../TestRunner';

export function Toolbar() {
  const meta = useWorkflowStore(s => s.meta);
  const isDirty = useWorkflowStore(s => s.isDirty);
  const updateMeta = useWorkflowStore(s => s.updateMeta);
  const save = useWorkflowStore(s => s.save);
  const deploy = useWorkflowStore(s => s.deploy);
  const undo = useWorkflowStore(s => s.undo);
  const redo = useWorkflowStore(s => s.redo);
  const loadYaml = useWorkflowStore(s => s.loadYaml);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleLoadFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      if (typeof ev.target?.result === 'string') {
        loadYaml(ev.target.result);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="h-12 bg-white border-b flex items-center px-4 gap-2 shadow-sm flex-shrink-0">
      <span className="font-bold text-blue-600 text-lg mr-2">⚡ FlowForge</span>
      <input
        className="border rounded px-2 py-1 text-sm w-48"
        value={meta.name}
        onChange={e => updateMeta({ name: e.target.value })}
        placeholder="Workflow name"
      />
      {/* Fix 5: Version badge */}
      <span className="text-xs text-gray-500 border rounded px-2 py-1">v{meta.version}</span>
      <div className="flex items-center gap-1 ml-2">
        <button
          disabled={!isDirty}
          onClick={() => { save().catch(() => {}); }}
          className="px-3 py-1 bg-blue-500 text-white rounded text-sm disabled:opacity-40 hover:bg-blue-600"
        >
          💾 Save
        </button>
        <button
          onClick={() => { deploy().catch(() => {}); }}
          className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
        >
          🚀 Deploy
        </button>
        <button onClick={undo} className="px-2 py-1 border rounded text-sm hover:bg-gray-50">↩</button>
        <button onClick={redo} className="px-2 py-1 border rounded text-sm hover:bg-gray-50">↪</button>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="px-2 py-1 border rounded text-sm hover:bg-gray-50"
        >
          📂 Load YAML
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".yaml,.yml"
          className="hidden"
          onChange={handleLoadFile}
        />
        {/* Fix 1: Test Runner button */}
        <TestRunner onHighlight={(ids) => console.log('Highlighted step IDs:', ids)} />
      </div>
      {isDirty && <span className="text-xs text-orange-500 ml-auto">● Unsaved changes</span>}
    </div>
  );
}
