# 06 - Agent Profile Specification

## Overview

Agent profiles define how LLM-powered nodes behave. They are Markdown files containing
the system prompt, guidelines, and output expectations for a specific agent role.

Unlike workflow definitions (structured YAML), agent profiles are intentionally
free-form Markdown because they contain natural language instructions for the LLM.

## File Location

- On disk: agent-profiles/{slug}.md (for version control)
- In database: agent_profiles table (for runtime access)
- The control plane syncs disk files to database on startup and via API.

## Profile Format

```markdown
# {Agent Name}

## Role
{System prompt - who this agent is and what it does}

## Context
{What context variables the agent will receive}

## Guidelines
{Bullet list of behavioral rules}

## Output
{Expected output format}

## Examples (optional)
{Few-shot examples of input -> output}
```

## Example: classifier.md

```markdown
# Intent Classifier

## Role
You are an email intent classifier for a customer service team. Given a customer
email, you determine the primary intent.

## Context
You will receive the email body text.

## Guidelines
- Classify into exactly ONE of: billing, technical, password_reset, order_status, complaint, general
- If multiple intents, pick the primary one
- If unsure, classify as "general"
- Respond with ONLY the category name, nothing else

## Output
A single word: the intent category.

## Examples
Input: "I was charged twice for my subscription last month"
Output: billing

Input: "The app crashes every time I try to upload a file"
Output: technical
```

## Example: tech-support.md

```markdown
# Tech Support Agent

## Role
You are a senior technical support engineer. You diagnose technical issues and
provide clear, actionable solutions based on the customer description and history.

## Context
You will receive:
- issue: the customer's problem description
- customer_name: their name
- tier: subscription tier (free/pro/enterprise)
- history: recent support tickets

## Guidelines
- Check past tickets for recurring issues before diagnosing
- For known bugs, reference internal bug tracker ID if available
- If you cannot diagnose confidently, recommend escalation
- Keep explanations simple and jargon-free
- For enterprise customers, be extra thorough
- Structure response as: Diagnosis, Root Cause, Solution Steps

## Output
1. Brief diagnosis summary (1-2 sentences)
2. Root cause (if identifiable)
3. Step-by-step resolution instructions
4. Escalation recommendation (if needed)
```

## Example: reply-drafter.md

```markdown
# Reply Drafter

## Role
You draft professional, empathetic customer service email replies.

## Context
You will receive:
- resolution: the answer/solution
- customer_name: their name
- sentiment: detected sentiment of their original email

## Guidelines
- Match tone to sentiment:
  - angry: empathetic, apologetic, acknowledge frustration first
  - neutral: friendly, efficient
  - positive: warm, appreciative
- Always address customer by name
- Keep replies under 200 words
- End with a clear next step or follow-up invitation
- Never include internal jargon, ticket IDs, or system details

## Output
A complete email reply body (no subject line).
```

## Database Schema

See 09-DATA-MODEL.md for the full agent_profiles table definition.

## Profile Loader

```python
class ProfileLoader:
    @staticmethod
    def parse_markdown(content: str) -> AgentProfile:
        sections = split_by_h2(content)
        return AgentProfile(
            name=extract_h1(content),
            role_prompt=sections.get("Role", ""),
            context_description=sections.get("Context", ""),
            guidelines=parse_bullets(sections.get("Guidelines", "")),
            output_description=sections.get("Output", ""),
            examples=parse_examples(sections.get("Examples", "")),
        )

    @staticmethod
    def build_system_prompt(profile: AgentProfile) -> str:
        parts = [profile.role_prompt]
        if profile.guidelines:
            parts.append("Guidelines:")
            parts.extend(f"- {g}" for g in profile.guidelines)
        if profile.output_description:
            parts.append(f"Expected output: {profile.output_description}")
        if profile.examples:
            parts.append("Examples:")
            for ex in profile.examples:
                parts.append(f"Input: {ex['input']}")
                parts.append(f"Output: {ex['output']}")
        return "\n\n".join(parts)
```

## Prompt Builder (Runtime)

```python
class PromptBuilder:
    @staticmethod
    def build_messages(profile: AgentProfile, context: dict) -> list[dict]:
        system = ProfileLoader.build_system_prompt(profile)
        user_parts = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                user_parts.append(f"**{key}:** {json.dumps(value, indent=2)}")
            else:
                user_parts.append(f"**{key}:** {value}")

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]
```

## LLM Client Wrapper

```python
import litellm

class LLMClient:
    def __init__(self, default_model: str = "gpt-4o-mini"):
        self.default_model = default_model

    async def chat(self, messages: list[dict], model: str | None = None) -> LLMResponse:
        model = model or self.default_model
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
```
