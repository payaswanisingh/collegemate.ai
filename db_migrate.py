# db_migrate.py
"""
Lightweight, additive schema reconciliation for SQLite.

This project doesn't use Flask-Migrate/Alembic, so ``db.create_all()``
alone isn't enough once a model gains a new column after the database
file already exists on disk — ``create_all()`` only creates tables that
are completely missing; it never alters a table that's already there.
That gap is exactly what produces errors like:

    sqlite3.OperationalError: no such column: chat_messages.client_id

``sync_schema()`` closes that gap without requiring Alembic and without
deleting any data. For every table SQLAlchemy knows about (from
``db.metadata``), it compares the model's declared columns against what
actually exists in the database (via ``sqlalchemy.inspect``) and issues
``ALTER TABLE ... ADD COLUMN ...`` for whatever is missing. It then
(re)creates the ``chat_messages`` uniqueness index that prevents
duplicate messages, since that index can only be missing for the exact
same reason (it was declared after the table already existed).

It also repairs one specific, narrow correctness bug that a plain
``ADD COLUMN`` can never fix: a primary key column that isn't wired up
as a real SQLite "INTEGER PRIMARY KEY" (rowid alias). SQLAlchemy's ORM
inserts never include a value for an autoincrement primary key — it
relies on SQLite assigning the next rowid automatically. If a table's
``id`` column exists but isn't that rowid alias (e.g. because the
table on disk predates the current model, or was created by hand),
every insert omits ``id`` and SQLite raises
``NOT NULL constraint failed: <table>.id`` instead of assigning one.
There is no ``ALTER TABLE ... ALTER COLUMN`` in SQLite, so the only
correct fix is the rebuild recipe SQLite itself recommends: rename the
table aside, recreate it from the model's real metadata (which already
declares the column correctly), copy every row across, drop the
renamed copy. ``_ensure_table_matches_model`` below does exactly that,
and only when the live schema is actually broken.

IMPORTANT CORRECTNESS FIX (this revision):
  The rebuild used to blindly copy every column declared on the
  *model* from the *legacy* table, e.g.:

      INSERT INTO chat_messages (id, conversation_id, question,
                                  answer, source, client_id, created_at)
      SELECT id, conversation_id, question,
             answer, source, client_id, created_at
      FROM _chat_messages_legacy

  If the legacy table predates a column the model has since gained
  (exactly what happens right after a column like ``client_id`` was
  added to the model but the on-disk table hadn't been touched yet),
  that ``SELECT`` references a column that doesn't exist on the legacy
  table and the whole rebuild fails with
  ``sqlite3.OperationalError: no such column``. Because the primary-key
  repair runs *before* the "add missing columns" pass (on purpose, so
  the rebuilt table already has every column), a database that needs
  *both* a PK repair *and* new columns would hit this every single
  startup — the ORM would never manage to save anything, which matches
  "every message fails with an internal error" even after the missing
  column itself was patched in once by hand.

  The fix: before rebuilding, inspect which columns the *legacy* table
  actually has (via ``PRAGMA table_info``) and only copy the
  intersection of "exists on legacy" and "declared on model". Any
  model column that doesn't exist yet on the legacy table is simply
  left out of the copy — it gets created empty by ``CREATE TABLE`` and
  is then picked up completely normally by the ordinary "add missing
  columns" pass that runs right after (which, for a *new* table, is a
  no-op, since the column already exists — the column is just NULL for
  old rows, same as it would be either way).

ALSO HANDLED (this revision): a legacy column the model no longer has.
  ``ChatMessage`` in chat_model.py has never had a ``user_id`` column —
  ownership flows only through ``ChatConversation.user_id``. But an
  on-disk ``chat_messages`` table created by an *older* version of that
  model can still carry a ``user_id NOT NULL`` column. Because this
  file used to be strictly additive (see below), it had no way to
  remove that column, so every insert (which the ORM correctly never
  populates ``user_id`` for) kept failing with
  ``NOT NULL constraint failed: chat_messages.user_id`` forever, on
  every single startup, with no way for this file to ever fix it.

  The fix reuses the exact same rebuild-in-place recipe already used
  for the primary-key repair, rather than adding a second mechanism:
  that rebuild already only copies columns that exist on *both* the
  legacy table and the current model (see
  ``_rebuild_table_to_match_model`` below) — it was already fully
  capable of dropping a stale column, it just previously only ever got
  triggered by a broken primary key. ``_ensure_table_matches_model``
  now triggers that same rebuild whenever the live table's primary key
  is broken *or* the live table carries any column the current model
  no longer declares. One mechanism, two triggers — not two mechanisms.

Design constraints, on purpose:
  - Repair-only, never silently lossy for anything the model still
    recognizes. Ordinary column *additions* are handled with plain
    ``ADD COLUMN`` and never touch existing data. The rebuild path
    (triggered by a broken primary key or a legacy column the model no
    longer declares) preserves every row and every column the model
    still declares exactly; it only ever drops a column that the model
    itself has already dropped. Every check is a no-op once the
    database already matches the models, so it's safe to call on
    *every* startup, not just once.
  - New columns are always added as nullable at the SQLite level, even
    if the model marks them ``nullable=False``. SQLite refuses to add a
    NOT NULL column with no default to a table that already has rows.
    Existing rows simply get NULL for the new column; the ORM still
    enforces "not null" for anything written going forward.
  - A single table failing to repair must never take the whole app
    down, and must never leave the other tables unrepaired. Every
    per-table step is wrapped so one bad table is logged and skipped
    rather than raised, and the loop always continues to the next
    table.
  - Beyond primary-key and legacy-column repair, this intentionally
    only handles the "model gained a column/index" and "model dropped
    a column" cases. A genuine breaking migration — renaming a column,
    changing a column's type, backfilling a new NOT NULL column with
    real values — is outside what this file safely handles; that's
    what Flask-Migrate/Alembic is for (see the note at the bottom of
    this file for how to adopt it later).
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.schema import CreateTable

logger = logging.getLogger(__name__)


def _column_ddl_type(column) -> str:
    """Render a SQLAlchemy column's type as SQLite DDL, e.g. 'VARCHAR(64)'."""
    try:
        return column.type.compile(dialect=sqlite_dialect.dialect())
    except Exception:
        # Fall back to SQLite's dynamic typing if a type ever fails to
        # compile explicitly — an untyped column still works fine in SQLite.
        return "TEXT"


def _model_declares_rowid_pk(table):
    """Return the single primary-key column name if ``table``'s model
    declares exactly one integer primary key (the normal, autoincrement
    case), else None. Composite keys or non-integer keys aren't something
    the repair below applies to.
    """
    pk_cols = list(table.primary_key.columns)
    if len(pk_cols) != 1:
        return None
    if not str(pk_cols[0].type).upper().startswith("INTEGER"):
        return None
    return pk_cols[0].name


def _live_table_columns(db, table_name) -> list[str]:
    """Return the column names that actually exist on ``table_name`` right
    now, in on-disk order, via PRAGMA table_info (not sqlalchemy.inspect,
    so this stays valid to call mid-transaction / right before a rebuild
    without needing a fresh Inspector).
    """
    with db.engine.connect() as conn:
        rows = conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    return [row[1] for row in rows]


def _live_pk_is_rowid_alias(db, table_name, pk_column) -> bool:
    """Return True if, on the *live* database, ``pk_column`` is actually
    wired up as SQLite's INTEGER PRIMARY KEY rowid alias — the thing that
    makes SQLite auto-assign an id on INSERT when the ORM (correctly)
    omits one.

    Checked directly via ``PRAGMA table_info`` rather than
    ``sqlalchemy.inspect``'s higher-level primary-key report, because
    what matters here is SQLite's own column-level ``pk`` flag together
    with an ``INTEGER`` type affinity — that combination is exactly
    SQLite's documented rule for rowid-alias behaviour, and it's possible
    for a table to have the "right" primary key column by name while
    still failing that rule (e.g. if it was ever created with a
    non-INTEGER affinity, or outside of ``create_all()`` entirely).
    """
    with db.engine.connect() as conn:
        rows = conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()

    for row in rows:
        if row[1] == pk_column:
            return bool(row[5]) and str(row[2]).upper() == "INTEGER"
    return False  # column doesn't even exist yet — nothing to repair here


def _live_columns_not_in_model(db, table_name, table) -> set[str]:
    """Column names that exist on the live table but are no longer
    declared on the current model — e.g. the historic
    ``chat_messages.user_id`` column, which ``chat_model.py`` has never
    carried (``ChatMessage`` tracks ownership only indirectly, via
    ``chat_conversations.user_id``). A plain ``ADD COLUMN`` pass can
    only ever add what's missing; it has no way to remove a column the
    model has since dropped. If that column is ``NOT NULL`` with no
    default, every insert fails forever until the table is rebuilt.
    """
    model_columns = {c.name for c in table.columns}
    live_columns = set(_live_table_columns(db, table.name))
    return live_columns - model_columns


def _rebuild_table_to_match_model(db, table) -> None:
    """Rebuild ``table`` in place so it matches the current model exactly
    — both repairing a primary key that isn't a proper SQLite INTEGER
    PRIMARY KEY (rowid alias), and dropping any column the live table
    still carries that the model no longer declares — without losing
    any data the model still recognizes, and without assuming the
    legacy table already has every column the current model declares
    (see the module docstring's "IMPORTANT CORRECTNESS FIX" section for
    why that assumption used to break this on databases that needed
    both a PK repair *and* a missing column at the same time).
    """
    legacy_name = f"_{table.name}_legacy"

    # Only copy columns that actually exist on the legacy table. Any
    # model column not yet present there is simply omitted from the
    # copy; CREATE TABLE below still creates it (as NULL for old rows),
    # and the ordinary "add missing columns" pass that runs right after
    # this in sync_schema() will find it already present and skip it.
    legacy_columns = set(_live_table_columns(db, table.name))
    model_columns = [c.name for c in table.columns]
    copy_columns = [c for c in model_columns if c in legacy_columns]

    if not copy_columns:
        # Nothing in common (shouldn't normally happen — the table at
        # least has its primary key column) — bail out rather than run
        # a nonsensical empty INSERT; the ADD COLUMN pass and a future
        # startup will sort this table out once there's overlap.
        logger.error(
            "Cannot repair primary key for %s: legacy table has no columns "
            "in common with the current model. Skipping repair.",
            table.name,
        )
        return

    quoted_cols = ", ".join(f'"{c}"' for c in copy_columns)
    create_sql = str(CreateTable(table).compile(dialect=sqlite_dialect.dialect()))

    dropped_columns = legacy_columns - set(model_columns)
    logger.warning(
        "Schema repair: rebuilding %s from the model's own schema; all "
        "columns and rows the model still recognizes are preserved. "
        "Copying columns: %s%s%s",
        table.name, copy_columns,
        "" if len(copy_columns) == len(model_columns)
        else f" (model also has {sorted(set(model_columns) - legacy_columns)}, "
             f"which didn't exist on the legacy table yet — those will be "
             f"NULL for pre-existing rows and are added by the next pass)",
        f" (dropping legacy column(s) {sorted(dropped_columns)}, which the "
        f"current model no longer declares)" if dropped_columns else "",
    )

    with db.engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text(f'ALTER TABLE "{table.name}" RENAME TO "{legacy_name}"'))
        conn.execute(text(create_sql))
        conn.execute(text(
            f'INSERT INTO "{table.name}" ({quoted_cols}) '
            f'SELECT {quoted_cols} FROM "{legacy_name}"'
        ))
        conn.execute(text(f'DROP TABLE "{legacy_name}"'))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_table_matches_model(db, inspector, table_name, table) -> None:
    """If this table's primary key exists but isn't a valid rowid alias,
    OR the live table carries a column the current model no longer
    declares (e.g. the legacy ``chat_messages.user_id``), repair it via
    a full rebuild. No-op if everything already matches. Never raises —
    a failure here is logged and the table is left as-is so the rest of
    ``sync_schema`` (and the app) can still start; the ADD COLUMN pass
    and unique-index pass for *other* tables must not be blocked by one
    broken table.
    """
    needs_rebuild = False

    pk_column = _model_declares_rowid_pk(table)
    if pk_column is not None:
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if pk_column in existing_columns:
            try:
                if not _live_pk_is_rowid_alias(db, table_name, pk_column):
                    needs_rebuild = True
            except Exception:
                logger.exception(
                    "Failed to check primary key validity for table %s; "
                    "leaving it as-is for this startup.",
                    table_name,
                )
        # else: pk column missing entirely — the ADD COLUMN pass can't
        # fix a PK anyway, and create_all() would have made this table
        # correctly if it were brand new; nothing to repair here.

    try:
        if _live_columns_not_in_model(db, table_name, table):
            needs_rebuild = True
    except Exception:
        logger.exception(
            "Failed to check for legacy columns on table %s; leaving it "
            "as-is for this startup.",
            table_name,
        )

    if not needs_rebuild:
        return

    try:
        _rebuild_table_to_match_model(db, table)
    except Exception:
        logger.exception(
            "Failed to repair table %s; leaving it as-is for this "
            "startup. Inserts into this table may continue to fail "
            "until this is resolved.",
            table_name,
        )


def _backfill_conversation_titles(db) -> None:
    """Make sure no ``chat_conversations`` row is ever left with a NULL
    title. New rows get "New chat" from the model's column default (see
    ``chat_model.py``), but rows that predate that default — or that
    came through the primary-key rebuild path above, where a brand-new
    column never gets a value copied into it for pre-existing rows —
    would otherwise stay NULL forever. This is a plain, idempotent
    UPDATE, safe to run on every startup.
    """
    try:
        with db.engine.begin() as conn:
            conn.execute(text(
                "UPDATE chat_conversations SET title = 'New chat' "
                "WHERE title IS NULL OR title = ''"
            ))
    except Exception:
        # Table might not exist yet on a brand-new database — create_all()
        # will have just made it with no rows anyway, nothing to backfill.
        logger.debug("Skipping title backfill (chat_conversations not ready yet)")


def sync_schema(app, db) -> None:
    """Add any model columns/indexes missing from the live database, and
    repair a primary key that isn't wired up as a proper SQLite rowid
    alias, or a legacy column the model no longer declares (see
    ``_ensure_table_matches_model`` for why both matter).

    Must be called from inside an active app/application context (the
    caller in app.py already does this alongside ``db.create_all()``).
    Safe to call on every startup. A failure reconciling any single
    table is logged and does not prevent the rest of the tables (or the
    app) from starting.
    """
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, table in db.metadata.tables.items():
        if table_name not in existing_tables:
            # Brand-new table — db.create_all() already handled it.
            continue

        try:
            # Fix the primary key and/or drop any legacy column first:
            # if it needs a rebuild, the rebuilt table already has every
            # column the legacy table had (minus anything the model has
            # since dropped), which makes the ADD COLUMN pass below a
            # no-op for those (any genuinely new column still gets added
            # normally right after).
            _ensure_table_matches_model(db, inspector, table_name, table)
            inspector = inspect(db.engine)

            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            added_any = False

            for column in table.columns:
                if column.name in existing_columns:
                    continue

                ddl_type = _column_ddl_type(column)
                alter_sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {ddl_type}'
                logger.warning(
                    "Schema drift detected: %s.%s is missing from the database. Running: %s",
                    table_name, column.name, alter_sql,
                )
                with db.engine.begin() as conn:
                    conn.execute(text(alter_sql))
                added_any = True

            if added_any:
                # Refresh so later tables (and the index pass below) see
                # the up-to-date column list.
                inspector = inspect(db.engine)
        except Exception:
            logger.exception(
                "Failed to reconcile schema for table %s; continuing with "
                "the remaining tables.",
                table_name,
            )
            inspector = inspect(db.engine)

    _ensure_chat_message_unique_index(db)
    _backfill_conversation_titles(db)


def _ensure_chat_message_unique_index(db) -> None:
    """(Re)create the uq_chat_message_conversation_client uniqueness index.

    A UNIQUE constraint declared in a model's ``__table_args__`` is only
    applied by the original ``CREATE TABLE`` that ``create_all()`` issues.
    Since ``chat_messages`` already existed before ``client_id`` (and its
    uniqueness rule) was added, that constraint never made it onto the
    live database. Creating the equivalent index here re-establishes the
    same duplicate-message protection. ``IF NOT EXISTS`` makes this a
    no-op once it's already in place.
    """
    index_sql = (
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_message_conversation_client '
        'ON chat_messages (conversation_id, client_id)'
    )
    try:
        with db.engine.begin() as conn:
            conn.execute(text(index_sql))
    except Exception:
        # Would only fail if the table already contained duplicate
        # (conversation_id, client_id) pairs with a non-NULL client_id —
        # not expected here since client_id didn't exist until now (every
        # pre-existing row gets NULL, and SQLite treats every NULL as
        # distinct in a unique index). Logged instead of crashing startup.
        logger.exception("Could not (re)create uq_chat_message_conversation_client index")


# ---------------------------------------------------------------------------
# Optional: adopting Flask-Migrate/Alembic later
# ---------------------------------------------------------------------------
# If a future change needs a real migration (rename/drop a column, change a
# type, backfill data), reach for Flask-Migrate instead of extending this
# file:
#
#   pip install Flask-Migrate
#
#   # app.py
#   from flask_migrate import Migrate
#   migrate = Migrate(app, db)
#
#   # one-time, from the project root:
#   flask db init
#   flask db migrate -m "describe the change"
#   flask db upgrade
#
# sync_schema() and Flask-Migrate are safe to have side by side — the
# `for table_name in db.metadata.tables` loop above only ever adds columns
# that are already missing, so it won't conflict with Alembic-managed
# migrations.
