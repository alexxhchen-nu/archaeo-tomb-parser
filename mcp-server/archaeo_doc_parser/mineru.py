"""Unified async MinerU API client — free (v1) and pro (v4)."""

import asyncio
import os
import zipfile
from io import BytesIO
from pathlib import Path

import httpx

FREE_BASE = "https://mineru.net/api/v1"
PRO_BASE = "https://mineru.net/api/v4"


class MinerUError(Exception):
    """MinerU API error with code and message."""


class MinerUClient:
    """Async MinerU client. Defaults to free API; set token for pro."""

    def __init__(self, token: str | None = None, timeout: int = 300):
        self.token = token or os.getenv("MINERU_TOKEN")
        self.timeout = timeout

    @property
    def use_pro(self) -> bool:
        return bool(self.token)

    def _pro_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    # ── Free API (v1) ──────────────────────────────────────────────

    async def _free_submit_url(
        self, client: httpx.AsyncClient, url: str, language: str, pages: str | None
    ) -> str:
        data: dict = {"url": url, "language": language}
        if pages:
            data["page_range"] = pages
        resp = await client.post(f"{FREE_BASE}/agent/parse/url", json=data)
        result = resp.json()
        if result["code"] != 0:
            raise MinerUError(f"Submit failed: {result['msg']}")
        return result["data"]["task_id"]

    async def _free_submit_file(
        self, client: httpx.AsyncClient, file_path: str, language: str, pages: str | None
    ) -> str:
        file_name = Path(file_path).name
        data: dict = {"file_name": file_name, "language": language}
        if pages:
            data["page_range"] = pages
        resp = await client.post(f"{FREE_BASE}/agent/parse/file", json=data)
        result = resp.json()
        if result["code"] != 0:
            raise MinerUError(f"Upload URL failed: {result['msg']}")
        task_id = result["data"]["task_id"]
        upload_url = result["data"]["file_url"]
        with open(file_path, "rb") as f:
            file_data = f.read()
        put_resp = await client.put(upload_url, content=file_data, timeout=120)
        if put_resp.status_code not in (200, 201):
            raise MinerUError(f"Upload failed: HTTP {put_resp.status_code}")
        return task_id

    async def _free_poll(
        self, client: httpx.AsyncClient, task_id: str
    ) -> str:
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < self.timeout:
            resp = await client.get(f"{FREE_BASE}/agent/parse/{task_id}")
            result = resp.json()
            state = result["data"]["state"]
            if state == "done":
                md_url = result["data"]["markdown_url"]
                try:
                    md_resp = await client.get(md_url, timeout=30)
                    return md_resp.text
                except Exception:
                    return (
                        f"Parse completed but the result CDN is unreachable from this location "
                        f"(MinerU CDN is China-hosted).\n\n"
                        f"Result URL (try via VPN or browser): {md_url}\n\n"
                        f"Tip: Set MINERU_TOKEN to use Pro API, which returns results directly."
                    )
            if state == "failed":
                raise MinerUError(f"Parse failed: {result['data'].get('err_msg', 'unknown')}")
            await asyncio.sleep(3)
        raise MinerUError(f"Timed out after {self.timeout}s. Task: {task_id}")

    # ── Pro API (v4) ───────────────────────────────────────────────

    async def _pro_submit_url(
        self, client: httpx.AsyncClient, url: str, language: str, pages: str | None
    ) -> str:
        data: dict = {"url": url, "model_version": "vlm", "language": language}
        if pages:
            data["page_ranges"] = pages
        resp = await client.post(
            f"{PRO_BASE}/extract/task", headers=self._pro_headers(), json=data
        )
        result = resp.json()
        if result["code"] != 0:
            raise MinerUError(f"Pro submit failed: {result['msg']}")
        return result["data"]["task_id"]

    async def _pro_submit_file(
        self, client: httpx.AsyncClient, file_path: str, language: str, pages: str | None
    ) -> tuple[str, str]:
        """Returns (batch_id, full result). Uses batch upload endpoint."""
        file_name = Path(file_path).name
        data: dict = {"files": [{"name": file_name}], "model_version": "vlm", "language": language}
        if pages:
            data["page_ranges"] = pages
        resp = await client.post(
            f"{PRO_BASE}/file-urls/batch", headers=self._pro_headers(), json=data
        )
        result = resp.json()
        if result["code"] != 0:
            raise MinerUError(f"Upload URL failed: {result['msg']}")
        batch_id = result["data"]["batch_id"]
        upload_url = result["data"]["file_urls"][0]
        with open(file_path, "rb") as f:
            file_data = f.read()
        await client.put(upload_url, content=file_data, timeout=120)
        return batch_id

    async def _pro_poll_task(
        self, client: httpx.AsyncClient, task_id: str
    ) -> dict:
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < self.timeout:
            resp = await client.get(
                f"{PRO_BASE}/extract/task/{task_id}", headers=self._pro_headers()
            )
            result = resp.json()
            data = result["data"]
            state = data["state"]
            if state == "done":
                return data
            if state == "failed":
                raise MinerUError(f"Pro parse failed: {data.get('err_msg', 'unknown')}")
            await asyncio.sleep(3)
        raise MinerUError(f"Timed out after {self.timeout}s. Task: {task_id}")

    async def _pro_poll_batch(
        self, client: httpx.AsyncClient, batch_id: str
    ) -> list[dict]:
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < self.timeout:
            resp = await client.get(
                f"{PRO_BASE}/extract-results/batch/{batch_id}", headers=self._pro_headers()
            )
            result = resp.json()
            items = result["data"]["extract_result"]
            if all(r["state"] in ("done", "failed") for r in items):
                return items
            await asyncio.sleep(5)
        raise MinerUError(f"Batch timed out after {self.timeout}s")

    async def _pro_download_markdown(
        self, client: httpx.AsyncClient, zip_url: str
    ) -> str:
        resp = await client.get(zip_url, timeout=120)
        resp.raise_for_status()
        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith("full.md"):
                    return zf.read(name).decode("utf-8")
            # fallback: try any .md file
            for name in zf.namelist():
                if name.endswith(".md"):
                    return zf.read(name).decode("utf-8")
        raise MinerUError("No markdown found in result ZIP")

    # ── Public interface ───────────────────────────────────────────

    async def parse_url(
        self, url: str, language: str = "ch", pages: str | None = None
    ) -> str:
        """Parse a document URL to Markdown. Returns markdown text."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if self.use_pro:
                task_id = await self._pro_submit_url(client, url, language, pages)
                data = await self._pro_poll_task(client, task_id)
                return await self._pro_download_markdown(client, data["full_zip_url"])
            else:
                task_id = await self._free_submit_url(client, url, language, pages)
                return await self._free_poll(client, task_id)

    async def parse_file(
        self, file_path: str, language: str = "ch", pages: str | None = None
    ) -> str:
        """Parse a local file to Markdown. Returns markdown text."""
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if self.use_pro:
                batch_id = await self._pro_submit_file(client, file_path, language, pages)
                items = await self._pro_poll_batch(client, batch_id)
                r = items[0]
                if r["state"] != "done":
                    raise MinerUError(f"Parse failed: {r.get('err_msg', 'unknown')}")
                return await self._pro_download_markdown(client, r["full_zip_url"])
            else:
                task_id = await self._free_submit_file(client, file_path, language, pages)
                return await self._free_poll(client, task_id)

    async def batch_parse(
        self, urls: list[str], language: str = "ch", pages: str | None = None
    ) -> dict[str, str]:
        """Batch parse multiple URLs. Returns {filename: markdown}. Pro only."""
        if not self.use_pro:
            raise MinerUError("Batch parsing requires MINERU_TOKEN (Pro API)")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data: dict = {
                "files": [{"url": u} for u in urls],
                "model_version": "vlm",
                "language": language,
            }
            if pages:
                data["page_ranges"] = pages
            resp = await client.post(
                f"{PRO_BASE}/extract/task/batch", headers=self._pro_headers(), json=data
            )
            result = resp.json()
            if result["code"] != 0:
                raise MinerUError(f"Batch submit failed: {result['msg']}")
            batch_id = result["data"]["batch_id"]
            items = await self._pro_poll_batch(client, batch_id)

            output: dict[str, str] = {}
            for r in items:
                name = r.get("file_name", r.get("url", "unknown"))
                if r["state"] == "done":
                    md = await self._pro_download_markdown(client, r["full_zip_url"])
                    output[name] = md
                else:
                    output[name] = f"ERROR: {r.get('err_msg', 'unknown')}"
            return output

    async def get_task_status(self, task_id: str) -> dict:
        """Check task progress. Pro only for status endpoint."""
        if not self.use_pro:
            raise MinerUError("Task status requires MINERU_TOKEN (Pro API)")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{PRO_BASE}/extract/task/{task_id}", headers=self._pro_headers()
            )
            result = resp.json()
            if result["code"] != 0:
                raise MinerUError(f"Status check failed: {result['msg']}")
            return result["data"]
