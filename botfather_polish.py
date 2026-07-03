"""One-shot: polish @Quest3131Bot's public profile via BotFather.
Sets command list, description (what strangers see before /start), and about text.
Uses the existing learnix_tester.session (bot owner's account).
"""
import asyncio
import sys

from telethon import TelegramClient

API_ID = 38978049
API_HASH = "d0b46bd9b101c3f25b6be6251d6a2dd2"

BOT = "@Quest3131Bot"

COMMANDS = """start - wake the bot
tasks - see all your tasks
newtask - add a task
schedule - plan your day
weblogin - get a login code for the web app
goal - set a study goal
study - continue studying
graph - activity graph
timesheet - plan habit times
settings - reminder settings"""

DESCRIPTION = (
    "Your AI life OS — tasks, daily habits, reminders, study plans and focus "
    "sessions. Just talk naturally: 'remind me to call mom at 6pm', 'gym every "
    "day at 7am'. Includes a web app with a day timeline — send /weblogin to open it."
)

ABOUT = "AI life OS — tasks, habits, reminders + a web day-timeline. Talk to me naturally."


async def converse(client, *messages, wait=2.5):
    for m in messages:
        await client.send_message("BotFather", m)
        await asyncio.sleep(wait)
        async for r in client.iter_messages("BotFather", limit=1):
            print(f">> {m!r}\n<< {r.text[:160]!r}\n")


async def main():
    client = TelegramClient("learnix_tester", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("SESSION NOT AUTHORIZED — aborting")
        sys.exit(1)
    async with client:
        await converse(client, "/setcommands", BOT, COMMANDS)
        await converse(client, "/setdescription", BOT, DESCRIPTION)
        await converse(client, "/setabouttext", BOT, ABOUT)
    print("BotFather polish DONE")


if __name__ == "__main__":
    asyncio.run(main())
