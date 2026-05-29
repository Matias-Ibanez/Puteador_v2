from discord.ext import commands
import os
import discord
from typing import Optional

from src import config
from src.tts import tts_service
from src.audio import ffmpeg_utils
from src.voice import manager as voice_manager


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="say")
    async def say(self, ctx: commands.Context, *, text: str):
        if not ctx.author or not getattr(ctx.author, "voice", None) or not ctx.author.voice.channel:
            await ctx.reply("Por favor, únete a un canal de voz primero.")
            return

        if not text or text.strip() == "":
            await ctx.reply("No se proporcionó texto para reproducir.")
            return

        if len(text) > config.MAX_TEXT_LENGTH:
            await ctx.reply(f"Texto demasiado largo. Máximo {config.MAX_TEXT_LENGTH} caracteres.")
            return

        channel = ctx.author.voice.channel
        guild_id = ctx.guild.id if ctx.guild else None

        voice_client: Optional[discord.VoiceClient] = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if not voice_client or not voice_client.is_connected():
            try:
                voice_client = await channel.connect()
            except Exception as e:
                await ctx.reply(f"No pude conectar al canal de voz: {e}")
                return
        else:
            if voice_client.channel.id != channel.id:
                try:
                    await voice_client.move_to(channel)
                except Exception as e:
                    await ctx.reply(f"No pude moverme al canal de voz: {e}")
                    return

        tmp_name = None
        processed_name = None
        try:
            # generate_tts and ffmpeg processing are blocking; run in thread
            import asyncio

            tmp_name = await asyncio.to_thread(tts_service.generate_tts, text)

            # apply the single default preset (same as warning voice)
            processed_name = await asyncio.to_thread(
                ffmpeg_utils.process_with_preset, tmp_name, "warning"
            )

            play_file = processed_name if processed_name else tmp_name

            await voice_manager.play_audio(voice_client, play_file)

            if guild_id is not None:
                voice_manager.touch_activity(guild_id, voice_client)

            await ctx.reply("Reproduciendo en el canal de voz.")

        except Exception as e:
            await ctx.reply(f"Error al reproducir audio: {e}")
        finally:
            try:
                if tmp_name:
                    os.remove(tmp_name)
            except Exception:
                pass
            try:
                if processed_name:
                    os.remove(processed_name)
            except Exception:
                pass

    @commands.command(name="leave")
    async def leave(self, ctx: commands.Context):
        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if vc and vc.is_connected():
            await vc.disconnect()
            if ctx.guild and ctx.guild.id in voice_manager.guild_states:
                voice_manager.guild_states.pop(ctx.guild.id, None)
            await ctx.reply("Me desconecté.")
        else:
            await ctx.reply("No estoy conectado a ningún canal de voz.")

async def setup(bot: commands.Bot):
    # discord.py's add_cog may be async in recent versions; await it so
    # the cog is registered correctly when loaded.
    await bot.add_cog(VoiceCog(bot))
