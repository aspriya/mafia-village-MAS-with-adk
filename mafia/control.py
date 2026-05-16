"""Threaded controller that runs the ADK game loop in the background.

The Streamlit page polls this controller for snapshots; the controller
runs the asyncio loop on a worker thread and respects a pause flag
between events.
"""
from __future__ import annotations
import asyncio
import copy
import threading
import traceback
from typing import Any

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

from .state import init_state
from .game import build_game


class GameController:
    def __init__(self, players: list[dict], model: str = "gemini-flash-latest"):
        self._players = players
        self._model = model
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._pause_evt: asyncio.Event | None = None
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] = init_state(players)
        self._done = False
        self._error: str | None = None    # populated if the bg thread crashes

    # ---------- public API ----------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        # asyncio.Event is NOT thread-safe — schedule the change on the loop.
        if self._loop and self._pause_evt:
            self._loop.call_soon_threadsafe(self._pause_evt.clear)

    def resume(self) -> None:
        if self._loop and self._pause_evt:
            self._loop.call_soon_threadsafe(self._pause_evt.set)

    def is_paused(self) -> bool:
        return bool(self._pause_evt and not self._pause_evt.is_set())

    def is_done(self) -> bool:
        return self._done

    def error(self) -> str | None:
        return self._error

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._snapshot)

    # ---------- internals ----------
    def _run_thread(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._pause_evt = asyncio.Event()
        self._pause_evt.set()  # start un-paused
        try:
            self._loop.run_until_complete(self._main())
        except Exception:  # surface to the UI rather than swallow silently
            self._error = traceback.format_exc()
        finally:
            self._done = True

    async def _main(self) -> None:
        state = init_state(self._players)
        sess = InMemorySessionService()
        await sess.create_session(app_name="mafia", user_id="u",
                                  session_id="s", state=state)
        runner = Runner(agent=build_game(), app_name="mafia",
                        session_service=sess)
        message = types.Content(role="user", parts=[types.Part(text="play")])
        async for _event in runner.run_async(
            user_id="u", session_id="s", new_message=message
        ):
            live = (await sess.get_session(
                app_name="mafia", user_id="u", session_id="s")).state
            with self._lock:
                self._snapshot = copy.deepcopy(live)
            # Respect pause between events.
            await self._pause_evt.wait()
