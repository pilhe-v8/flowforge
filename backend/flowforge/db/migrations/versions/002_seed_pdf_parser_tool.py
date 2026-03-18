"""Seed pdf-parser tool registration for default tenant

Revision ID: 002
Revises: 001
Create Date: 2025-03-16
"""

import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

_PDF_PARSER_TOOL = {
    "slug": "pdf-parser",
    "name": "PDF Parser",
    "uri": "http://pdf-parser:8100",
    "protocol": "http",
    "description": "Extracts text from a PDF given its URL",
    "input_schema": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "PDF URL"}},
        "required": ["url"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "pages": {"type": "integer"},
            "chars": {"type": "integer"},
        },
    },
}


def upgrade() -> None:
    conn = op.get_bind()

    # Fetch all tenant IDs so we register the tool for every existing tenant.
    # In a fresh dev stack there is typically one tenant ("default").
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:
        # Upsert: skip if already registered for this tenant
        existing = conn.execute(
            sa.text("SELECT id FROM tool_registrations WHERE tenant_id = :tid AND slug = :slug"),
            {"tid": tenant_id, "slug": _PDF_PARSER_TOOL["slug"]},
        ).fetchone()

        if existing is None:
            conn.execute(
                sa.text(
                    "INSERT INTO tool_registrations "
                    "(id, tenant_id, slug, name, protocol, endpoint, description, "
                    " input_schema, output_schema, is_active, created_at) "
                    "VALUES ("
                    "  gen_random_uuid(), :tid, :slug, :name, :protocol, :endpoint, "
                    "  :description, CAST(:input_schema AS jsonb), CAST(:output_schema AS jsonb), "
                    "  true, now()"
                    ")"
                ),
                {
                    "tid": tenant_id,
                    "slug": _PDF_PARSER_TOOL["slug"],
                    "name": _PDF_PARSER_TOOL["name"],
                    "protocol": _PDF_PARSER_TOOL["protocol"],
                    "endpoint": _PDF_PARSER_TOOL["uri"],
                    "description": _PDF_PARSER_TOOL["description"],
                    "input_schema": json.dumps(_PDF_PARSER_TOOL["input_schema"]),
                    "output_schema": json.dumps(_PDF_PARSER_TOOL["output_schema"]),
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM tool_registrations WHERE slug = :slug"),
        {"slug": _PDF_PARSER_TOOL["slug"]},
    )
