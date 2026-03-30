#!/usr/bin/env python3
"""
Configuration loader for AutoArticle.
Reads .env file and provides typed access to config values.
"""
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None  # no-op if dotenv not available


@dataclass
class Config:
    anthropic_api_key: str
    writer_model: str
    judge_model: str
    review_model: str
    api_base_url: str


def load_config() -> Config:
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")

    return Config(
        anthropic_api_key=api_key,
        writer_model=os.getenv("AUTOARTICLE_WRITER_MODEL", "claude-sonnet-4-20250514"),
        judge_model=os.getenv("AUTOARTICLE_JUDGE_MODEL", "claude-sonnet-4-20250514"),
        review_model=os.getenv("AUTOARTICLE_REVIEW_MODEL", "claude-opus-4-20250514"),
        api_base_url=os.getenv("AUTOARTICLE_API_BASE_URL", "https://api.anthropic.com"),
    )
