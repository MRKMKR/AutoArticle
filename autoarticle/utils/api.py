#!/usr/bin/env python3
"""
Shared API utilities for AutoArticle.
All LLM calls go through here — single place to configure headers, base URL, and provider.
"""
import json
import re

import httpx
from autoarticle.utils.config import load_config


def api_post(
    prompt: str,
    system: str = "",
    model: str = "",
    max_tokens: int = 1536,
) -> str:
    """
    Make an LLM API call. Returns response text.

    Provider is determined by AUTOARTICLE_PROVIDER env var:
    - "anthropic" (default): api.anthropic.com, x-api-key header, no system prompt
    - "zai"/"zhipu": api.z.ai/api/paas/v4, api-key header, system becomes meta prompt

    For ZAI, system prompt is prepended to user message with [200] markers.
    """
    config = load_config()

    if model:
        effective_model = model
    else:
        effective_model = config.writer_model

    base_url = config.api_base_url.rstrip("/")
    api_key = config.anthropic_api_key

    headers = {
        "content-type": "application/json",
    }

    # Detect provider from base URL
    is_zai = "z.ai" in base_url or "zhipu" in base_url.lower()

    if is_zai:
        # ZAI uses Authorization: Bearer
        headers["Authorization"] = f"Bearer {api_key}"
        endpoint = f"{base_url}/chat/completions"
        if system:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        else:
            messages = [{"role": "user", "content": prompt}]
        body_json = {
            "model": effective_model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
    else:
        # Anthropic: /v1/messages
        endpoint = f"{base_url}/messages"
        headers["anthropic-version"] = "2023-06-01"
        headers["x-api-key"] = api_key
        if system:
            body_json = {
                "model": effective_model,
                "messages": [
                    {"role": "user", "content": f"{system}\n\n{prompt}"},
                ],
                "max_tokens": max_tokens,
            }
        else:
            body_json = {
                "model": effective_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            }

    client = httpx.Client(timeout=120)
    response = client.post(endpoint, headers=headers, json=body_json)

    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} {response.text}")

    raw = response.text

    # Strip markdown code fences (ZAI wraps responses in ```json ... ```)
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()

    # Handle different response formats
    if '"content":' in raw and '"text":' in raw:
        # Anthropic format: {"content": [{"text": "..."}]}
        data = json.loads(raw)
        return data["content"][0]["text"]
    else:
        # OpenAI-compatible format (ZAI, OpenAI, etc.)
        data = json.loads(raw)
        if isinstance(data, dict) and "choices" in data:
            content = data["choices"][0]["message"]["content"]
            # Strip markdown fences from content (ZAI sometimes wraps in ```json ... ```)
            content = re.sub(r"^```json\s*", "", content)
            content = re.sub(r"```\s*$", "", content)
            return content.strip()
        return str(data)
