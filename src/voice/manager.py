import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, Optional

import discord

from src import config


guild_states: Dict[int, Dict] = {}

# Per-guild playback lock so multiple commands queue instead of interrupting.
_play_locks: Dict[int, asyncio.Lock] = {}


async def schedule_disconnect(guild_id: int):
    initial_wait = max(0, config.INACTIVITY_SECONDS - config.WARNING_SECONDS)
    await asyncio.sleep(initial_wait)

    state = guild_states.get(guild_id)
    if not state:
        return

    last = state.get("last_activity")
    if not last:
        return

    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    if elapsed < initial_wait:
        state["disconnect_task"] = asyncio.create_task(schedule_disconnect(guild_id))
        return

    vc: Optional[discord.VoiceClient] = state.get("voice")
    if not vc or not vc.is_connected():
        guild_states.pop(guild_id, None)
        return

    tmp_name = None
    try:
        # generate warning TTS (blocking) in a thread
        from src.tts.tts_service import generate_tts

        tmp_name = await asyncio.to_thread(generate_tts, config.WARNING_TTS_TEXT)

        if vc.is_playing():
            vc.stop()
        source = discord.FFmpegPCMAudio(tmp_name)
        vc.play(source)

        waited = 0.0
        while vc.is_playing() and waited < config.WARNING_SECONDS + 5:
            await asyncio.sleep(0.5)
            waited += 0.5

    except Exception:
        pass
    finally:
        try:
            if tmp_name:
                os.remove(tmp_name)
        except Exception:
            pass

    await asyncio.sleep(config.WARNING_SECONDS)
    state = guild_states.get(guild_id)
    if not state:
        return
    last = state.get("last_activity")
    if last and (datetime.now(timezone.utc) - last).total_seconds() >= config.INACTIVITY_SECONDS:
        try:
            if vc and vc.is_connected():
                await vc.disconnect()
        except Exception:
            pass
        guild_states.pop(guild_id, None)


def touch_activity(guild_id: int, voice_client: discord.VoiceClient):
    state = guild_states.setdefault(guild_id, {})
    state["voice"] = voice_client
    state["last_activity"] = datetime.now(timezone.utc)

    task = state.get("disconnect_task")
    if task and not task.done():
        task.cancel()
    state["disconnect_task"] = asyncio.create_task(schedule_disconnect(guild_id))


async def play_audio(vc: discord.VoiceClient, file_path: str):
    """Play the given file in the VoiceClient and wait until finished."""
    try:
        guild_id = getattr(getattr(vc, "guild", None), "id", None)
        lock_key = int(guild_id) if guild_id is not None else id(vc)
        lock = _play_locks.get(lock_key)
        if lock is None:
            lock = asyncio.Lock()
            _play_locks[lock_key] = lock

        async with lock:
            # Queue behavior: if something is already playing, wait for it.
            while vc.is_playing():
                await asyncio.sleep(0.25)

            source = discord.FFmpegPCMAudio(file_path)
            vc.play(source)
            while vc.is_playing():
                await asyncio.sleep(0.25)
    except Exception:
        # best-effort: do not raise to caller
        return
