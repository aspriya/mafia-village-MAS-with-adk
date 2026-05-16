"""Step 5 check — a full round: Night → Resolve → Day → Execute."""
import asyncio
from dotenv import load_dotenv
from google.adk.agents import SequentialAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from rich import print as rprint

from mafia.state import init_state
from mafia.night import NightPhaseAgent, DeathResolverAgent
from mafia.day import DayPhaseAgent, ExecutionAgent

load_dotenv()


async def main() -> None:
    players = [
        {"name": "Aruna", "role": "wolf", "alive": True},
        {"name": "Nimal", "role": "wolf", "alive": True},
        {"name": "Seetha", "role": "seer", "alive": True},
        {"name": "Kamala", "role": "doctor", "alive": True},
        {"name": "Bandara", "role": "villager", "alive": True},
        {"name": "Chathura", "role": "villager", "alive": True},
        {"name": "Dilani", "role": "villager", "alive": True},
    ]
    state = init_state(players)
    root = SequentialAgent(
        name="OneRound",
        sub_agents=[
            NightPhaseAgent(),
            DeathResolverAgent(name="Resolver"),
            DayPhaseAgent(),
            ExecutionAgent(name="Executioner"),
        ],
    )
    sess = InMemorySessionService()
    await sess.create_session(app_name="m", user_id="u", session_id="s", state=state)
    runner = Runner(agent=root, app_name="m", session_service=sess)
    async for _ in runner.run_async(
        user_id="u", session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text="play")]),
    ):
        pass
    s = (await sess.get_session(app_name="m", user_id="u", session_id="s")).state
    rprint("\n[bold green]PUBLIC LOG[/bold green]")
    for line in s["public_log"]:
        rprint(" •", line)
    rprint("\n[bold cyan]EVENTS[/bold cyan]")
    for line in s["events"]:
        rprint(" •", line)
    rprint("\n[bold]Survivors:[/bold]",
           [(p["name"], p["role"]) for p in s["players"] if p["alive"]])


if __name__ == "__main__":
    asyncio.run(main())
