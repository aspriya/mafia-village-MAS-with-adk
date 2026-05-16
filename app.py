"""Mafia Village — Streamlit UI (setup + live)."""
from __future__ import annotations
import json
import random

import streamlit as st
from dotenv import load_dotenv

from mafia.names import DEFAULT_NAMES
from mafia.control import GameController

load_dotenv()
st.set_page_config(page_title="Mafia Village", layout="wide")

ss = st.session_state
ss.setdefault("config", None)
ss.setdefault("controller", None)
ss.setdefault("god_mode", False)


def random_roster(total: int) -> list[str]:
    pool = DEFAULT_NAMES.copy()
    random.shuffle(pool)
    return pool[:total]


def assign_roles(names: list[str], n_wolves: int,
                 include_seer: bool, include_doctor: bool) -> list[dict]:
    roles: list[str] = ["wolf"] * n_wolves
    if include_seer:
        roles.append("seer")
    if include_doctor:
        roles.append("doctor")
    roles += ["villager"] * (len(names) - len(roles))
    random.shuffle(roles)
    return [{"name": n, "role": r, "alive": True} for n, r in zip(names, roles)]


def render_setup() -> None:
    st.title("🏘️ Mafia Village")
    st.caption("A multi-agent simulation powered by Google ADK.")

    with st.form("setup"):
        c1, c2 = st.columns(2)
        with c1:
            total = st.slider("Total players", 5, 12, value=7)
            n_wolves = st.slider("Number of wolves", 1, 3, value=2)
        with c2:
            include_seer = st.toggle("Include Seer", value=True)
            include_doctor = st.toggle("Include Doctor", value=True)
            model = st.text_input("LLM model", value="gemini-flash-latest")

        st.subheader("Players")
        if "name_drafts" not in ss or len(ss.name_drafts) != total:
            ss.name_drafts = random_roster(total)
        edited: list[str] = []
        cols = st.columns(3)
        for i in range(total):
            with cols[i % 3]:
                edited.append(st.text_input(
                    f"Player {i+1}", value=ss.name_drafts[i], key=f"name_{i}"))

        god = st.toggle("🔓 God Mode (reveal all roles + private chat live)", value=False)

        ok = True
        if n_wolves >= total // 2:
            st.error("Wolves must be fewer than half the players.")
            ok = False
        if len(set(edited)) != len(edited):
            st.error("Player names must be unique.")
            ok = False

        play = st.form_submit_button("▶️ Play", disabled=not ok)
        if play and ok:
            players = assign_roles(edited, n_wolves, include_seer, include_doctor)
            ss.config = {"players": players, "model": model}
            ss.god_mode = god
            ss.controller = None  # force a fresh game on next render
            st.rerun()


def _render_header(ctrl: GameController, snap: dict) -> None:
    """Title, phase caption, and the Pause/Resume/God-mode/New-game buttons."""
    top = st.columns([3, 1, 1, 1])
    with top[0]:
        st.title("🏘️ Mafia Village — live")
        phase = snap.get("phase", "setup")
        status = "🏁 done" if ctrl.is_done() else ("⏸ paused" if ctrl.is_paused() else "▶ running")
        st.caption(f"Day {snap.get('day_number', 0)} · Phase: **{phase}** · {status}")
    with top[1]:
        if ctrl.is_paused():
            if st.button("▶️ Resume", use_container_width=True,
                         disabled=ctrl.is_done()):
                ctrl.resume()
                st.rerun()
        else:
            if st.button("⏸️ Pause", use_container_width=True,
                         disabled=ctrl.is_done()):
                ctrl.pause()
                st.rerun()
    with top[2]:
        ss.god_mode = st.toggle("🔓 God Mode", value=ss.god_mode)
    with top[3]:
        if st.button("⟲ New game", use_container_width=True):
            ss.config = None
            ss.controller = None
            st.rerun()


def _render_squares(snap: dict) -> None:
    """Village Square + Moderator Log columns."""
    left, mid = st.columns([3, 2])
    with left:
        st.subheader("🏛️ Village Square")
        log = snap.get("public_log", [])
        if not log:
            st.info("The game is starting…")
        for line in log:
            st.markdown(f"- {line}")
    with mid:
        st.subheader("📋 Moderator Log")
        for line in snap.get("events", []):
            st.caption(line)


def _render_peek(snap: dict) -> None:
    """Player list + Peek-into-agent panel."""
    st.subheader("👥 Players")
    for p in snap.get("players", []):
        icon = "🟢" if p["alive"] else "💀"
        role = p["role"] if (ss.god_mode or not p["alive"]) else "???"
        st.markdown(f"{icon} **{p['name']}** · _{role}_")

    st.divider()
    st.subheader("🔍 Peek into an agent")
    names = [p["name"] for p in snap.get("players", [])]
    if not names:
        return
    target = st.selectbox("Pick a player", names, key="peek_target")
    priv = snap.get("private_memory", {}).get(target, {})
    true_role = next(
        (p["role"] for p in snap["players"] if p["name"] == target), "?")
    st.markdown(f"**True role:** `{true_role}`")
    if priv.get("last_action"):
        st.markdown(f"**Last action:** {priv['last_action']}")
    if priv.get("last_reasoning"):
        with st.expander("Last reasoning (raw LLM reply)"):
            st.code(priv["last_reasoning"])
    with st.expander("All private memory"):
        st.json(priv)


@st.fragment(run_every=1.0)
def _live_panels(ctrl: GameController) -> None:
    """The auto-refreshing portion: panels + end-of-game banner."""
    snap = ctrl.snapshot()
    body_left, body_right = st.columns([5, 2])
    with body_left:
        _render_squares(snap)
    with body_right:
        _render_peek(snap)

    if ctrl.is_done():
        if ctrl.error():
            st.error("The background game thread crashed:")
            st.code(ctrl.error())
        else:
            st.success(f"Game over — **{snap.get('winner') or 'no clear winner'}** win!")
            st.download_button(
                "⬇️ Download full transcript (JSON)",
                data=json.dumps(snap, indent=2, default=str),
                file_name="mafia_game.json",
                mime="application/json",
            )


def render_live() -> None:
    cfg = ss.config
    if ss.controller is None:
        ss.controller = GameController(cfg["players"], model=cfg["model"])
        ss.controller.start()
    ctrl: GameController = ss.controller

    # Header (buttons) outside the fragment — instantly responsive.
    _render_header(ctrl, ctrl.snapshot())
    # Panels inside the fragment — refresh every second on their own.
    _live_panels(ctrl)


# ---- entry point ----
if ss.config is None:
    render_setup()
else:
    render_live()
