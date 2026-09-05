"""Shared types for HarnessTest."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class KillChainStage(str, Enum):
    INJECTION_INGESTED = "injection_ingested"
    OBJECTIVE_CHANGED = "objective_changed"
    TOOL_INVOKED = "tool_invoked"
    SECRET_READ = "secret_read"
    EGRESS_ATTEMPTED = "egress_attempted"
    EGRESS_SUCCEEDED = "egress_succeeded"
    PLUGIN_ESCALATION = "plugin_escalation"
    NONE = "none"


STAGE_ORDER: list[KillChainStage] = [
    KillChainStage.INJECTION_INGESTED,
    KillChainStage.OBJECTIVE_CHANGED,
    KillChainStage.TOOL_INVOKED,
    KillChainStage.SECRET_READ,
    KillChainStage.EGRESS_ATTEMPTED,
    KillChainStage.EGRESS_SUCCEEDED,
    KillChainStage.PLUGIN_ESCALATION,
]


class ScoreDimension(str, Enum):
    ATTACK_RECOGNITION = "attack_recognition"
    TOOL_INVOCATION = "tool_invocation"
    POLICY_BLOCK = "policy_block"
    PRIVILEGE_AVAILABLE = "privilege_available"
    DATA_EXPOSURE = "data_exposure"
    NETWORK_EGRESS = "network_egress"
    PERSISTENCE = "persistence"
    HUMAN_APPROVAL = "human_approval"
    ISOLATION = "isolation"
    RECOVERY = "recovery"


class Profile(str, Enum):
    DEFAULT = "default"
    HARDENED = "hardened"


class AttackId(str, Enum):
    KILL_CHAIN = "kill_chain"
    INDIRECT_PROMPT_INJECTION = "indirect_prompt_injection"
    SECRET_EXFIL = "secret_exfil"
    NETWORK_EGRESS = "network_egress"
    CREDENTIAL_BOUNDARY = "credential_boundary"
    PLUGIN_SUPPLY_CHAIN = "plugin_supply_chain"


class MonitorEvent(BaseModel):
    kind: str
    detail: str
    path: str | None = None
    destination: str | None = None
    secret_id: str | None = None
    timestamp: float | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class DimensionScore(BaseModel):
    dimension: ScoreDimension
    score: int = Field(ge=0, le=5)
    evidence: str = ""
    observed: bool = True


class AttackResult(BaseModel):
    attack: AttackId
    harness: str
    profile: Profile
    model: str | None = None
    first_stop_stage: KillChainStage = KillChainStage.NONE
    stages_reached: list[KillChainStage] = Field(default_factory=list)
    dimensions: list[DimensionScore] = Field(default_factory=list)
    monitor_events: list[MonitorEvent] = Field(default_factory=list)
    trajectory_path: str | None = None
    notes: str = ""
    error: str | None = None
    live: bool = True


class Scorecard(BaseModel):
    version: str = "0.1.0"
    model_backend: str = "unknown"
    model_name: str | None = None
    results: list[AttackResult] = Field(default_factory=list)

    def matrix(self) -> dict[str, dict[str, dict[str, dict[str, int]]]]:
        """harness → profile → attack → dimension → score.

        Profiles are never collapsed: default and hardened remain separate so
        last-write-wins cannot hide posture differences.

        Includes live runs even when the process exited non-zero (e.g. timeout)
        as long as dimensions were scored from the trajectory. Skips unavailable
        / non-live rows and rows with no dimension scores.
        """
        out: dict[str, dict[str, dict[str, dict[str, int]]]] = {}
        for r in self.results:
            if not r.live or not r.dimensions:
                continue
            h = out.setdefault(r.harness, {})
            p = h.setdefault(r.profile.value, {})
            a = p.setdefault(r.attack.value, {})
            for d in r.dimensions:
                a[d.dimension.value] = d.score
        return out
