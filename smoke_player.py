"""Step 3 check — one villager replies to a tiny public log."""
import asyncio
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from mafia.players import create_player

load_dotenv()


async def main() -> None:
    aruna = create_player("Aruna", "villager")
    sess = InMemorySessionService()
    await sess.create_session(app_name="t", user_id="u", session_id="s", state={})
    runner = Runner(agent=aruna, app_name="t", session_service=sess)

    public_log = [
        "Day 1 begins. No one died last night.",
        "Moderator: each of you, please share one suspicion.",
    ]
    prompt = (
        "PUBLIC LOG:\n" + "\n".join(public_log) +
        "\n\nYour private notes: (empty)\n\nTask: SPEAK."
    )
    async for event in runner.run_async(
        user_id="u", session_id="s",
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if part.text:
                    print(f"--- Aruna says ---\n{part.text}\n")


if __name__ == "__main__":
    asyncio.run(main())
