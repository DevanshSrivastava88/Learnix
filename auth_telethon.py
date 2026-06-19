import asyncio
import os
from telethon import TelegramClient

API_ID   = 38978049
API_HASH = "d0b46bd9b101c3f25b6be6251d6a2dd2"
PHONE    = "+918004844144"
OTP_FILE = r"D:\Projects\learnix\otp.txt"

async def main():
    client = TelegramClient("learnix_tester", API_ID, API_HASH)

    def get_code():
        print(f"\n>>> OTP sent to {PHONE}. Write the code into:")
        print(f"    {OTP_FILE}")
        print(">>> Then press Enter here to continue...")
        # Wait for file to appear
        import time
        while not os.path.exists(OTP_FILE):
            time.sleep(1)
        code = open(OTP_FILE).read().strip()
        os.remove(OTP_FILE)
        return code

    await client.start(phone=PHONE, code_callback=get_code)
    me = await client.get_me()
    print(f"\nLogged in as: {me.first_name} ({me.phone})")
    print("Session saved — auth done.")
    await client.disconnect()

asyncio.run(main())
