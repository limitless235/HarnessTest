"""Harness adapter protocol and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harnesstest.models import AttackId, Profile


@dataclass
class RunRequest:
    attack: AttackId
    profile: Profile
    workspace: Path
    egress_url: str
    task_prompt: str
    model: str | None = None
    timeout_sec: int = 300
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResponse:
    trajectory_text: str = ""
    trajectory_path: Path | None = None
    policy_denials: list[str] = field(default_factory=list)
    approval_required: bool | None = None
    model: str | None = None
    notes: str = ""
    error: str | None = None
    live: bool = True
    raw_events: list[dict[str, Any]] = field(default_factory=list)


class HarnessAdapter(ABC):
    name: str

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        ...

    @abstractmethod
    def prepare(self, req: RunRequest) -> None:
        ...

    @abstractmethod
    def run(self, req: RunRequest) -> RunResponse:
        ...


_REGISTRY: dict[str, type[HarnessAdapter]] = {}


def register(cls: type[HarnessAdapter]) -> type[HarnessAdapter]:
    _REGISTRY[cls.name] = cls
    return cls


def get_adapter(name: str) -> HarnessAdapter:
    if name not in _REGISTRY:
        _load_all()
    if name not in _REGISTRY:
        raise KeyError(f"unknown harness adapter: {name}. known={sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def list_adapters() -> list[str]:
    _load_all()
    return sorted(_REGISTRY)


def _load_all() -> None:
    from harnesstest.harnesses import deepseek, hermes, local, nemoclaw, openclaw  # noqa: F401
