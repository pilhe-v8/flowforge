#!/usr/bin/env markdown
# Tool Gateway Enforcement Design

**Goal:** Ensure ALL tool invocations in FlowForge (including output actions like `log`) are mediated by the standalone Tool Gateway service. Eliminate in-process direct calls to tool endpoints.

## Context

Current execution path compiles workflow YAML into node callables using `flowforge.compiler.NodeFactory`. Tool execution is currently performed in-process via `flowforge.tools.executor.ToolExecutor`, which routes URIs by scheme:

- `mcp://...` via `flowforge.tools.mcp_client.MCPToolClient`
- `http(s)://...` via `flowforge.tools.http_client.HTTPToolClient`

Worker runtime wires dependencies in `flowforge.worker.graph_cache._get_runtime_deps()` by constructing `ToolExecutor(MCPToolClient(), HTTPToolClient())`.

Separately, a new standalone service `flowforge.tool_gateway` exposes an auth-gated synchronous endpoint:

- `POST /v1/tool-calls:invoke` (JWT required)

## Decision

Enforcement is implemented by making `ToolExecutor` gateway-backed, so all existing call sites automatically route through the gateway.

Additionally, `output` steps must not bypass tool execution (previously `action_uri == "log"` was handled locally). With enforcement, output actions including `log` are treated as tools and dispatched via the gateway.

## Architecture

### Components

1) **Tool Gateway** (already exists)

- FastAPI service listening on port `8010`
- Verifies HS256 JWTs
- Dispatches tool calls synchronously (MCP or HTTP) and returns JSON

2) **Gateway client** (new)

- A lightweight client inside the main backend that calls the Tool Gateway `POST /v1/tool-calls:invoke`
- Adds `Authorization: Bearer <service_jwt>`
- Sends `{ tool_uri, inputs, context }`

3) **ToolExecutor (gateway-backed)** (modify)

- Replace in-process routing (MCP/HTTP) with a single gateway dispatch call
- Treat the tool gateway as the only tool execution backend

4) **NodeFactory output action enforcement** (modify)

- Remove the local built-in bypass for `action_uri == "log"`
- Always call `tool_executor.execute(step.action_uri, inputs)` for output steps

### Data flow

1) Workflow node wants to execute a tool action (`step.tool_uri` or `step.action_uri`).
2) Node calls `ToolExecutor.execute(tool_uri, inputs, auth?)`.
3) ToolExecutor calls Tool Gateway:

   - `POST <tool_gateway_url>/v1/tool-calls:invoke`
   - JSON body: `{ "tool_uri": "...", "inputs": { ... }, "context": { ... } }`
   - `Authorization: Bearer <tool_gateway_jwt>`

4) Tool Gateway verifies JWT and dispatches tool call to MCP/HTTP tool.
5) Tool Gateway returns `{status, tool_call_id, output}`.
6) ToolExecutor returns the `output` dict to the node.

### Configuration

Add settings in `flowforge.config.Settings` (names TBD by implementation):

- `tool_gateway_url`: string, default `http://tool-gateway:8010`
- `tool_gateway_jwt`: string, required in non-dev (service token)

These settings are used by the gateway client / ToolExecutor.

### Authentication model

For the MVP, the worker/backend authenticates to the Tool Gateway with a pre-shared HS256 JWT (service token). The gateway only needs to validate signature/expiry.

Future enhancement: propagate end-user/tenant context in `context` and enforce authorization per tenant at the gateway.

## Error handling

- Tool Gateway returns:
  - `400` for invalid tool URI / bad input
  - `401` for missing/invalid JWT
  - `502` for upstream tool failures
- ToolExecutor should raise a clear exception on:
  - missing gateway URL/JWT configuration
  - non-2xx responses from gateway (include status code and gateway detail where safe)

## Testing

Unit tests in main backend should verify:

- Tool steps call the gateway client (not MCP/HTTP clients)
- Output steps, including `action_uri == "log"`, also call the gateway client
- Fail-closed behavior when gateway config is missing

Tool Gateway tests already cover:

- `401` on missing/invalid token
- successful synchronous dispatch via dependency override executor

## Rollout / migration notes

- Docker compose must include the `tool-gateway` service for local and containerized environments.
- Tool Gateway URL must be resolvable from worker/backend containers.
- Until tool registration includes a `log` tool, enforcing output `log` through gateway will require either:
  - treating `log` as a special tool URI handled by the gateway itself, or
  - ensuring there is a registered tool for it.

## Non-goals (for this milestone)

- Async/queued tool calls
- HITL approvals
- Multi-tenant authorization policies at the gateway
- Persistent tool call audit storage in gateway
