export { TriggerNode } from './TriggerNode';
export { ToolNode } from './ToolNode';
export { AgentNode } from './AgentNode';
export { RouterNode } from './RouterNode';
export { GateNode } from './GateNode';
export { OutputNode } from './OutputNode';

import { TriggerNode } from './TriggerNode';
import { ToolNode } from './ToolNode';
import { AgentNode } from './AgentNode';
import { RouterNode } from './RouterNode';
import { GateNode } from './GateNode';
import { OutputNode } from './OutputNode';

export const nodeTypes = {
  trigger: TriggerNode,
  tool: ToolNode,
  agent: AgentNode,
  router: RouterNode,
  gate: GateNode,
  output: OutputNode,
};
