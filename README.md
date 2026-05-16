# 🏘️ Mafia Village — Multi-Agent Simulation with Google ADK

> A small Streamlit app that simulates the classic social-deduction game **Mafia** (a.k.a. Werewolf). The "players" aren't humans — they're LLM-powered agents built with **Google's Agent Development Kit (ADK)**. They lie to each other, vote for each other, and occasionally save each other's lives.

This is the **finished reference implementation** that accompanies the live-build session in [`docs/mafia-village-tutorial.md`](docs/mafia-village-tutorial.md). The slide deck for the session lives in [`docs/adk_lesson.html`](docs/adk_lesson.html).

---

## What you'll see

- A **Village Square** panel where agents argue in public: _"I don't trust Aruna, she was too quiet last round"_.
- A **Moderator Log** of system events: _"Night 2 begins", "Nimal was eliminated"_.
- A live **player list** with 🟢 alive / 💀 dead indicators.
- A **Pause** button + **Peek** dropdown that let you halt the game between phases and inspect any agent's secret role, private memory, and the exact reasoning that drove their last vote — including watching a wolf decide to frame an innocent villager.

---

## Prerequisites

- **Python 3.10 or newer** (check with `python --version`). ADK does not support Python 3.9 or older.
- A free **Google AI Studio API key** — grab one at <https://aistudio.google.com/apikey>.
- ~5 minutes for setup; 30–90 seconds per game.

---

## Quick start

```bash
# 1. Clone the repo
git clone <your-fork-url> mafia-village
cd mafia-village

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# Then edit .env and paste your Google AI Studio key after GOOGLE_API_KEY=

# 5. Sanity check (one LLM call)
python smoke_test.py
# You should see: [HelloAgent] Hi class — ...

# 6. Run a full game in the terminal
python play_cli.py

# 7. Or launch the Streamlit UI
streamlit run app.py
# Opens http://localhost:8501
```

---

## Project layout

```
mafia-village/
├── .env.example          # template — copy to .env and add your key
├── .gitignore            # ignores .env, venvs, transcripts
├── requirements.txt
├── README.md             # this file
├── app.py                # Streamlit UI (setup + live view)
├── play_cli.py           # full terminal game
├── smoke_test.py         # Part 1.6 — one LLM call
├── smoke_state.py        # Part 2  — state asymmetry demo
├── smoke_player.py       # Part 3  — one villager speaks
├── smoke_call_player.py  # Part 4.1 — call_player + parse_single
├── smoke_seer.py         # Part 4.2 — SeerAgent alone
├── smoke_wolves.py       # Part 4.4 — WolvesAgent alone
├── smoke_night.py        # Part 4.5 — full night phase
├── smoke_round.py        # Part 5   — full round (night + day)
├── docs/
│   ├── mafia-village-tutorial.md   # step-by-step tutorial
│   └── adk_lesson.html             # accompanying slide deck
└── mafia/
    ├── __init__.py
    ├── names.py          # Sri Lankan name pool
    ├── state.py          # init_state, helpers (shared whiteboard)
    ├── players.py        # role prompt templates + create_player
    ├── night.py          # call_player, Wolves/Seer/Doctor/NightPhase/DeathResolver
    ├── day.py            # Discussion / Voting / Execution / DayPhase
    ├── game.py           # WinConditionChecker + build_game()
    └── control.py        # GameController (background thread for Streamlit)
```

---

## How it works in 60 seconds

The game tree is composed entirely from four ADK primitives:

| Primitive | Used for |
|---|---|
| `LlmAgent` | Each player (one prompt per role: villager / wolf / seer / doctor). |
| `SequentialAgent` | A single round: Night → Resolve → Day → Execute → Win check. |
| `LoopAgent` | The outer game loop, capped at 20 rounds. |
| `BaseAgent` (custom) | Pure-Python orchestration: wolves' private chat, death resolution, vote tallying, win check. |

Information flows through **one shared dict** (`session.state`) that has a **public side** (`public_log` — everyone reads) and a **private side** (`private_memory[player_name]` — only fed into that player's prompt). Removing this asymmetry is what makes the game collapse, so the entire architecture is organised around protecting it.

For the full story — including diagrams, deliberate pitfalls, and the philosophical asides — read [`docs/mafia-village-tutorial.md`](docs/mafia-village-tutorial.md).

---

## Running the smoke tests

Each smoke test is an independent verification of one piece of the system. Run them in order if anything goes wrong:

```bash
python smoke_test.py          # ADK + API key working
python smoke_state.py         # state helpers (no LLM)
python smoke_player.py        # one player replies
python smoke_call_player.py   # parser handles markdown
python smoke_seer.py          # Seer fills her private memory
python smoke_wolves.py        # Wolves chat + agree
python smoke_night.py         # full night phase
python smoke_round.py         # one full round
python play_cli.py            # a complete game
```

Every game finishes with a JSON dump (`last_game.json`) you can grep for the full reasoning trail — useful for debugging an oddly-behaving agent.

---

## Common issues

| Error | Fix |
|---|---|
| `pip install google-adk` complains about no matching distribution | Your Python is older than 3.10. Run `python --version`. |
| `google.api_core.exceptions.PermissionDenied: 403` | Check `.env` — make sure `GOOGLE_API_KEY` is set and `load_dotenv()` ran before any agent was built. |
| `TypeError: ... is not an async generator` | Your custom `BaseAgent._run_async_impl` has no `yield`. Add `if False: yield` at the bottom. |
| Streamlit complains about `set_page_config` | `st.set_page_config(...)` must be the very first Streamlit call. |
| Game seems frozen | Press **Resume** — auto-refresh is intentionally paused when the controller is paused. |

A fuller troubleshooting table is in **Appendix B** of the tutorial.

---

## Credits

Built for **CoDev Labs × STEMLink** Module 01 — Multi-Agent Foundations, led by Ashan.

Have fun lying to your own agents. 🐺
