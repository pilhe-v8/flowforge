import { useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import { ReactFlow, Background, Controls, MiniMap, applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import type { NodeChange, EdgeChange, Connection, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { nodeTypes } from './components/Nodes';
import { NodePalette } from './components/Layout/NodePalette';
import { ValidationBar } from './components/Layout/ValidationBar';
import { PropertiesPanel } from './components/Layout/PropertiesPanel';
import { useWorkflowStore } from './stores/workflowStore';
import { useToolCatalogueStore } from './stores/toolCatalogueStore';
import { useModelsStore } from './stores/modelsStore';

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
  const catalogueError = useToolCatalogueStore(s => s.error);
  const revalidate = useWorkflowStore(s => s.revalidate);
  const fetchCatalogue = useToolCatalogueStore(s => s.fetchCatalogue);
  const fetchAgentsAction = useToolCatalogueStore(s => s.fetchAgents);
  const fetchModels = useModelsStore(s => s.fetchModels);

  useEffect(() => {
    void fetchCatalogue();
    void fetchAgentsAction();
    void fetchModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (catalogueError) toast.error(`Catalogue: ${catalogueError}`);
  }, [catalogueError]);

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
    <div className="h-[calc(100vh-3rem)] w-screen flex flex-col">
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
