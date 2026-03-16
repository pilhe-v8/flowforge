import { useCallback, useEffect } from 'react';
import { ReactFlow, Background, Controls, MiniMap, applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import type { NodeChange, EdgeChange, Connection, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { nodeTypes } from './components/Nodes';
import { NodePalette } from './components/Layout/NodePalette';
import { Toolbar } from './components/Layout/Toolbar';
import { ValidationBar } from './components/Layout/ValidationBar';
import { useWorkflowStore } from './stores/workflowStore';
import { useToolCatalogueStore } from './stores/toolCatalogueStore';
import { TriggerPanel } from './components/Panels/TriggerPanel';
import { ToolPanel } from './components/Panels/ToolPanel';
import { AgentPanel } from './components/Panels/AgentPanel';
import { RouterPanel } from './components/Panels/RouterPanel';
import { GatePanel } from './components/Panels/GatePanel';
import { OutputPanel } from './components/Panels/OutputPanel';

function PropertiesPanel() {
  const selectedNodeId = useWorkflowStore(s => s.selectedNodeId);
  const nodes = useWorkflowStore(s => s.nodes);
  if (!selectedNodeId) {
    return <div className="p-4 text-gray-400 text-sm">Select a node to configure it</div>;
  }
  const node = nodes.find(n => n.id === selectedNodeId);
  if (!node) return null;
  switch (node.type) {
    case 'trigger': return <TriggerPanel nodeId={selectedNodeId} />;
    case 'tool':    return <ToolPanel nodeId={selectedNodeId} />;
    case 'agent':   return <AgentPanel nodeId={selectedNodeId} />;
    case 'router':  return <RouterPanel nodeId={selectedNodeId} />;
    case 'gate':    return <GatePanel nodeId={selectedNodeId} />;
    case 'output':  return <OutputPanel nodeId={selectedNodeId} />;
    default:        return <div className="p-4 text-sm text-gray-500">Unknown node type</div>;
  }
}

export default function App() {
  const nodes = useWorkflowStore(s => s.nodes);
  const edges = useWorkflowStore(s => s.edges);
  const setNodes = useWorkflowStore(s => s.setNodes);
  const setEdges = useWorkflowStore(s => s.setEdges);
  const selectNode = useWorkflowStore(s => s.selectNode);
  const connectNodes = useWorkflowStore(s => s.connectNodes);
  const removeNode = useWorkflowStore(s => s.removeNode);
  const tools = useToolCatalogueStore(s => s.tools);
  const agents = useToolCatalogueStore(s => s.agents);
  const revalidate = useWorkflowStore(s => s.revalidate);
  const fetchCatalogue = useToolCatalogueStore(s => s.fetchCatalogue);
  const fetchAgentsAction = useToolCatalogueStore(s => s.fetchAgents);

  useEffect(() => {
    void fetchCatalogue();
    void fetchAgentsAction();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    revalidate(tools, agents);
  }, [nodes, edges, tools, agents, revalidate]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes(applyNodeChanges(changes, nodes) as typeof nodes);
    },
    [nodes, setNodes],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges(applyEdgeChanges(changes, edges) as typeof edges);
    },
    [edges, setEdges],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      connectNodes(connection);
    },
    [connectNodes],
  );

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      deleted.forEach(n => removeNode(n.id));
    },
    [removeNode],
  );

  return (
    <div className="h-screen w-screen flex flex-col">
      <Toolbar />
      <div className="flex flex-1 overflow-hidden">
        <NodePalette />
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodesDelete={onNodesDelete}
            deleteKeyCode="Delete"
            onNodeClick={(_: React.MouseEvent, node: Node) => selectNode(node.id)}
            onPaneClick={() => selectNode(null)}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        <div className="w-72 bg-white border-l overflow-y-auto">
          <PropertiesPanel />
        </div>
      </div>
      <ValidationBar />
    </div>
  );
}
