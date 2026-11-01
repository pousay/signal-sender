#!/usr/bin/env python3
"""Interactive helper script to generate a Kurigram MTProto user session string."""

import asyncio

from pyrogram import Client


async def main() -> None:
    """Prompt user for MTProto credentials, authenticate, and export string session."""
    print("=" * 65)
    print("  Telegram MTProto Session String Generator (Kurigram)")
    print("=" * 65)
    print("This script generates a session string for user account MTProto")
    print("access to read source channel history without bot restrictions.\n")

    api_id_input = input("Enter API_ID: ").strip()
    api_hash_input = input("Enter API_HASH: ").strip()

    if not api_id_input or not api_hash_input:
        print("Error: API_ID and API_HASH are required.")
        return

    try:
        api_id = int(api_id_input)
    except ValueError:
        print("Error: API_ID must be a numeric integer.")
        return

    api_hash = api_hash_input

    print("\nConnecting to Telegram MTProto...")
    async with Client(
        name="session_generator",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    ) as app:
        session_string = await app.export_session_string()
        me = await app.get_me()

        first_name = getattr(me, "first_name", "User")
        username = getattr(me, "username", "N/A")
        user_id = getattr(me, "id", 0)

        print("\n" + "=" * 65)
        print("Authentication Successful!")
        print(f"Logged in as: {first_name} (@{username}) [ID: {user_id}]")
        print("=" * 65)
        print("\nCopy and paste the following line into your .env file:\n")
        print(f'USER_SESSION_STRING="{session_string}"\n')
        print("=" * 65)
        print("NOTE: Keep this string secret. Never commit it to git repositories.")


if __name__ == "__main__":
    asyncio.run(main())
