# 02 - Workflow YAML Schema Reference

## Overview

The YAML workflow definition is the source of truth for every workflow. It is produced
by the visual builder and consumed by the compiler. Users never edit it manually, but
it must be human-readable for debugging and version control.

## Top-Level Structure

```yaml
workflow:
  name: string                    # Human-readable name
  slug: string                    # URL-safe identifier (auto-generated)
  version: integer                # Auto-incremented on each save
  description: string             # Optional
  tenant_id: string               # Owner tenant

  trigger:
    type: enum                    # email_received | webhook | schedule | manual
    config: object                # Type-specific config
    output: list[string]          # Variable names this trigger produces

  steps: list[StepDefinition]     # Ordered list of workflow steps
```

## Trigger Types

### email_received
```yaml
trigger:
  type: email_received
  config:
    mailbox: "support@acme.com"
    filter:
      subject_contains: "urgent"  # optional
  output: [sender, subject, body, attachments, received_at]
```

### webhook
```yaml
trigger:
  type: webhook
  config:
    path: "/incoming/customer-service"
    method: POST
    auth: bearer_token            # none | bearer_token | api_key
  output: [payload]
```

### schedule
```yaml
trigger:
  type: schedule
  config:
    cron: "0 9 * * MON-FRI"
  output: [triggered_at]
```

### manual
```yaml
trigger:
  type: manual
  config: {}
  output: [input_data]
```

## Step Definition (Common Fields)

```yaml
- id: string                      # Unique within workflow, URL-safe
  name: string                    # Human-readable label
  type: enum                      # tool | agent | router | gate | deterministic | output
```

## Step Types

### tool
Calls an external tool via MCP, HTTP, or gRPC. No LLM involved.
```yaml
- id: lookup_customer
  name: Look Up Customer
  type: tool
  tool: "mcp://crm-service/customer-lookup"
  input:
    email: "{{trigger.sender}}"
  output: [customer_id, name, tier, past_tickets]
  next: sentiment
```

### tool-with-fallback
```yaml
- id: classify
  name: Classify Intent
  type: tool
  tool: "mcp://ml-services/intent-classifier"
  input:
    text: "{{trigger.body}}"
  output: [intent, intent_confidence]
  fallback:
    when: "intent_confidence < 0.85"
    agent: classifier-agent
    input:
      text: "{{trigger.body}}"
    output: [intent]
  next: route
```

### agent
Calls an LLM using an agent profile.
```yaml
- id: tech_diagnosis
  name: Technical Diagnosis
  type: agent
  agent: tech-support
  model: "gpt-4o"                 # optional model override
  context:
    issue: "{{trigger.body}}"
    customer_name: "{{lookup_customer.name}}"
    tier: "{{lookup_customer.tier}}"
    history: "{{lookup_customer.past_tickets}}"
  output: [resolution]
  next: draft_reply
```

### router
Branches the flow based on a variable value. Pure logic, no LLM.
```yaml
- id: route
  name: Route by Intent
  type: router
  on: "{{classify.intent}}"
  routes:
    password_reset: handle_password
    order_status: lookup_order
    billing: fetch_invoice
    technical: tech_diagnosis
    complaint: escalate
  default: general_response
```

### gate
Evaluates rules to decide the next step. Can loop back for retries.
```yaml
- id: quality_gate
  name: Quality Gate
  type: gate
  rules:
    - if: "len(draft_response) < 20"
      then: draft_reply
      label: "Response too short"
    - if: "tier == 'enterprise' and sentiment == 'angry'"
      then: escalate
      label: "VIP escalation"
  default: send_reply
```

### Gate Rule Expression Language
Restricted expression language (not arbitrary Python):
| Operator        | Example                                       |
|-----------------|-----------------------------------------------|
| ==, !=          | tier == 'enterprise'                          |
| <, >, <=, >=    | intent_confidence < 0.85                      |
| and, or, not    | tier == 'enterprise' and sentiment == 'angry' |
| in              | intent in ['billing', 'refund']               |
| contains()      | contains(body, 'urgent')                      |
| len()           | len(draft_response) < 20                      |
| is_empty()      | is_empty(resolution)                          |
| starts_with()   | starts_with(subject, 'Re:')                   |

### deterministic
Runs a built-in operation with no external calls.
```yaml
- id: fill_template
  name: Fill Password Reset Template
  type: deterministic
  operation: render_template
  template: password_reset
  template_vars:
    name: "{{lookup_customer.name}}"
    reset_link: "{{handle_password.reset_link}}"
  output: [draft_response]
  next: quality_gate
```

Built-in operations:
| Operation        | Description                              |
|------------------|------------------------------------------|
| parse_email      | Extract sender, subject, body from raw   |
| render_template  | Render a Jinja2 template with variables  |
| format_text      | Simple string formatting / concatenation |
| merge_objects    | Combine multiple variables into one      |
| extract_field    | Pull a nested field from a JSON object   |
| timestamp        | Generate current timestamp               |

### output
Terminal node. Performs a final action and ends the workflow.
```yaml
- id: send_reply
  name: Send Reply
  type: output
  action: "mcp://email-service/send"
  input:
    to: "{{trigger.sender}}"
    subject: "Re: {{trigger.subject}}"
    body: "{{draft_response}}"
```

## Variable Reference Syntax

All references use {{step_id.variable_name}}:
- {{trigger.sender}} - output from the trigger
- {{lookup_customer.name}} - output from step with id lookup_customer

Rules:
1. A variable {{X.Y}} is only available if step X is upstream in the graph
2. Router/gate nodes do not produce variables; they only route
3. The compiler validates all references at compile time
4. At runtime, missing variables resolve to null

## JSON Schema

The full JSON Schema for validation is at backend/flowforge/compiler/schema.json.
Key constraints:
- workflow.name: string, 1-200 chars
- workflow.slug: string, pattern ^[a-z0-9-]+$
- step.id: string, pattern ^[a-z0-9_]+$
- step.type: enum [tool, agent, router, gate, deterministic, output]
- trigger.type: enum [email_received, webhook, schedule, manual]
- steps: array, minItems 1
