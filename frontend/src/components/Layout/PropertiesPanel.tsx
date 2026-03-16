import { useWorkflowStore } from '../../stores/workflowStore';
import { TriggerPanel } from '../Panels/TriggerPanel';
import { ToolPanel } from '../Panels/ToolPanel';
import { AgentPanel } from '../Panels/AgentPanel';
import { RouterPanel } from '../Panels/RouterPanel';
import { GatePanel } from '../Panels/GatePanel';
import { OutputPanel } from '../Panels/OutputPanel';
import { DefinitionDrawer } from '../shared/DefinitionDrawer';

export function PropertiesPanel() {
  const selectedNodeId = useWorkflowStore(s => s.selectedNodeId);
  const nodes = useWorkflowStore(s => s.nodes);
  const removeNode = useWorkflowStore(s => s.removeNode);

  const selectedNode = selectedNodeId ? nodes.find(n => n.id === selectedNodeId) : undefined;

  let panelContent: React.ReactNode;

  if (!selectedNodeId) {
    panelContent = (
      <div className="p-4 text-gray-400 text-sm">Select a node to configure it</div>
    );
  } else {
    if (!selectedNode) {
      panelContent = null;
    } else {
      switch (selectedNode.type) {
        case 'trigger': panelContent = <TriggerPanel nodeId={selectedNodeId} />; break;
        case 'tool':    panelContent = <ToolPanel nodeId={selectedNodeId} />; break;
        case 'agent':   panelContent = <AgentPanel nodeId={selectedNodeId} />; break;
        case 'router':  panelContent = <RouterPanel nodeId={selectedNodeId} />; break;
        case 'gate':    panelContent = <GatePanel nodeId={selectedNodeId} />; break;
        case 'output':  panelContent = <OutputPanel nodeId={selectedNodeId} />; break;
        default:        panelContent = <div className="p-4 text-sm text-gray-500">Unknown node type</div>;
      }
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        {panelContent}
      </div>
      {selectedNode && selectedNode.type && <DefinitionDrawer nodeType={selectedNode.type} />}
      {selectedNodeId && (
        <div className="border-t border-gray-200 p-3 mt-2">
          <button
            onClick={() => removeNode(selectedNodeId)}
            className="w-full text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded px-3 py-1.5 border border-red-200"
          >
            Delete node
          </button>
        </div>
      )}
    </div>
  );
}
