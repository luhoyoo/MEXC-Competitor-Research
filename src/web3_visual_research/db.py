from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    competitor_name TEXT NOT NULL,
    competitor_slug TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    page_url TEXT NOT NULL,
    page_title TEXT,
    published_at TEXT,
    image_url TEXT NOT NULL,
    image_path TEXT,
    image_width INTEGER,
    image_height INTEGER,
    file_sha256 TEXT,
    visual_type TEXT,
    analysis_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_date, competitor_slug, source_type, image_url)
);
"""


class VisualDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def upsert_item(self, item: dict[str, Any]) -> int:
        fields = [
            "run_date",
            "competitor_name",
            "competitor_slug",
            "source_type",
            "source_url",
            "page_url",
            "page_title",
            "published_at",
            "image_url",
            "image_path",
            "image_width",
            "image_height",
            "file_sha256",
            "visual_type",
            "analysis_json",
        ]
        payload = {field: item.get(field) for field in fields}
        self.conn.execute(
            """
            INSERT INTO visual_items (
                run_date, competitor_name, competitor_slug, source_type, source_url,
                page_url, page_title, published_at, image_url, image_path,
                image_width, image_height, file_sha256, visual_type, analysis_json
            )
            VALUES (
                :run_date, :competitor_name, :competitor_slug, :source_type, :source_url,
                :page_url, :page_title, :published_at, :image_url, :image_path,
                :image_width, :image_height, :file_sha256, :visual_type, :analysis_json
            )
            ON CONFLICT(run_date, competitor_slug, source_type, image_url)
            DO UPDATE SET
                source_url = excluded.source_url,
                page_url = excluded.page_url,
                page_title = COALESCE(excluded.page_title, visual_items.page_title),
                published_at = COALESCE(excluded.published_at, visual_items.published_at),
                image_path = COALESCE(excluded.image_path, visual_items.image_path),
                image_width = COALESCE(excluded.image_width, visual_items.image_width),
                image_height = COALESCE(excluded.image_height, visual_items.image_height),
                file_sha256 = COALESCE(excluded.file_sha256, visual_items.file_sha256),
                visual_type = COALESCE(excluded.visual_type, visual_items.visual_type),
                analysis_json = COALESCE(excluded.analysis_json, visual_items.analysis_json)
            """,
            payload,
        )
        self.conn.commit()
        row = self.conn.execute(
            """
            SELECT id FROM visual_items
            WHERE run_date = ? AND competitor_slug = ? AND source_type = ? AND image_url = ?
            """,
            (
                payload["run_date"],
                payload["competitor_slug"],
                payload["source_type"],
                payload["image_url"],
            ),
        ).fetchone()
        return int(row["id"])

    def update_download(self, item_id: int, image_path: Path, width: int, height: int, file_sha256: str) -> None:
        self.conn.execute(
            """
            UPDATE visual_items
            SET image_path = ?, image_width = ?, image_height = ?, file_sha256 = ?
            WHERE id = ?
            """,
            (str(image_path), width, height, file_sha256, item_id),
        )
        self.conn.commit()

    def update_analysis(self, item_id: int, analysis: dict[str, Any]) -> None:
        self.conn.execute(
            """
            UPDATE visual_items
            SET visual_type = ?, analysis_json = ?
            WHERE id = ?
            """,
            (
                analysis.get("visual_type"),
                json.dumps(analysis, ensure_ascii=False, indent=2),
                item_id,
            ),
        )
        self.conn.commit()

    def clear_run_date(self, run_date: str) -> None:
        self.conn.execute("DELETE FROM visual_items WHERE run_date = ?", (run_date,))
        self.conn.commit()

    def list_items(self, run_date: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM visual_items
            WHERE run_date = ?
            ORDER BY competitor_name, source_type, id
            """,
            (run_date,),
        ).fetchall()
        return [dict(row) for row in rows]
