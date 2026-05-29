import discord
from discord.ext import commands

from src import config
from src.clients import openrouter_client


def create_bot():
    INTENTS = discord.Intents.default()
    INTENTS.message_content = True
    INTENTS.voice_states = True
    # Use a Bot subclass with setup_hook for proper async initialization
    class PuteadorBot(commands.Bot):
        async def setup_hook(self):
            # initialize openrouter client (no-op if not configured)
            openrouter_client.init_client()

            # load extensions; load_extension is a coroutine
            try:
                await self.load_extension("src.cogs.insult_cog")
            except Exception as e:
                print(f"Failed to load insult_cog: {e}")
            try:
                await self.load_extension("src.cogs.voice_cog")
            except Exception as e:
                print(f"Failed to load voice_cog: {e}")

    bot = PuteadorBot(command_prefix="!", intents=INTENTS)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user} (id: {bot.user.id})")

    return bot


if __name__ == "__main__":
    bot = create_bot()
    bot.run(config.DISCORD_TOKEN)
