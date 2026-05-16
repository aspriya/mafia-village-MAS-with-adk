"""Step 4.1 check — one LlmAgent, one prompt, one reply, parsed cleanly."""
import asyncio
from dotenv import load_dotenv
from mafia.players import create_player
from mafia.night import call_player, parse_single

load_dotenv()


async def main() -> None:
    aruna = create_player("Aruna", "villager")
    reply = await call_player(
        aruna,
        "Alive players: Aruna, Nimal, Seetha.\n"
        "Task: SPEAK in one sentence about who you suspect.\n"
        "Then on a new line write VOTE: <name>.",
    )
    print("RAW REPLY:\n", reply)
    print("\nParsed vote target:", parse_single(reply, "VOTE", ["Nimal", "Seetha"]))


if __name__ == "__main__":
    asyncio.run(main())
