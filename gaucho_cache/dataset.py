"""SQLite-backed variant dataset with idempotent, resumable writes.

Ported pattern from models-medical-evaluation
(`chapter_3_3_dense_variants.py`): UNIQUE-keyed cells +
``get_missing_cells`` so a crashed/re-run generation only fills gaps.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

# The WhatsApp variant matrix (PLAN.md §3): length × register × noise.
LENGTH_LEVELS = {
    0: "fragment, 1-3 words",
    1: "short, 4-7 words",
    2: "one full sentence, 8-14 words",
    3: "longer message, 15-25 words, may have two clauses",
}
REGISTERS = {
    "formal": "formal Spanish (usted or neutral, polite, full words)",
    "neutral": "neutral everyday Argentine Spanish (vos, plain)",
    "slang": "rioplatense slang (che, vos, colloquialisms like 'guita', 'posta', 'dale')",
}
NOISE_LEVELS = {
    0: "clean spelling and punctuation",
    1: "typical WhatsApp noise: typos, missing accents, abbreviations (q, xq, tmb), little punctuation",
}
PARAPHRASES_PER_CELL = 4  # 4×3×2 cells × 4 ≈ 96 positives per intent
NEGATIVES_PER_INTENT = 35  # 20 initial + boundary top-ups (rounds 6-7)

SCHEMA = """
CREATE TABLE IF NOT EXISTS variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    intent TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('positive','negative')),
    length_level INTEGER,
    register TEXT,
    noise INTEGER,
    variant_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    actual_intent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stage, intent, kind, length_level, register, noise, variant_index)
);
"""


@dataclass(frozen=True)
class Cell:
    stage: str
    intent: str
    length_level: int
    register: str
    noise: int


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    # QA-pass columns (clean_dataset.py): an LLM-judged corrected label,
    # and a drop flag for genuinely ambiguous variants (they represent
    # the miss path, not a classifier target).
    for ddl in ("ALTER TABLE variants ADD COLUMN judged_intent TEXT",
                "ALTER TABLE variants ADD COLUMN dropped INTEGER DEFAULT 0"):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists
    return conn


def all_cells(stage: str, intent: str) -> list[Cell]:
    return [
        Cell(stage, intent, ll, reg, nz)
        for ll in LENGTH_LEVELS
        for reg in REGISTERS
        for nz in NOISE_LEVELS
    ]


def missing_positive_cells(conn: sqlite3.Connection, stage: str, intent: str) -> list[Cell]:
    """Cells that don't yet hold all PARAPHRASES_PER_CELL variants."""
    rows = conn.execute(
        """SELECT length_level, register, noise, COUNT(*) FROM variants
           WHERE stage=? AND intent=? AND kind='positive'
           GROUP BY length_level, register, noise""",
        (stage, intent),
    ).fetchall()
    complete = {(r[0], r[1], r[2]) for r in rows if r[3] >= PARAPHRASES_PER_CELL}
    return [
        c for c in all_cells(stage, intent)
        if (c.length_level, c.register, c.noise) not in complete
    ]


def missing_negatives(conn: sqlite3.Connection, stage: str, intent: str) -> int:
    n = conn.execute(
        """SELECT COUNT(*) FROM variants
           WHERE stage=? AND intent=? AND kind='negative' AND dropped=0""",
        (stage, intent),
    ).fetchone()[0]
    return max(0, NEGATIVES_PER_INTENT - n)


def next_negative_index(conn: sqlite3.Connection, stage: str, intent: str) -> int:
    """First free variant_index for negative top-ups (never reuses an
    index, including dropped rows', so UNIQUE can't collide)."""
    return conn.execute(
        """SELECT COALESCE(MAX(variant_index) + 1, 0) FROM variants
           WHERE stage=? AND intent=? AND kind='negative'""",
        (stage, intent),
    ).fetchone()[0]


def store_positives(conn: sqlite3.Connection, cell: Cell, texts: list[str]) -> None:
    for i, text in enumerate(texts):
        conn.execute(
            """INSERT OR REPLACE INTO variants
               (stage, intent, kind, length_level, register, noise, variant_index, text)
               VALUES (?,?,?,?,?,?,?,?)""",
            (cell.stage, cell.intent, "positive",
             cell.length_level, cell.register, cell.noise, i, text),
        )
    conn.commit()


def store_negatives(conn: sqlite3.Connection, stage: str, intent: str,
                    items: list[tuple[str, str]], start_index: int = 0) -> None:
    """items: (text, actual_intent) pairs."""
    for i, (text, actual) in enumerate(items, start=start_index):
        conn.execute(
            """INSERT OR REPLACE INTO variants
               (stage, intent, kind, length_level, register, noise,
                variant_index, text, actual_intent)
               VALUES (?,?,?,NULL,NULL,NULL,?,?,?)""",
            (stage, intent, "negative", i, text, actual),
        )
    conn.commit()


def load_all(conn: sqlite3.Connection, stage: str):
    """Return [(intent, kind, text, actual_intent)] for index/eval builds.

    Positives honor the QA pass: the judged label wins over the
    generation label, and dropped (ambiguous) rows are excluded.
    """
    return conn.execute(
        """SELECT COALESCE(NULLIF(judged_intent,''), intent), kind, text,
                  COALESCE(actual_intent,'')
           FROM variants WHERE stage=? AND dropped=0
           ORDER BY intent, kind, id""",
        (stage,),
    ).fetchall()


def counts(conn: sqlite3.Connection, stage: str) -> list[tuple[str, str, int]]:
    return conn.execute(
        """SELECT intent, kind, COUNT(*) FROM variants
           WHERE stage=? GROUP BY intent, kind ORDER BY intent, kind""",
        (stage,),
    ).fetchall()
