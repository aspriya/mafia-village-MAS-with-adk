"""Night phase: parsers, call_player, then the four night agents.

We build this file in five small steps. After each step you can run a
matching smoke test from the mafia-village/ folder.
"""
from __future__ import annotations
from collections import Counter
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

from .state import (
    append_public, log_event, write_private, read_private,
    alive_players, players_with_role,
)
from .players import create_player


# ---------- Step 4.0: the state-sync helper ----------

def state_sync_event(state: dict, author: str) -> Event:
    """Emit an Event that pushes the entire current local state to the
    SessionService via `state_delta`.

    Why this exists: ADK's `InMemorySessionService.get_session()` returns a
    `copy.deepcopy()` of the stored session. So `ctx.session.state` inside a
    custom `BaseAgent` is a *copy* — direct mutations live only in the local
    invocation. The Runner's `append_event` is what commits values from
    `event.actions.state_delta` back into the stored session.

    Without these events, our Streamlit UI (which polls
    `sess.get_session(...).state`) would only ever see the initial state, and
    the smoke tests that read state after `run_async()` finishes would see
    empty dicts. The whole state is small for this toy game, so we just push
    a snapshot of it; in larger systems you'd push only the keys you changed.
    """
    return Event(
        author=author,
        actions=EventActions(state_delta=dict(state)),
    )


# ---------- Step 4.1: parsing + LLM helpers ----------

def format_public(state: dict, n: int = 30) -> str:
    """Render the last n public log lines for inclusion in a prompt."""
    return "\n".join(state["public_log"][-n:]) or "(no public events yet)"


def find_field(reply: str, field: str, valid: list[str] | None = None) -> str | None:
    """Find a 'FIELD: value' line in `reply`, tolerating common markdown.

    Returns the value if found (and valid if `valid` is given), else None.
    Examples it handles:
        TARGET: Bandara
        **TARGET:** Bandara
        > TARGET: Bandara.
        - target: Bandara,
    """
    needle = field.upper() + ":"
    for line in reply.splitlines():
        # Strip leading/trailing markdown decoration.
        s = line.strip().lstrip("*#>- ").rstrip("*").strip()
        if s.upper().startswith(needle):
            value = s.split(":", 1)[1].strip().rstrip("*.,;:").strip()
            if valid is None or value in valid:
                return value
    return None


def first_match(text: str, valid: list[str]) -> str:
    """Fuzzy fallback: first valid name that appears anywhere in `text`."""
    for v in valid:
        if v in text:
            return v
    return valid[0]


def parse_single(reply: str, field: str, valid: list[str]) -> str:
    """Robustly extract one valid name for `field`. Never raises."""
    return find_field(reply, field, valid) or first_match(reply, valid)


def parse_wolf_reply(reply: str, valid_targets: list[str]) -> tuple[str, str]:
    """Wolves return two fields: MSG and TARGET."""
    msg = find_field(reply, "MSG") or "(no message)"
    target = find_field(reply, "TARGET", valid_targets) or first_match(reply, valid_targets)
    return msg, target


async def call_player(player_agent: LlmAgent, prompt: str,
                      app_name: str = "mafia-sub") -> str:
    """Run a single LlmAgent once with a custom prompt; return its final text.

    Each call lives in its own throwaway Runner + Session — keeping the
    outer game session clean of stray LlmAgent invocations.
    """
    sess = InMemorySessionService()
    await sess.create_session(app_name=app_name, user_id="u", session_id="s", state={})
    runner = Runner(agent=player_agent, app_name=app_name, session_service=sess)
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    out = ""
    async for ev in runner.run_async(user_id="u", session_id="s", new_message=msg):
        if ev.is_final_response() and ev.content:
            for part in ev.content.parts:
                if part.text:
                    out += part.text
    return out


# ---------- Step 4.2: SeerAgent ----------

class SeerAgent(BaseAgent):
    """Picks one player to investigate; learns their true role secretly."""

    async def _run_async_impl(
        self, ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        seers = players_with_role(state, "seer")
        if not seers:
            # No seer in this game — nothing to do. Still must yield so the
            # method is recognised as an async generator.
            yield state_sync_event(state, self.name)
            return
        seer = seers[0]
        targets = [p["name"] for p in alive_players(state) if p["name"] != seer["name"]]
        priors = read_private(state, seer["name"]).get("investigations", [])

        prompt = (
            f"NIGHT {state['day_number']}. You are the Seer. Pick ONE player to investigate.\n"
            f"Alive players (excluding you): {', '.join(targets)}\n"
            f"Past investigations: {priors or '(none)'}\n\n"
            f"PUBLIC LOG (recent):\n{format_public(state)}\n\n"
            "Reply on ONE line:\nINVESTIGATE: <player_name>"
        )
        agent = create_player(seer["name"], "seer")
        reply = await call_player(agent, prompt)
        state[f"{seer['name']}_response"] = reply

        target = parse_single(reply, "INVESTIGATE", targets)
        truth = next(p["role"] for p in state["players"] if p["name"] == target)
        result = "wolf" if truth == "wolf" else "not a wolf"

        priors.append({"target": target, "result": result})
        write_private(state, seer["name"], "investigations", priors)
        write_private(state, seer["name"], "last_reasoning", reply)
        write_private(state, seer["name"], "last_action",
                      f"investigated {target} → {result}")
        state["night_action"]["seer_check"] = {"target": target, "result": result}
        log_event(state, f"Seer investigated {target}: {result}.")
        # Commit our mutations to the session storage so the UI can see them.
        yield state_sync_event(state, self.name)


# ---------- Step 4.3: DoctorAgent ----------

class DoctorAgent(BaseAgent):
    """Picks one alive player to protect tonight."""

    async def _run_async_impl(
        self, ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        docs = players_with_role(state, "doctor")
        if not docs:
            yield state_sync_event(state, self.name)
            return
        doc = docs[0]
        targets = [p["name"] for p in alive_players(state)]
        priors = read_private(state, doc["name"]).get("saves", [])

        prompt = (
            f"NIGHT {state['day_number']}. You are the Doctor. Pick ONE alive player to protect tonight.\n"
            f"You may protect yourself. Past saves: {priors or '(none)'}\n"
            f"Alive players: {', '.join(targets)}\n\n"
            f"PUBLIC LOG (recent):\n{format_public(state)}\n\n"
            "Reply on ONE line:\nPROTECT: <player_name>"
        )
        agent = create_player(doc["name"], "doctor")
        reply = await call_player(agent, prompt)
        state[f"{doc['name']}_response"] = reply

        save = parse_single(reply, "PROTECT", targets)
        priors.append(save)
        write_private(state, doc["name"], "saves", priors)
        write_private(state, doc["name"], "last_reasoning", reply)
        write_private(state, doc["name"], "last_action", f"protected {save}")
        state["night_action"]["doctor_save"] = save
        log_event(state, f"Doctor chose to protect {save}.")
        yield state_sync_event(state, self.name)


# ---------- Step 4.4: WolvesAgent ----------

class WolvesAgent(BaseAgent):
    """Each alive wolf adds a message + a target proposal to a private chat.
    The majority proposal wins."""

    async def _run_async_impl(
        self, ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        wolves = players_with_role(state, "wolf")
        alive_targets = [p["name"] for p in alive_players(state) if p["role"] != "wolf"]
        if not wolves or not alive_targets:
            yield state_sync_event(state, self.name)
            return

        chat: list[str] = []
        proposals: list[str] = []
        teammates_by_wolf = {
            w["name"]: [o["name"] for o in wolves if o["name"] != w["name"]]
            for w in wolves
        }

        for wolf in wolves:
            wolf_agent = create_player(
                wolf["name"], "wolf",
                teammates=teammates_by_wolf[wolf["name"]],
            )
            mates = teammates_by_wolf[wolf["name"]]
            prompt = (
                f"NIGHT {state['day_number']}. You and your teammates "
                f"({', '.join(mates) if mates else 'none'}) "
                f"must pick ONE non-wolf to eliminate.\n\n"
                f"Alive non-wolves: {', '.join(alive_targets)}\n\n"
                "Wolf chat so far:\n" +
                ("\n".join(chat) if chat else "(empty)") +
                f"\n\nPUBLIC LOG (recent):\n{format_public(state)}\n\n"
                "Reply on TWO lines exactly:\n"
                "MSG: <one sentence to your teammates>\n"
                "TARGET: <one name from the alive non-wolves list>"
            )
            reply = await call_player(wolf_agent, prompt)
            state[f"{wolf['name']}_response"] = reply

            msg, target = parse_wolf_reply(reply, alive_targets)
            chat.append(f"{wolf['name']}: {msg} (→ {target})")
            proposals.append(target)
            write_private(state, wolf["name"], "last_reasoning", reply)
            write_private(state, wolf["name"], "last_action",
                          f"proposed killing {target}")
            # Per-wolf sync — lets the Peek panel show each wolf's reasoning
            # the moment it lands, instead of waiting for all wolves.
            yield state_sync_event(state, self.name)

        # Majority wins; Counter.most_common breaks ties by first proposal.
        winning_target = Counter(proposals).most_common(1)[0][0]
        state["night_action"]["wolf_target"] = winning_target

        # Mirror the wolf chat into every wolf's private memory so they
        # can refer to it on later nights.
        for wolf in wolves:
            existing = read_private(state, wolf["name"]).get("wolf_chat", [])
            write_private(state, wolf["name"], "wolf_chat", existing + chat)

        log_event(state, f"Wolves agreed to attack {winning_target}.")
        yield state_sync_event(state, self.name)


# ---------- Step 4.5: NightPhaseAgent + DeathResolverAgent ----------

class NightPhaseAgent(BaseAgent):
    """Bumps day_number, then runs Wolves → Seer → Doctor, then dawn."""

    def __init__(self, name: str = "NightPhaseAgent"):
        super().__init__(
            name=name,
            sub_agents=[
                WolvesAgent(name="WolvesAgent"),
                SeerAgent(name="SeerAgent"),
                DoctorAgent(name="DoctorAgent"),
            ],
        )

    async def _run_async_impl(
        self, ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        state["day_number"] += 1
        state["phase"] = "night"
        state["night_action"] = {
            "wolf_target": None, "doctor_save": None, "seer_check": None,
        }
        log_event(state, f"--- Night {state['day_number']} begins ---")
        # Sync the day-number / phase bump so the UI sees them immediately.
        yield state_sync_event(state, self.name)
        for sub in self.sub_agents:
            async for ev in sub.run_async(ctx):
                yield ev
        append_public(state, f"Night {state['day_number']} has passed. Dawn breaks.")
        yield state_sync_event(state, self.name)


class DeathResolverAgent(BaseAgent):
    """Pure Python: apply the wolves' kill unless the doctor saved the target."""

    async def _run_async_impl(
        self, ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        target = state["night_action"]["wolf_target"]
        save = state["night_action"]["doctor_save"]
        if target is None:
            append_public(state, "No one was attacked last night.")
        elif target == save:
            append_public(state, f"The wolves attacked {target}, but the Doctor saved them!")
            log_event(state, f"{target} was attacked but saved.")
        else:
            for p in state["players"]:
                if p["name"] == target:
                    p["alive"] = False
            append_public(state, f"{target} was found dead this morning.")
            log_event(state, f"{target} died (wolf attack).")
        yield state_sync_event(state, self.name)
