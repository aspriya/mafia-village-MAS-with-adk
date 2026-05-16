"""Step 4.5 check — a full night phase: Wolves → Seer → Doctor → Resolve."""
import asyncio
from dotenv import load_dotenv
from google.adk.agents import SequentialAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from rich import print as rprint

from mafia.state import init_state
from mafia.night import NightPhaseAgent, DeathResolverAgent

load_dotenv()


async def main() -> None:
    players = [
        {"name": "Aruna",   "role": "wolf",     "alive": True},
        {"name": "Nimal",   "role": "wolf",     "alive": True},
        {"name": "Seetha",  "role": "seer",     "alive": True},
        {"name": "Kamala",  "role": "doctor",   "alive": True},
        {"name": "Bandara", "role": "villager", "alive": True},
        {"name": "Chathura","role": "villager", "alive": True},
    ]
    state = init_state(players)
    root = SequentialAgent(
        name="OneNight",
        sub_agents=[NightPhaseAgent(), DeathResolverAgent(name="DeathResolver")],
    )
    sess = InMemorySessionService()
    await sess.create_session(app_name="m", user_id="u", session_id="s", state=state)
    runner = Runner(agent=root, app_name="m", session_service=sess)
    async for _ in runner.run_async(
        user_id="u", session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text="run one night")]),
    ):
        pass

    s = (await sess.get_session(app_name="m", user_id="u", session_id="s")).state
    rprint("[bold]Public log:[/bold]", s["public_log"])
    rprint("[bold]Events:[/bold]",     s["events"])
    rprint("[bold]Alive:[/bold]",      [p["name"] for p in s["players"] if p["alive"]])
    rprint("[bold]Seer private:[/bold]", s["private_memory"]["Seetha"])


if __name__ == "__main__":
    asyncio.run(main())
