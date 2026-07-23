from __future__ import annotations

from typing import Any

import httpx

from .core import get_settings


ALLOWED_TOOLS = {"list_log_entries", "list_log_names", "list_timeseries", "list_alerts"}


class OpsMcpAdapter:
    def __init__(self):
        self.settings = get_settings()

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.settings.mcp_provider,
            "connected": bool(self.settings.google_cloud_mcp_token),
            "mode": "Google Cloud read-only",
            "allowed_tools": sorted(ALLOWED_TOOLS),
        }

    async def snapshot(self) -> dict[str, Any]:
        if not self.settings.google_cloud_project or not self.settings.google_cloud_mcp_token:
            raise RuntimeError("Google Cloud MCP requires project and bearer token")
        headers = {
            "Authorization": f"Bearer {self.settings.google_cloud_mcp_token}",
            "x-goog-user-project": self.settings.google_cloud_project,
            "Accept": "application/json, text/event-stream",
        }
        calls = [
            (
                "https://logging.googleapis.com/mcp",
                "list_log_names",
                {"parent": f"projects/{self.settings.google_cloud_project}", "pageSize": 50},
            ),
            (
                "https://logging.googleapis.com/mcp",
                "list_log_entries",
                {
                    "resourceNames": [f"projects/{self.settings.google_cloud_project}"],
                    "filter": (
                        'resource.labels.project_id="'
                        f"{self.settings.google_cloud_project}"
                        '" AND severity>=WARNING'
                    ),
                    "pageSize": 20,
                },
            ),
            (
                "https://monitoring.googleapis.com/mcp",
                "list_timeseries",
                {
                    "name": f"projects/{self.settings.google_cloud_project}",
                    "filter": 'metric.type="run.googleapis.com/request_count"',
                    "view": "HEADERS",
                },
            ),
            (
                "https://monitoring.googleapis.com/mcp",
                "list_alerts",
                {"parent": f"projects/{self.settings.google_cloud_project}", "pageSize": 20},
            ),
        ]
        summaries = []
        async with httpx.AsyncClient(timeout=5) as client:
            for index, (url, tool, arguments) in enumerate(calls, 1):
                if tool not in ALLOWED_TOOLS:
                    raise PermissionError(f"MCP tool {tool} is not allowlisted")
                response = await client.post(url, headers=headers, json={"jsonrpc":"2.0", "id":index, "method":"tools/call", "params":{"name":tool, "arguments":arguments}})
                response.raise_for_status()
                body = response.json()
                result = body.get("result", {}) if isinstance(body, dict) else {}
                summaries.append(
                    {
                        "tool": tool,
                        "ok": "error" not in body,
                        "result_fields": sorted(result) if isinstance(result, dict) else [],
                    }
                )
        return {
            "source": "google-cloud-mcp",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "project": self.settings.google_cloud_project,
            "sanitized_summaries": summaries,
            "note": "Raw log entries, metric points, and alert payloads are not returned to the UI.",
        }
