export interface FieldDef {
  name: string;
  description: string;
  example: string;
  required: boolean;
}

export interface NodeDef {
  type: string;
  icon: string;
  title: string;
  summary: string;
  fields: FieldDef[];
}

export const NODE_DEFINITIONS: Record<string, NodeDef> = {
  trigger: {
    type: 'trigger',
    icon: '⚡',
    title: 'Trigger',
    summary: 'The workflow entry point. Defines what event starts the workflow and what data it provides to subsequent steps.',
    fields: [
      { name: 'type', description: 'The event type that starts this workflow', example: 'manual | webhook | email_received | schedule', required: true },
      { name: 'output', description: 'Variable names this trigger makes available to later steps', example: '[message, sender, body]', required: true },
    ],
  },
  tool: {
    type: 'tool',
    icon: '🔧',
    title: 'Tool',
    summary: 'Calls an external tool — either an MCP server (mcp://) or an HTTP endpoint (http://). The tool runs synchronously and its output becomes available to later steps.',
    fields: [
      { name: 'tool', description: 'URI of the tool to call', example: 'mcp://crm-service:9000/customer-lookup', required: true },
      { name: 'input.*', description: 'Variables to pass to the tool. Use {{step_id.var}} to reference previous step outputs.', example: 'email: "{{trigger.sender}}"', required: false },
      { name: 'output', description: 'Variable names returned by the tool', example: '[customer_id, name, tier]', required: true },
      { name: 'fallback', description: 'If the tool result fails a condition, run an agent instead', example: 'when: "confidence < 0.85"', required: false },
    ],
  },
  agent: {
    type: 'agent',
    icon: '🧠',
    title: 'Agent',
    summary: "Runs an LLM-powered agent from your agent profile library. The agent receives context variables and returns one or more output variables containing the LLM's response.",
    fields: [
      { name: 'agent', description: 'Slug of the agent profile to use', example: 'reply-drafter', required: true },
      { name: 'model', description: "Override the agent's default LLM model", example: 'gpt-4o-mini | mistral-large-latest', required: false },
      { name: 'context.*', description: 'Variables passed as context to the LLM prompt', example: 'message: "{{trigger.body}}"', required: false },
      { name: 'output', description: 'Variable names the agent produces', example: '[reply, summary]', required: true },
    ],
  },
  router: {
    type: 'router',
    icon: '◆',
    title: 'Router',
    summary: 'Branches the workflow based on the value of a variable. Routes traffic to different steps based on exact string matches, with a default fallback.',
    fields: [
      { name: 'on', description: 'The variable value to switch on', example: '{{classify.intent}}', required: true },
      { name: 'routes.*', description: 'Map of value → next step ID', example: 'billing: fetch_invoice', required: true },
      { name: 'default', description: 'Step to go to if no route matches', example: 'general_response', required: false },
    ],
  },
  gate: {
    type: 'gate',
    icon: '🛡',
    title: 'Gate',
    summary: "Evaluates a list of boolean rules against the current workflow state. Routes to the first matching rule's target step, or to the default if none match.",
    fields: [
      { name: 'rules[].if', description: 'Boolean Python expression evaluated against current state', example: 'len(draft_response) < 20', required: true },
      { name: 'rules[].then', description: 'Step ID to route to when this rule matches', example: 'draft_reply', required: true },
      { name: 'rules[].label', description: 'Human-readable label for this rule', example: 'Response too short', required: false },
      { name: 'default', description: 'Step ID if no rules match', example: 'send_reply', required: true },
    ],
  },
  output: {
    type: 'output',
    icon: '📤',
    title: 'Output',
    summary: 'The workflow terminal node. Calls an external action (MCP tool or HTTP endpoint) to deliver the final result — for example sending an email or creating a ticket.',
    fields: [
      { name: 'action', description: 'URI of the action to execute', example: 'mcp://email-service:9006/send', required: true },
      { name: 'input.*', description: 'Data to pass to the action', example: 'to: "{{trigger.sender}}"', required: false },
    ],
  },
};
