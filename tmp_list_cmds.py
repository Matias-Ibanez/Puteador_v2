from src.bot_main import create_bot
import asyncio

if __name__ == '__main__':
    b = create_bot()
    # If the bot provides setup_hook, run it so extensions load
    setup = getattr(b, "setup_hook", None)
    if callable(setup):
        try:
            asyncio.run(b.setup_hook())
        except Exception as e:
            print("setup_hook failed:", e)
    print(sorted(c.name for c in b.commands))
