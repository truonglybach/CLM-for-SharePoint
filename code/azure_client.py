"""
azure_client.py (v2)
Thin wrapper around Azure OpenAI Structured Outputs.
"""
from __future__ import annotations
import copy
import json
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel
from config import settings

T = TypeVar("T", bound=BaseModel)
_AOAI_SCOPE = "https://cognitiveservices.azure.com/.default"
_client = None

def to_strict_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    "Pydantic model -> strict JSON Schema accepted by Structured Outputs."
    schema = copy.deepcopy(model.model_json_schema())
    _strictify(schema)
    return schema

def _strictify(node: Any) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        if node.get("type") == "object" or "properties" in node:
            props = node.get("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(props.keys())
        for value in node.values():
            _strictify(value)
    elif isinstance(node, list):
        for item in node:
            _strictify(item)

def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from openai import AzureOpenAI
    except ImportError as exc:
        raise RuntimeError("pip install openai for the Azure OpenAI client.") from exc
    if not settings.azure_openai_endpoint:
        raise RuntimeError("Set AZURE_OPENAI_ENDPOINT.")
    if settings.azure_openai_api_key:
        # Explicit key = local-dev opt-in, mirroring the client-secret fallback in auth.py.
        _client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        return _client
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError as exc:
        raise RuntimeError(
            "pip install azure-identity for Entra ID auth, or set AZURE_OPENAI_API_KEY."
        ) from exc
    _client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(), _AOAI_SCOPE),
        api_version=settings.azure_openai_api_version,
    )
    return _client

def _call(model: Type[T], system: str, user: str, deployment: str,
          temperature: Optional[float] = 0.0) -> T:
    client = _get_client()
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": model.__name__, "schema": to_strict_schema(model), "strict": True},
    }
    kwargs: Dict[str, Any] = {
        "model": deployment,
        "response_format": response_format,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0].message
    if getattr(choice, "refusal", None):
        raise RuntimeError(f"Model refused: {choice.refusal}")
    return model.model_validate(json.loads(choice.content))

def extract(model: Type[T], system: str, user: str) -> T:
    return _call(model, system, user, settings.azure_openai_deployment_extract, temperature=0.0)

def judge(model: Type[T], system: str, user: str) -> T:
    return _call(model, system, user, settings.azure_openai_deployment_judge, temperature=None)

def which_models() -> Dict[str, Optional[str]]:
    return {"extract": settings.azure_openai_deployment_extract, "judge": settings.azure_openai_deployment_judge}

def map_terms(model, system, user):
    return extract(model, system, user)
