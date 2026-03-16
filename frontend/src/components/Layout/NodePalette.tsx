import { useState } from 'react';
import { useWorkflowStore } from '../../stores/workflowStore';
import { useToolCatalogueStore } from '../../stores/toolCatalogueStore';
import type { NodeType } from '../../types';

const NODE_TYPES = [
  { type: 'trigger' as NodeType, label: 'Trigger', icon: '⚡', description: 'Workflow entry point' },
  { type: 'tool'    as NodeType, label: 'Tool',    icon: '🔧', description: 'Call an external tool or MCP server' },
  { type: 'agent'   as NodeType, label: 'Agent',   icon: '🧠', description: 'Run an LLM-powered agent' },
  { type: 'router'  as NodeType, label: 'Router',  icon: '◆',  description: 'Branch on a value' },
  { type: 'gate'    as NodeType, label: 'Gate',    icon: '🛡',  description: 'Apply conditional rules' },
  { type: 'output'  as NodeType, label: 'Output',  icon: '📤', description: 'Send a result or call an action' },
];

export function NodePalette() {
  const [tab, setTab] = useState<'types' | 'catalogue'>('types');
  const [search, setSearch] = useState('');
  const addNode = useWorkflowStore(s => s.addNode);
  const updateNodeData = useWorkflowStore(s => s.updateNodeData);
  const nodes = useWorkflowStore(s => s.nodes);
  const tools = useToolCatalogueStore(s => s.tools);
  const agents = useToolCatalogueStore(s => s.agents);

  const nextPosition = () => {
    const offset = (nodes.length % 10) * 30;
    return { x: 250 + offset, y: 100 + offset };
  };

  const addToolFromCatalogue = (tool: { uri: string; name: string; slug: string }) => {
    const pos = nextPosition();
    addNode('tool', pos);
    setTimeout(() => {
      const latestNodes = useWorkflowStore.getState().nodes;
      const added = latestNodes[latestNodes.length - 1];
      if (added) updateNodeData(added.id, { toolUri: tool.uri, toolName: tool.name, label: tool.name });
    }, 0);
  };

  const addAgentFromCatalogue = (agent: { slug: string; name: string }) => {
    const pos = nextPosition();
    addNode('agent', pos);
    setTimeout(() => {
      const latestNodes = useWorkflowStore.getState().nodes;
      const added = latestNodes[latestNodes.length - 1];
      if (added) updateNodeData(added.id, { agentSlug: agent.slug, label: agent.name });
    }, 0);
  };

  const filteredTools = tools.filter((t: { name: string; description?: string }) =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    (t.description?.toLowerCase() ?? '').includes(search.toLowerCase())
  );
  const filteredAgents = agents.filter((a: { name: string }) =>
    a.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="w-56 bg-white border-r border-gray-200 flex flex-col h-full">
      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {(['types', 'catalogue'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-medium capitalize ${
              tab === t
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'types' ? 'Node Types' : 'Catalogue'}
          </button>
        ))}
      </div>

      {tab === 'types' && (
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {NODE_TYPES.map(({ type, label, icon }) => (
            <button
              key={type}
              onClick={() => addNode(type, nextPosition())}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded hover:bg-gray-50 text-left"
            >
              <span>{icon}</span>
              <span>{label}</span>
            </button>
          ))}
        </div>
      )}

      {tab === 'catalogue' && (
        <div className="flex-1 overflow-y-auto flex flex-col">
          <div className="p-2">
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
            />
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-3">
            {filteredTools.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide py-1">Tools</p>
                {filteredTools.map((tool: { uri: string; name: string; slug: string; description?: string }) => (
                  <div key={tool.slug} className="flex items-start justify-between gap-1 py-1">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-800 truncate">🔧 {tool.name}</p>
                      {tool.description && (
                        <p className="text-xs text-gray-400 truncate">{tool.description}</p>
                      )}
                    </div>
                    <button
                      onClick={() => addToolFromCatalogue(tool)}
                      className="shrink-0 text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
                    >
                      +
                    </button>
                  </div>
                ))}
              </div>
            )}
            {filteredAgents.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide py-1">Agents</p>
                {filteredAgents.map((agent: { slug: string; name: string }) => (
                  <div key={agent.slug} className="flex items-center justify-between gap-1 py-1">
                    <p className="text-xs font-medium text-gray-800 truncate">🧠 {agent.name}</p>
                    <button
                      onClick={() => addAgentFromCatalogue(agent)}
                      className="shrink-0 text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
                    >
                      +
                    </button>
                  </div>
                ))}
              </div>
            )}
            {filteredTools.length === 0 && filteredAgents.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">
                {tools.length === 0 && agents.length === 0
                  ? 'No tools or agents registered yet.'
                  : 'No results match your search.'}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
