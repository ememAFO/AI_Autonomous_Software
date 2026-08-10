"""Minimal MCP stdio transport for a pinned Hound process.

No MCP dependency is added to the factory. The transport speaks the small
JSON-RPC subset required for initialize, tools/list and tools/call.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Self


class HoundTransportError(RuntimeError):
    pass


ALLOWED_HOUND_EXECUTABLE = "hound"


def _validate_hound_command(command: Sequence[str]) -> tuple[str, ...]:
    """Validate the factory-owned Hound process boundary.

    The transport may pass optional arguments to Hound, but it must never be
    used as a generic subprocess launcher.
    """
    if isinstance(command, (str, bytes)):
        raise HoundTransportError(
            "Hound command must be a sequence of arguments, not a string"
        )

    normalized = tuple(command)

    if not normalized:
        raise HoundTransportError("Hound command cannot be empty")

    if any(not isinstance(part, str) or not part.strip() for part in normalized):
        raise HoundTransportError(
            "Hound command arguments must be non-empty strings"
        )

    if any("\x00" in part for part in normalized):
        raise HoundTransportError("Hound command contains an invalid NUL byte")

    if normalized[0] != ALLOWED_HOUND_EXECUTABLE:
        raise HoundTransportError(
            "Hound executable is pinned to 'hound'; arbitrary executables are blocked"
        )

    return normalized


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    input_schema: dict[str, Any]


class MCPStdioTransport:
    def __init__(
        self,
        command: Sequence[str] = ("hound",),
        *,
        protocol_version: str = "2025-03-26",
        request_timeout_seconds: float = 60.0,
    ) -> None:
        self.command = _validate_hound_command(command)
        self.protocol_version = protocol_version
        self.request_timeout_seconds = request_timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._lock = threading.Lock()
        self._tools: dict[str, ToolDescriptor] = {}

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return
        try:
            # Command is validated and the executable is pinned to "hound".
            self._process = subprocess.Popen(  # nosec B603
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise HoundTransportError(f"Unable to start Hound: {exc}") from exc

        result = self._request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": "ai-software-factory-hound-wrapper",
                    "version": "0.1.0",
                },
            },
        )
        if not isinstance(result, dict):
            raise HoundTransportError("Invalid initialize response")
        self._notify("notifications/initialized", {})
        self._tools = {tool.name: tool for tool in self.list_tools()}

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.stdin:
                process.stdin.close()
            process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            process.kill()

    def list_tools(self) -> list[ToolDescriptor]:
        result = self._request("tools/list", {})
        raw_tools = result.get("tools", []) if isinstance(result, dict) else []
        tools: list[ToolDescriptor] = []
        for raw in raw_tools:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip()
            if not name:
                continue
            schema = raw.get("inputSchema", {})
            tools.append(
                ToolDescriptor(
                    name=name,
                    input_schema=schema if isinstance(schema, dict) else {},
                )
            )
        return tools

    def tool_schema(self, name: str) -> dict[str, Any]:
        descriptor = self._tools.get(name)
        if descriptor is None:
            raise HoundTransportError(f"Required Hound tool not available: {name}")
        return descriptor.input_schema

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise HoundTransportError(f"Hound tool not available: {name}")
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        if not isinstance(result, dict):
            return result
        if result.get("isError"):
            raise HoundTransportError(
                f"Hound tool {name} failed: {self._content_text(result)}"
            )
        structured = result.get("structuredContent")
        if structured is not None:
            return structured
        text = self._content_text(result)
        try:
            return json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return {"content": text}

    def health(self) -> dict[str, Any]:
        return {
            "running": self._process is not None
            and self._process.poll() is None,
            "command": list(self.command),
            "tools": sorted(self._tools),
        }

    @staticmethod
    def _content_text(result: dict[str, Any]) -> str:
        content = result.get("content", [])
        parts: list[str] = []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._write(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )
            while True:
                message = self._read()
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise HoundTransportError(
                        f"MCP {method} error: {message['error']}"
                    )
                return message.get("result")

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        with self._lock:
            self._write(
                {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                }
            )

    def _write(self, payload: dict[str, Any]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise HoundTransportError("Hound transport stdin is unavailable")
        process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _read(self) -> dict[str, Any]:
        process = self._require_process()
        if process.stdout is None:
            raise HoundTransportError("Hound transport stdout is unavailable")
        line = process.stdout.readline()
        if not line:
            stderr = ""
            if process.stderr is not None:
                stderr = process.stderr.read()[-2_000:]
            raise HoundTransportError(
                f"Hound ended before responding. stderr={stderr!r}"
            )
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HoundTransportError(
                f"Invalid JSON-RPC response: {line[:500]!r}"
            ) from exc
        if not isinstance(message, dict):
            raise HoundTransportError("JSON-RPC response must be an object")
        return message

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise HoundTransportError("Hound transport is not started")
        if self._process.poll() is not None:
            raise HoundTransportError("Hound process is not running")
        return self._process


class ToolTransport:
    """Structural base used by tests and alternative MCP harnesses."""

    def tool_schema(self, name: str) -> dict[str, Any]:
        raise NotImplementedError

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError

    def health(self) -> dict[str, Any]:
        raise NotImplementedError
