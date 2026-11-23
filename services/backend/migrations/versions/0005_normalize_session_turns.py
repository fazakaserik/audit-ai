"""Replace session_turns JSONB blobs with columns and child tables.

Also converts chunks.heading_path from JSONB to text[].

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- chunks.heading_path: jsonb -> text[] ---
    # Postgres forbids subqueries in ALTER ... USING, so convert via a new column.
    op.add_column(
        "chunks",
        sa.Column(
            "heading_path_arr",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.execute(
        """
        UPDATE chunks
        SET heading_path_arr = COALESCE(
            (
                SELECT array_agg(value ORDER BY ordinality)
                FROM jsonb_array_elements_text(heading_path) WITH ORDINALITY AS t(value, ordinality)
            ),
            ARRAY[]::text[]
        )
        """
    )
    op.drop_column("chunks", "heading_path")
    op.alter_column("chunks", "heading_path_arr", new_column_name="heading_path")

    # --- session_turns: add relational columns ---
    op.add_column("session_turns", sa.Column("question_text", sa.Text(), nullable=True))
    op.add_column(
        "session_turns",
        sa.Column("question_folder_scope", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "session_turns",
        sa.Column("question_auditor_role", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "session_turns",
        sa.Column("question_topic", sa.String(length=200), nullable=True),
    )
    op.add_column("session_turns", sa.Column("answer_status", sa.String(length=32), nullable=True))
    op.add_column("session_turns", sa.Column("answer_text", sa.Text(), nullable=True))
    op.add_column(
        "session_turns",
        sa.Column("insufficient_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "session_turns",
        sa.Column("usage_prompt_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "session_turns",
        sa.Column("usage_completion_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "session_turns",
        sa.Column("usage_total_tokens", sa.Integer(), nullable=True),
    )

    op.create_table(
        "turn_citations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("turn_id", sa.Uuid(), sa.ForeignKey("session_turns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("marker", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_path", sa.String(length=1024), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column(
            "heading_path",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.UniqueConstraint("turn_id", "kind", "marker", name="uq_turn_citations_turn_kind_marker"),
    )
    op.create_index("ix_turn_citations_turn_id", "turn_citations", ["turn_id"])

    op.create_table(
        "turn_suggested_questions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("turn_id", sa.Uuid(), sa.ForeignKey("session_turns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.UniqueConstraint("turn_id", "ordinal", name="uq_turn_suggested_questions_turn_ordinal"),
    )
    op.create_index("ix_turn_suggested_questions_turn_id", "turn_suggested_questions", ["turn_id"])

    # Backfill turn scalar fields from JSONB (supports legacy passage_id in citation blobs).
    op.execute(
        """
        UPDATE session_turns SET
          question_text = COALESCE(question->>'text', ''),
          question_folder_scope = NULLIF(question->>'folder_scope', ''),
          question_auditor_role = NULLIF(question->>'auditor_role', ''),
          question_topic = NULLIF(question->>'topic', ''),
          answer_status = COALESCE(answer->>'status', 'insufficient_evidence'),
          answer_text = CASE
            WHEN answer->>'status' = 'answered' THEN answer->>'text'
            ELSE NULL
          END,
          insufficient_reason = CASE
            WHEN answer->>'status' = 'insufficient_evidence' THEN
              CASE answer->>'reason'
                WHEN 'no_relevant_passages' THEN 'no_relevant_chunks'
                ELSE answer->>'reason'
              END
            ELSE NULL
          END,
          usage_prompt_tokens = CASE
            WHEN llm_usage ? 'prompt_tokens' THEN (llm_usage->>'prompt_tokens')::int
            ELSE NULL
          END,
          usage_completion_tokens = CASE
            WHEN llm_usage ? 'completion_tokens' THEN (llm_usage->>'completion_tokens')::int
            ELSE NULL
          END,
          usage_total_tokens = CASE
            WHEN llm_usage ? 'total_tokens' THEN (llm_usage->>'total_tokens')::int
            ELSE NULL
          END
        """
    )

    op.execute(
        """
        INSERT INTO turn_citations (
          id, turn_id, kind, marker, chunk_id, document_id, document_path,
          page, heading_path, snippet, score
        )
        SELECT
          gen_random_uuid(),
          t.id,
          'answer',
          COALESCE((c.elem->>'marker')::int, 1),
          COALESCE(
            NULLIF(c.elem->>'chunk_id', '')::uuid,
            NULLIF(c.elem->>'passage_id', '')::uuid
          ),
          (c.elem->>'document_id')::uuid,
          c.elem->>'document_path',
          NULLIF(c.elem->>'page', '')::int,
          COALESCE(
            ARRAY(SELECT jsonb_array_elements_text(COALESCE(c.elem->'heading_path', '[]'::jsonb))),
            ARRAY[]::text[]
          ),
          COALESCE(c.elem->>'snippet', ''),
          COALESCE((c.elem->>'score')::float, 0.0)
        FROM session_turns t
        CROSS JOIN LATERAL jsonb_array_elements(
          CASE
            WHEN jsonb_typeof(t.answer->'citations') = 'array' THEN t.answer->'citations'
            ELSE '[]'::jsonb
          END
        ) AS c(elem)
        WHERE t.answer->>'status' = 'answered'
          AND COALESCE(
            NULLIF(c.elem->>'chunk_id', '')::uuid,
            NULLIF(c.elem->>'passage_id', '')::uuid
          ) IS NOT NULL
        """
    )

    op.execute(
        """
        INSERT INTO turn_citations (
          id, turn_id, kind, marker, chunk_id, document_id, document_path,
          page, heading_path, snippet, score
        )
        SELECT
          gen_random_uuid(),
          t.id,
          'partial',
          COALESCE((c.elem->>'marker')::int, 1),
          COALESCE(
            NULLIF(c.elem->>'chunk_id', '')::uuid,
            NULLIF(c.elem->>'passage_id', '')::uuid
          ),
          (c.elem->>'document_id')::uuid,
          c.elem->>'document_path',
          NULLIF(c.elem->>'page', '')::int,
          COALESCE(
            ARRAY(SELECT jsonb_array_elements_text(COALESCE(c.elem->'heading_path', '[]'::jsonb))),
            ARRAY[]::text[]
          ),
          COALESCE(c.elem->>'snippet', ''),
          COALESCE((c.elem->>'score')::float, 0.0)
        FROM session_turns t
        CROSS JOIN LATERAL jsonb_array_elements(
          CASE
            WHEN jsonb_typeof(t.answer->'partial_citations') = 'array'
              THEN t.answer->'partial_citations'
            ELSE '[]'::jsonb
          END
        ) AS c(elem)
        WHERE t.answer->>'status' = 'insufficient_evidence'
          AND COALESCE(
            NULLIF(c.elem->>'chunk_id', '')::uuid,
            NULLIF(c.elem->>'passage_id', '')::uuid
          ) IS NOT NULL
        """
    )

    op.execute(
        """
        INSERT INTO turn_suggested_questions (id, turn_id, ordinal, question, rationale)
        SELECT
          gen_random_uuid(),
          t.id,
          (s.ord - 1),
          COALESCE(s.elem->>'question', ''),
          COALESCE(s.elem->>'rationale', '')
        FROM session_turns t
        CROSS JOIN LATERAL jsonb_array_elements(
          CASE
            WHEN jsonb_typeof(t.answer->'suggested_client_questions') = 'array'
              THEN t.answer->'suggested_client_questions'
            ELSE '[]'::jsonb
          END
        ) WITH ORDINALITY AS s(elem, ord)
        WHERE t.answer->>'status' = 'insufficient_evidence'
        """
    )

    # Domain requires ≥1 suggested question for insufficient answers.
    op.execute(
        """
        INSERT INTO turn_suggested_questions (id, turn_id, ordinal, question, rationale)
        SELECT
          gen_random_uuid(),
          t.id,
          0,
          'Can you provide additional documents for this question?',
          'Migrated turn had no suggested client questions stored.'
        FROM session_turns t
        WHERE t.answer_status = 'insufficient_evidence'
          AND NOT EXISTS (
            SELECT 1 FROM turn_suggested_questions s WHERE s.turn_id = t.id
          )
        """
    )

    # Answered requires ≥1 citation; demote broken legacy rows.
    op.execute(
        """
        UPDATE session_turns t
        SET
          answer_status = 'insufficient_evidence',
          insufficient_reason = COALESCE(insufficient_reason, 'model_judged_insufficient'),
          answer_text = NULL
        WHERE t.answer_status = 'answered'
          AND NOT EXISTS (
            SELECT 1 FROM turn_citations c
            WHERE c.turn_id = t.id AND c.kind = 'answer'
          )
        """
    )
    op.execute(
        """
        INSERT INTO turn_suggested_questions (id, turn_id, ordinal, question, rationale)
        SELECT
          gen_random_uuid(),
          t.id,
          0,
          'Can you restate or provide documents for this question?',
          'Migrated answered turn had no valid citations.'
        FROM session_turns t
        WHERE t.answer_status = 'insufficient_evidence'
          AND NOT EXISTS (
            SELECT 1 FROM turn_suggested_questions s WHERE s.turn_id = t.id
          )
        """
    )

    op.alter_column("session_turns", "question_text", nullable=False)
    op.alter_column("session_turns", "answer_status", nullable=False)

    op.drop_column("session_turns", "question")
    op.drop_column("session_turns", "answer")
    op.drop_column("session_turns", "llm_usage")


def downgrade() -> None:
    op.add_column(
        "session_turns",
        sa.Column("question", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "session_turns",
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "session_turns",
        sa.Column("llm_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.execute(
        """
        UPDATE session_turns SET
          question = jsonb_build_object(
            'text', question_text,
            'folder_scope', question_folder_scope,
            'auditor_role', question_auditor_role,
            'topic', question_topic
          ),
          answer = CASE
            WHEN answer_status = 'answered' THEN jsonb_build_object(
              'status', 'answered',
              'text', COALESCE(answer_text, ''),
              'citations', COALESCE((
                SELECT jsonb_agg(
                  jsonb_build_object(
                    'marker', marker,
                    'chunk_id', chunk_id::text,
                    'document_id', document_id::text,
                    'document_path', document_path,
                    'page', page,
                    'heading_path', to_jsonb(heading_path),
                    'snippet', snippet,
                    'score', score
                  ) ORDER BY marker
                )
                FROM turn_citations
                WHERE turn_id = session_turns.id AND kind = 'answer'
              ), '[]'::jsonb)
            )
            ELSE jsonb_build_object(
              'status', 'insufficient_evidence',
              'reason', COALESCE(insufficient_reason, 'model_judged_insufficient'),
              'partial_citations', COALESCE((
                SELECT jsonb_agg(
                  jsonb_build_object(
                    'marker', marker,
                    'chunk_id', chunk_id::text,
                    'document_id', document_id::text,
                    'document_path', document_path,
                    'page', page,
                    'heading_path', to_jsonb(heading_path),
                    'snippet', snippet,
                    'score', score
                  ) ORDER BY marker
                )
                FROM turn_citations
                WHERE turn_id = session_turns.id AND kind = 'partial'
              ), '[]'::jsonb),
              'suggested_client_questions', COALESCE((
                SELECT jsonb_agg(
                  jsonb_build_object(
                    'question', question,
                    'rationale', rationale
                  ) ORDER BY ordinal
                )
                FROM turn_suggested_questions
                WHERE turn_id = session_turns.id
              ), '[]'::jsonb)
            )
          END,
          llm_usage = CASE
            WHEN usage_prompt_tokens IS NULL
              AND usage_completion_tokens IS NULL
              AND usage_total_tokens IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'prompt_tokens', COALESCE(usage_prompt_tokens, 0),
              'completion_tokens', COALESCE(usage_completion_tokens, 0),
              'total_tokens', COALESCE(usage_total_tokens, 0)
            )
          END
        """
    )

    op.alter_column("session_turns", "question", nullable=False)
    op.alter_column("session_turns", "answer", nullable=False)

    op.drop_index("ix_turn_suggested_questions_turn_id", table_name="turn_suggested_questions")
    op.drop_table("turn_suggested_questions")
    op.drop_index("ix_turn_citations_turn_id", table_name="turn_citations")
    op.drop_table("turn_citations")

    op.drop_column("session_turns", "usage_total_tokens")
    op.drop_column("session_turns", "usage_completion_tokens")
    op.drop_column("session_turns", "usage_prompt_tokens")
    op.drop_column("session_turns", "insufficient_reason")
    op.drop_column("session_turns", "answer_text")
    op.drop_column("session_turns", "answer_status")
    op.drop_column("session_turns", "question_topic")
    op.drop_column("session_turns", "question_auditor_role")
    op.drop_column("session_turns", "question_folder_scope")
    op.drop_column("session_turns", "question_text")

    op.add_column(
        "chunks",
        sa.Column("heading_path_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        """
        UPDATE chunks
        SET heading_path_json = to_jsonb(heading_path)
        """
    )
    op.alter_column("chunks", "heading_path_json", nullable=False)
    op.drop_column("chunks", "heading_path")
    op.alter_column("chunks", "heading_path_json", new_column_name="heading_path")
