"""Win check + the full game agent tree."""
from __future__ import annotations
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, SequentialAgent, LoopAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from .state import append_public, log_event, alive_players, players_with_role
from .night import NightPhaseAgent, DeathResolverAgent, state_sync_event
from .day import DayPhaseAgent, ExecutionAgent


class WinConditionChecker(BaseAgent):
    """End game if wolves are gone, or if wolves >= non-wolves alive."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        wolves = len(players_with_role(state, "wolf"))
        non_wolves = len(alive_players(state)) - wolves
        winner = None
        if wolves == 0:
            winner = "villagers"
        elif wolves >= non_wolves:
            winner = "wolves"
        if winner:
            state["winner"] = winner
            append_public(state, f"GAME OVER. The {winner} win!")
            log_event(state, f"Game over: {winner} win.")
            # Final state-sync so the UI sees the winner + dead players.
            yield state_sync_event(state, self.name)
            # escalate=True tells the enclosing LoopAgent to stop.
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            # Game continues — still sync so any cumulative state from this
            # round (e.g. logged events) reaches the storage session.
            yield state_sync_event(state, self.name)


def build_round_agent() -> SequentialAgent:
    return SequentialAgent(
        name="RoundAgent",
        sub_agents=[
            NightPhaseAgent(),
            DeathResolverAgent(name="DeathResolverAgent"),
            DayPhaseAgent(),
            ExecutionAgent(name="ExecutionAgent"),
            WinConditionChecker(name="WinConditionChecker"),
        ],
    )


def build_game(max_rounds: int = 20) -> LoopAgent:
    return LoopAgent(
        name="GameLoopAgent",
        sub_agents=[build_round_agent()],
        max_iterations=max_rounds,
    )
