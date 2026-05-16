"""Run a full Mafia game in the terminal — no UI, just the transcript."""
import asyncio
import json
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from rich.console import Console
from rich.table import Table

from mafia.state import init_state
from mafia.game import build_game

load_dotenv()
console = Console()


async def main() -> None:
    players = [
        {"name": "Aruna",   "role": "wolf",     "alive": True},
        {"name": "Nimal",   "role": "wolf",     "alive": True},
        {"name": "Seetha",  "role": "seer",     "alive": True},
        {"name": "Kamala",  "role": "doctor",   "alive": True},
        {"name": "Bandara", "role": "villager", "alive": True},
        {"name": "Chathura","role": "villager", "alive": True},
        {"name": "Dilani",  "role": "villager", "alive": True},
    ]
    state = init_state(players)
    sess = InMemorySessionService()
    await sess.create_session(app_name="m", user_id="u", session_id="s", state=state)
    runner = Runner(agent=build_game(), app_name="m", session_service=sess)
    async for _ in runner.run_async(
        user_id="u", session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text="play")]),
    ):
        pass

    s = (await sess.get_session(app_name="m", user_id="u", session_id="s")).state

    console.rule("[bold]Public log[/bold]")
    for line in s["public_log"]:
        console.print(" •", line)
    console.rule("[bold]Moderator events[/bold]")
    for line in s["events"]:
        console.print(" •", line, style="dim")
    console.rule("[bold]Final standings[/bold]")
    t = Table("Name", "Role", "Alive")
    for p in s["players"]:
        t.add_row(p["name"], p["role"], "✅" if p["alive"] else "💀")
    console.print(t)
    console.print(f"\n[bold green]Winner:[/bold green] {s['winner']}")

    with open("last_game.json", "w") as f:
        json.dump(s, f, indent=2, default=str)
    console.print("\nFull transcript written to [bold]last_game.json[/bold]")


if __name__ == "__main__":
    asyncio.run(main())
