"""A 30-second sanity check: can we talk to Gemini through ADK?"""
import asyncio
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

load_dotenv()

hello_agent = LlmAgent(
    name="HelloAgent",
    model="gemini-flash-latest",
    instruction="You are a friendly greeter. Reply in one sentence.",
)


async def main() -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="smoke", user_id="u1", session_id="s1", state={}
    )
    runner = Runner(
        agent=hello_agent, app_name="smoke", session_service=session_service
    )
    message = types.Content(role="user", parts=[types.Part(text="Say hi to my class.")])
    async for event in runner.run_async(
        user_id="u1", session_id="s1", new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{event.author}] {part.text}")


if __name__ == "__main__":
    asyncio.run(main())
