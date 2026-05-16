"""Step 4.2 check — run SeerAgent against a fixed roster and confirm the
seer's investigation lands in her private memory."""
import asyncio
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from rich import print as rprint

from mafia.state import init_state
from mafia.night import SeerAgent

load_dotenv()


async def main() -> None:
    players = [
        {"name": "Aruna",  "role": "wolf",     "alive": True},
        {"name": "Seetha", "role": "seer",     "alive": True},
        {"name": "Bandara","role": "villager", "alive": True},
    ]
    state = init_state(players)
    state["day_number"] = 1  # pretend night 1 has begun
    sess = InMemorySessionService()
    await sess.create_session(app_name="m", user_id="u", session_id="s", state=state)
    runner = Runner(agent=SeerAgent(name="SeerAgent"),
                    app_name="m", session_service=sess)
    async for _ in runner.run_async(
        user_id="u", session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text="night")]),
    ):
        pass

    s = (await sess.get_session(app_name="m", user_id="u", session_id="s")).state
    rprint("Seetha's private memory:", s["private_memory"]["Seetha"])
    rprint("Night action seer_check:", s["night_action"]["seer_check"])


if __name__ == "__main__":
    asyncio.run(main())
