"""Schema + tiny helpers for the shared whiteboard.

The runner stores everything under `session.state`. Custom agents read
and mutate this dict in place; LlmAgents only ever see the slice we
manually compose into their prompts.
"""
from __future__ import annotations
from typing import Any, Literal, TypedDict

Role = Literal["villager", "wolf", "seer", "doctor"]


class PlayerInfo(TypedDict):
    name: str
    role: Role
    alive: bool


def init_state(players: list[PlayerInfo]) -> dict[str, Any]:
    """Build the initial state dict the runner will start with."""
    return {
        "players": players,
        "public_log": [],
        "private_memory": {p["name"]: {} for p in players},
        "day_number": 0,
        "phase": "setup",
        "night_action": {"wolf_target": None, "doctor_save": None, "seer_check": None},
        "votes": {},
        "winner": None,
        "events": [],   # moderator log — for the UI only, never fed to any agent
    }


def append_public(state: dict[str, Any], line: str) -> None:
    """Anything in public_log will appear in every agent's prompt."""
    state["public_log"].append(line)


def log_event(state: dict[str, Any], line: str) -> None:
    """The moderator log is for humans; agents never read it."""
    state["events"].append(line)


def write_private(state: dict[str, Any], player: str, key: str, value: Any) -> None:
    """Set one slot in one player's private memory."""
    state["private_memory"].setdefault(player, {})[key] = value


def read_private(state: dict[str, Any], player: str) -> dict[str, Any]:
    """Read one player's private memory — used when composing their prompt."""
    return state["private_memory"].get(player, {})


def alive_players(state: dict[str, Any]) -> list[PlayerInfo]:
    return [p for p in state["players"] if p["alive"]]


def players_with_role(state: dict[str, Any], role: Role) -> list[PlayerInfo]:
    return [p for p in state["players"] if p["role"] == role and p["alive"]]
