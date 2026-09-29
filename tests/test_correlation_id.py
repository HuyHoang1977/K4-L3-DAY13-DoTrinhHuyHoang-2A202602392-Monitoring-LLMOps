from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest

from app import logging_config
from app.middleware import new_request_id
from app.main import app

REQUEST_ID_RE = re.compile(r"^req-[0-9a-f]{8}$")


async def _post(payload: dict, headers: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/chat", json=payload, headers=headers or {})


def _events(log_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_generated_request_id_format() -> None:
    for _ in range(20):
        assert REQUEST_ID_RE.match(new_request_id())


def test_chat_echoes_generated_correlation_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    response = asyncio.run(
        _post(
            {
                "user_id": "student-01",
                "session_id": "session-01",
                "feature": "qa",
                "message": "Explain observability",
            }
        )
    )

    assert response.status_code == 200
    correlation_id = response.headers["x-request-id"]
    assert REQUEST_ID_RE.match(correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert int(response.headers["x-response-time-ms"]) >= 0


def test_inbound_request_id_is_reused(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    response = asyncio.run(
        _post(
            {
                "user_id": "student-01",
                "session_id": "session-01",
                "message": "hello",
            },
            headers={"x-request-id": "req-abcdef12"},
        )
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-abcdef12"
    assert response.json()["correlation_id"] == "req-abcdef12"


def test_unsafe_inbound_request_id_is_replaced(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    response = asyncio.run(
        _post(
            {"user_id": "u", "session_id": "s", "message": "hi"},
            headers={"x-request-id": "bad id with spaces and \r\n injections"},
        )
    )

    assert response.status_code == 200
    assert REQUEST_ID_RE.match(response.headers["x-request-id"])


def test_context_does_not_leak_between_requests(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send() -> list[httpx.Response]:
        first = await _post(
            {
                "user_id": "student-01",
                "session_id": "session-01",
                "feature": "refund",
                "model": "gpt-x",
                "message": "first",
            }
        )
        second = await _post(
            {"user_id": "student-02", "session_id": "session-02", "message": "second"}
        )
        return [first, second]

    first, second = asyncio.run(send())
    assert first.headers["x-request-id"] != second.headers["x-request-id"]

    by_id = {event["correlation_id"]: event for event in _events(log_path)}
    assert set(by_id) == {first.headers["x-request-id"], second.headers["x-request-id"]}

    assert by_id[first.headers["x-request-id"]]["user_id_hash"] != (
        by_id[second.headers["x-request-id"]]["user_id_hash"]
    )
    # The second request must not inherit the first request's model/feature.
    assert by_id[first.headers["x-request-id"]]["model"] == "gpt-x"
    assert by_id[first.headers["x-request-id"]]["feature"] == "refund"
    assert by_id[second.headers["x-request-id"]]["feature"] == "qa"


def test_every_api_log_line_carries_context_and_scrubbed_payload(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    response = asyncio.run(
        _post(
            {
                "user_id": "student-01",
                "session_id": "session-01",
                "feature": "refund",
                "model": "gpt-x",
                "message": "email me at student@vinuni.edu.vn or 0901234567",
            }
        )
    )
    assert response.status_code == 200

    correlation_id = response.headers["x-request-id"]
    required = {"ts", "level", "service", "event", "correlation_id"}
    enrichment = {"user_id_hash", "session_id", "feature", "model", "env"}

    events = [e for e in _events(log_path) if e.get("service") == "api"]
    assert events
    for event in events:
        assert required.issubset(event)
        assert enrichment.issubset(event)
        assert event["correlation_id"] == correlation_id

    raw = log_path.read_text(encoding="utf-8")
    assert "student@vinuni.edu.vn" not in raw
    assert "0901234567" not in raw
    assert "REDACTED_EMAIL" in raw


@pytest.mark.parametrize("path", ["/health", "/metrics"])
def test_non_chat_endpoints_also_get_headers(path: str) -> None:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    response = asyncio.run(send())
    assert response.status_code == 200
    assert REQUEST_ID_RE.match(response.headers["x-request-id"])
    assert "x-response-time-ms" in response.headers
