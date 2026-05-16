"""Step 4.4 check — confirm two wolves negotiate and converge on one target."""
import asyncio
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from rich import print as rprint

from mafia.state import init_state
from mafia.night import WolvesAgent

load_dotenv()


async def main() -> None:
    players = [
        {"name": "Aruna",   "role": "wolf",     "alive": True},
        {"name": "Nimal",   "role": "wolf",     "alive": True},
        {"name": "Seetha",  "role": "villager", "alive": True},
        {"name": "Bandara", "role": "villager", "alive": True},
        {"name": "Kamala",  "role": "villager", "alive": True},
    ]
    state = init_state(players)
    state["day_number"] = 1
    sess = InMemorySessionService()
    await sess.create_session(app_name="m", user_id="u", session_id="s", state=state)
    runner = Runner(agent=WolvesAgent(name="WolvesAgent"),
                    app_name="m", session_service=sess)
    async for _ in runner.run_async(
        user_id="u", session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text="night")]),
    ):
        pass

    s = (await sess.get_session(app_name="m", user_id="u", session_id="s")).state
    rprint("Wolf target:", s["night_action"]["wolf_target"])
    rprint("Wolf chat (Aruna sees):", s["private_memory"]["Aruna"].get("wolf_chat"))


if __name__ == "__main__":
    asyncio.run(main())
