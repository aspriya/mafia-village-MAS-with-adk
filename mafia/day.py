"""Day phase: Discussion, Voting, DayPhase orchestrator, Execution."""
from __future__ import annotations
from collections import Counter
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from .state import (
    append_public, log_event, write_private, read_private, alive_players,
)
from .players import create_player
from .night import call_player, format_public, parse_single, state_sync_event


def _summarise_private(role: str, priv: dict) -> str:
    """Compact view of a player's private memory for their prompt."""
    bits: list[str] = [f"Your role: {role}"]
    if role == "wolf":
        chat = priv.get("wolf_chat", [])
        bits.append("Wolf chat history: " +
                    ("; ".join(chat[-10:]) if chat else "(empty)"))
    if role == "seer":
        invs = priv.get("investigations", [])
        bits.append("Investigations: " +
                    (", ".join(f"{i['target']}={i['result']}" for i in invs)
                     if invs else "(none)"))
    if role == "doctor":
        saves = priv.get("saves", [])
        bits.append("Past saves: " + (", ".join(saves) if saves else "(none)"))
    notes = priv.get("notes", [])
    if notes:
        bits.append("Notes: " + " | ".join(notes[-5:]))
    return "\n".join(bits)


def _player_agent_for(p: dict, state: dict):
    teammates = None
    if p["role"] == "wolf":
        teammates = [w["name"] for w in alive_players(state)
                     if w["role"] == "wolf" and w["name"] != p["name"]]
    return create_player(p["name"], p["role"], teammates=teammates)


class DiscussionAgent(BaseAgent):
    """Each alive player speaks once, in player-list order."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        for p in alive_players(state):
            priv = read_private(state, p["name"])
            prompt = (
                f"DAY {state['day_number']}. You are {p['name']}.\n"
                f"Alive players: {', '.join(q['name'] for q in alive_players(state))}\n"
                f"Your private notes:\n{_summarise_private(p['role'], priv)}\n\n"
                f"PUBLIC LOG (recent):\n{format_public(state)}\n\n"
                "Task: SPEAK. Share your suspicions or defend yourself."
            )
            agent = _player_agent_for(p, state)
            reply = await call_player(agent, prompt)
            state[f"{p['name']}_response"] = reply
            speech = reply.strip().splitlines()[0] if reply.strip() else "(silent)"
            append_public(state, f"{p['name']}: {speech}")
            write_private(state, p["name"], "last_reasoning", reply)
            write_private(state, p["name"], "last_action", "spoke in discussion")
            # Per-speech sync — makes the Village Square scroll in real time.
            yield state_sync_event(state, self.name)


class VotingAgent(BaseAgent):
    """Each alive player privately votes; the tally is announced publicly."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        state["votes"] = {}
        alive_names = [p["name"] for p in alive_players(state)]
        for p in alive_players(state):
            priv = read_private(state, p["name"])
            choices = [n for n in alive_names if n != p["name"]]
            prompt = (
                f"DAY {state['day_number']} VOTE. You are {p['name']}.\n"
                f"You may vote for any alive player except yourself: {', '.join(choices)}\n"
                f"Your private notes:\n{_summarise_private(p['role'], priv)}\n\n"
                f"PUBLIC LOG (recent):\n{format_public(state)}\n\n"
                "Reply EXACTLY:\nVOTE: <player_name>\nREASON: <one short sentence>"
            )
            agent = _player_agent_for(p, state)
            reply = await call_player(agent, prompt)
            state[f"{p['name']}_response"] = reply
            target = parse_single(reply, "VOTE", choices)
            state["votes"][p["name"]] = target
            write_private(state, p["name"], "last_reasoning", reply)
            write_private(state, p["name"], "last_action", f"voted for {target}")
            yield state_sync_event(state, self.name)

        tally = Counter(state["votes"].values())
        ranked = tally.most_common()
        winner, count = ranked[0]
        # Tie? No execution today.
        if len(ranked) > 1 and ranked[1][1] == count:
            append_public(state,
                          f"The vote was tied. No one is executed today. Tally: {dict(tally)}")
            log_event(state, f"Vote tied — no execution. {dict(tally)}")
            state["votes"]["__result__"] = None
        else:
            append_public(state,
                          f"The village voted to execute {winner}. Tally: {dict(tally)}")
            log_event(state, f"Vote: {winner} gets {count} votes. {dict(tally)}")
            state["votes"]["__result__"] = winner
        yield state_sync_event(state, self.name)


class ExecutionAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        target = state["votes"].get("__result__")
        if target is None:
            yield state_sync_event(state, self.name)
            return
        for p in state["players"]:
            if p["name"] == target:
                p["alive"] = False
                append_public(state, f"{target} was a {p['role']}.")
                log_event(state, f"{target} executed (was {p['role']}).")
        yield state_sync_event(state, self.name)


class DayPhaseAgent(BaseAgent):
    def __init__(self, name: str = "DayPhaseAgent"):
        super().__init__(
            name=name,
            sub_agents=[
                DiscussionAgent(name="DiscussionAgent"),
                VotingAgent(name="VotingAgent"),
            ],
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        state["phase"] = "day"
        log_event(state, f"--- Day {state['day_number']} begins ---")
        # Sync the phase change so the UI labels the new day immediately.
        yield state_sync_event(state, self.name)
        for sub in self.sub_agents:
            async for ev in sub.run_async(ctx):
                yield ev
