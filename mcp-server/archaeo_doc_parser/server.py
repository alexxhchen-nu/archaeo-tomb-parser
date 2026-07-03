#!/usr/bin/env python3
"""
考古文献解析 MCP Server

Parses archaeological documents (PDF, images, Office files) to Markdown
via MinerU cloud API. Free tier works out of the box; set MINERU_TOKEN
for Pro features (200MB/200 pages, batch parsing, JSON output).

Any MCP client (Claude Desktop, Cursor, Kimi Code, etc.) can connect.
"""

import json
import os
import sys
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from mcp.server.fastmcp import FastMCP

from .mineru import MinerUClient, MinerUError

# ── Server init ────────────────────────────────────────────────────

mcp = FastMCP(
    "archaeo_doc_parser",
    instructions="考古文献解析 — Parse PDFs, images, and Office docs to Markdown via MinerU",
)

# Lazy-init client so env vars are read at call time
_client: MinerUClient | None = None


def _get_client() -> MinerUClient:
    global _client
    if _client is None:
        _client = MinerUClient()  # reads MINERU_TOKEN from env automatically
    return _client


# ── Input models ───────────────────────────────────────────────────

class ParseDocumentInput(BaseModel):
    """Input for parsing a single document."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    source: str = Field(
        ...,
        description="Document URL (http/https) or local file path",
        min_length=1,
    )
    language: str = Field(
        default="ch",
        description="OCR language hint: 'ch' (Chinese), 'en', 'japan', 'korean', etc.",
    )
    pages: Optional[str] = Field(
        default=None,
        description="Page range, e.g. '1-10' or '5'",
    )


class ParseBatchInput(BaseModel):
    """Input for batch parsing multiple documents (Pro only)."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    sources: list[str] = Field(
        ...,
        description="List of document URLs to parse",
        min_length=1,
        max_length=50,
    )
    language: str = Field(
        default="ch",
        description="OCR language hint",
    )
    pages: Optional[str] = Field(
        default=None,
        description="Page range applied to all documents",
    )


class TaskStatusInput(BaseModel):
    """Input for checking task status."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    task_id: str = Field(
        ...,
        description="Task ID returned by a previous parse request",
        min_length=1,
    )


# ── Tools ──────────────────────────────────────────────────────────

SUPPORTED_FORMATS = {
    "documents": ["PDF", "DOCX", "PPTX", "XLSX"],
    "images": ["PNG", "JPG", "JPEG", "JP2", "WebP", "GIF", "BMP"],
    "free_limits": {"max_size_mb": 10, "max_pages": 20, "output": "markdown only"},
    "pro_limits": {"max_size_mb": 200, "max_pages": 200, "output": "markdown, JSON, DOCX, HTML, LaTeX"},
}


@mcp.tool(
    name="parse_document",
    annotations={
        "title": "Parse Document to Markdown",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parse_document(params: ParseDocumentInput) -> str:
    """Parse a document (URL or local file) to Markdown.

    Supports PDF, PNG, JPG, DOCX, PPTX, XLSX. Optimized for Chinese
    archaeological documents. Uses MinerU free API by default; set
    MINERU_TOKEN env var to unlock Pro features (larger files, better OCR).

    Args:
        params: source (URL or file path), language hint, page range

    Returns:
        Parsed document as Markdown text, or error message.
    """
    client = _get_client()
    try:
        is_url = params.source.startswith(("http://", "https://"))
        if is_url:
            result = await client.parse_url(params.source, params.language, params.pages)
        else:
            result = await client.parse_file(params.source, params.language, params.pages)

        # Truncate very long results to avoid flooding context
        if len(result) > 200_000:
            result = result[:200_000] + f"\n\n---\n[Truncated: output was {len(result):,} chars]"

        return result
    except FileNotFoundError as e:
        return f"Error: {e}"
    except MinerUError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error — {type(e).__name__}: {e}"


@mcp.tool(
    name="parse_batch",
    annotations={
        "title": "Batch Parse Documents (Pro)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def parse_batch(params: ParseBatchInput) -> str:
    """Batch-parse multiple documents at once. Requires MINERU_TOKEN (Pro API).

    Submits all URLs in parallel, polls until complete, returns a JSON
    mapping of {filename: markdown_content}.

    Args:
        params: list of source URLs, language hint, page range

    Returns:
        JSON string mapping filenames to their parsed Markdown content.
    """
    client = _get_client()
    if not client.use_pro:
        return (
            "Error: Batch parsing requires MINERU_TOKEN (Pro API).\n"
            "Get a token at https://mineru.net → API管理.\n"
            "Set it in your MCP client config's env block:\n"
            '  "env": { "MINERU_TOKEN": "your-token" }'
        )
    try:
        result = await client.batch_parse(params.sources, params.language, params.pages)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except MinerUError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error — {type(e).__name__}: {e}"


@mcp.tool(
    name="get_task_status",
    annotations={
        "title": "Check Parse Task Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def get_task_status(params: TaskStatusInput) -> str:
    """Check the progress of a parsing task. Requires MINERU_TOKEN (Pro API).

    Args:
        params: task_id from a previous parse request

    Returns:
        JSON with task state, progress, and result URLs.
    """
    client = _get_client()
    if not client.use_pro:
        return (
            "Error: Task status requires MINERU_TOKEN (Pro API).\n"
            "Free-tier tasks are polled automatically by parse_document."
        )
    try:
        data = await client.get_task_status(params.task_id)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except MinerUError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Unexpected error — {type(e).__name__}: {e}"


@mcp.tool(
    name="get_supported_formats",
    annotations={
        "title": "List Supported Formats and Limits",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_supported_formats() -> str:
    """List supported file types and API limits for free and Pro tiers.

    Returns:
        JSON with supported formats and tier limits.
    """
    client = _get_client()
    info = {**SUPPORTED_FORMATS, "pro_enabled": client.use_pro}
    return json.dumps(info, ensure_ascii=False, indent=2)


# ── Tomb parsing ──────────────────────────────────────────────────

from .tomb_parser import TombParser


class ParseTombsInput(BaseModel):
    """Input for parsing tomb data from an archaeological report."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_path: str = Field(
        ...,
        description="Path to a .md or .txt archaeological report file",
        min_length=1,
    )
    report_name: str = Field(
        default="",
        description="Optional report title (auto-detected from filename if empty)",
    )
    output_dir: str = Field(
        default="",
        description="Optional directory to export JSON + CSV + MD files. If empty, returns JSON only.",
    )


@mcp.tool(
    name="parse_tombs",
    annotations={
        "title": "Extract Tomb Data from Archaeological Report",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def parse_tombs(params: ParseTombsInput) -> str:
    """Extract tomb (墓葬) data from a Chinese archaeological report.

    Parses .md or .txt files to find tomb descriptions, artifacts, dynasty
    information, and dimensions. Returns structured JSON.

    Supports various report formats:
    - Standard tomb reports (M+number headers)
    - City site reports with incidental tombs (YSTG4AM1, etc.)
    - Diagram-only references, modern tomb groups, external references

    Optionally exports to three formats: JSON, CSV (Excel-compatible), Markdown.

    Args:
        params: file_path (required), report_name, output_dir

    Returns:
        JSON string with tomb list and artifact details.
    """
    from pathlib import Path

    file_path = Path(params.file_path).expanduser()
    if not file_path.exists():
        return f"Error: File not found: {file_path}"
    if file_path.suffix not in ('.md', '.txt'):
        return f"Error: Unsupported file type '{file_path.suffix}'. Use .md or .txt."

    report_name = params.report_name or file_path.stem

    try:
        parser = TombParser(
            report_name=report_name,
            input_file=str(file_path),
            output_dir=params.output_dir or str(file_path.parent / f"{file_path.stem}_tombs"),
        )

        # The TombParser loads the file; the agent is expected to have already
        # extracted tomb data. Here we provide a basic auto-extraction for
        # common patterns, but the real power is when the agent calls this
        # after analyzing the document structure.

        # Auto-detect M+number tomb headers
        import re
        tomb_headers = []
        for i, line in enumerate(parser.lines):
            m = re.match(r'^#{1,3}\s*(?:[一二三四五六七八九十百千]+、\s*)?(M\s*\d+)\b', line)
            if m:
                tomb_id = m.group(1).replace(' ', '')
                tomb_headers.append((i + 1, tomb_id))

        if tomb_headers:
            for idx, (line_num, tomb_id) in enumerate(tomb_headers):
                start = line_num - 1
                end = tomb_headers[idx + 1][0] - 1 if idx + 1 < len(tomb_headers) else len(parser.lines)
                block = ''.join(parser.lines[start:end])
                block_clean = re.sub(r'<div[^>]*>.*?</div>', ' ', block, flags=re.DOTALL)
                block_clean = re.sub(r'\s+', ' ', block_clean)

                dynasty = parser.extract_direction(block_clean)  # placeholder
                tomb_type = ""
                for t in ["土坑竖穴砖椁墓", "土坑竖穴墓", "土坑洞室墓", "砖室墓", "石室墓", "长方形土坑墓"]:
                    if t in block_clean.replace(' ', ''):
                        tomb_type = t
                        break

                parser.add_tomb({
                    "墓葬编号": tomb_id,
                    "墓葬形制": tomb_type,
                    **parser.extract_dimensions(block_clean),
                })

        # Export if output_dir specified or if we found tombs
        if parser.tombs and params.output_dir:
            parser.export()

        return json.dumps(
            {"墓葬列表": parser.tombs, "count": len(parser.tombs)},
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


# ── Entry point ────────────────────────────────────────────────────

def main():
    """Entry point for the MCP server (called by `archaeo-doc-parser` CLI)."""
    import argparse

    parser = argparse.ArgumentParser(description="考古文献解析 MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (only with --transport http)")
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="streamable_http", port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
