"""Simulate one round's-worth of state mutations, then peek at it from
three different players' points of view. Notice how much each one can see."""
from mafia.state import (
    init_state, append_public, log_event,
    write_private, read_private,
)

players = [
    {"name": "Aruna",   "role": "wolf",     "alive": True},
    {"name": "Nimal",   "role": "wolf",     "alive": True},
    {"name": "Seetha",  "role": "seer",     "alive": True},
    {"name": "Kamala",  "role": "doctor",   "alive": True},
    {"name": "Bandara", "role": "villager", "alive": True},
]
state = init_state(players)

# A fake night happens behind the scenes:
append_public(state, "Day 1 begins. The village wakes up.")
log_event(state, "Night 1 — wolves chose Bandara; doctor saved nobody.")
write_private(state, "Aruna",  "wolf_chat",      ["Aruna: Bandara is loud, kill him."])
write_private(state, "Nimal",  "wolf_chat",      ["Aruna: Bandara is loud, kill him."])
write_private(state, "Seetha", "investigations", [{"target": "Aruna", "result": "wolf"}])


def what_does(player_name: str) -> dict:
    """Return ONLY what `player_name` is allowed to see.
    This is exactly the slice we'll feed into each LLM prompt later."""
    return {
        "public": state["public_log"],
        "my_private": read_private(state, player_name),
    }


for name in ["Bandara", "Seetha", "Aruna"]:
    print(f"\n=== What {name} sees ===")
    print(what_does(name))
