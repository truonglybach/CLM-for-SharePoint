"""Retry behavior of the Azure OpenAI wrapper."""
from __future__ import annotations

import httpx
import openai
import pytest

from clm import azure_client


def _rate_limit_error(retry_after: str | None = None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(429, headers=headers, request=httpx.Request("POST", "https://aoai.test"))
    return openai.RateLimitError("rate limited", response=response, body=None)

def _bad_request_error() -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://aoai.test"))
    return openai.BadRequestError("bad request", response=response, body=None)

class _FlakyClient:
    def __init__(self, failures, result="ok"):
        self.failures = list(failures)
        self.calls = 0
        self.result = result
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return self.result

def test_retries_rate_limit_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(azure_client.time, "sleep", sleeps.append)
    client = _FlakyClient([_rate_limit_error(), _rate_limit_error("7")])
    assert azure_client._create_with_retry(client, {}) == "ok"
    assert client.calls == 3
    assert sleeps == [1.0, 7.0]  # exponential backoff, then honored retry-after header

def test_non_retryable_error_raises_immediately(monkeypatch):
    monkeypatch.setattr(azure_client.time, "sleep", lambda s: pytest.fail("must not sleep"))
    client = _FlakyClient([_bad_request_error()])
    with pytest.raises(openai.BadRequestError):
        azure_client._create_with_retry(client, {})
    assert client.calls == 1

def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(azure_client.time, "sleep", lambda s: None)
    client = _FlakyClient([_rate_limit_error() for _ in range(azure_client._MAX_RETRIES)])
    with pytest.raises(openai.RateLimitError):
        azure_client._create_with_retry(client, {})
    assert client.calls == azure_client._MAX_RETRIES
