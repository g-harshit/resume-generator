"""lock tables away from a hosted database's public API

Supabase serves the `public` schema over HTTP (PostgREST) to anyone holding the
project's anon key, which is public by design. Nothing here is meant to be reached
that way: every read and write goes through our API. So:

- row-level security on every table, with no policies: roles that aren't the owner
  see nothing. The app connects as the owner, which RLS doesn't restrict.
- where Supabase's `anon` and `authenticated` roles exist, no privileges for them on
  our tables and sequences, now or for tables made later.

On plain Postgres (development, tests) only the first applies, and changes nothing
for the app.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_API_ROLES = ("anon", "authenticated")


def _tables() -> list[str]:
    rows = op.get_bind().execute(
        sa.text("select tablename from pg_tables where schemaname = 'public'")
    )
    return [r[0] for r in rows]


def _api_roles() -> list[str]:
    rows = op.get_bind().execute(
        sa.text("select rolname from pg_roles where rolname = any(:names)"),
        {"names": list(_API_ROLES)},
    )
    return [r[0] for r in rows]


def upgrade() -> None:
    for table in _tables():
        op.execute(f'alter table public."{table}" enable row level security')
    roles = ", ".join(_api_roles())
    if roles:
        op.execute(f"revoke all on all tables in schema public from {roles}")
        op.execute(f"revoke all on all sequences in schema public from {roles}")
        op.execute(f"alter default privileges in schema public revoke all on tables from {roles}")
        op.execute(
            f"alter default privileges in schema public revoke all on sequences from {roles}"
        )


def downgrade() -> None:
    # Privileges aren't handed back: nothing should reach these tables that way.
    for table in _tables():
        op.execute(f'alter table public."{table}" disable row level security')
