"""Live test: /start weblogin deep-link on the DEPLOYED bot must reply with a
4-digit web login code (not the normal welcome)."""
import asyncio
import re
import sys

from telethon import TelegramClient

API_ID = 38978049
API_HASH = "d0b46bd9b101c3f25b6be6251d6a2dd2"
BOT = "Quest3131Bot"


async def main():
    client = TelegramClient("learnix_tester", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("SESSION NOT AUTHORIZED")
        sys.exit(1)
    async with client:
        await client.send_message(BOT, "/start weblogin")
        await asyncio.sleep(6)
        async for m in client.iter_messages(BOT, limit=1):
            text = m.text or ""
            print("REPLY:", text[:200].replace("\n", " | "))
            code = re.search(r"\b(\d{4})\b", text)
            if "login code" in text.lower() and code:
                print(f"PASS — deep-link minted code {code.group(1)}")
                return
            print("FAIL — expected a web login code reply")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
