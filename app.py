import asyncio
from telethon import TelegramClient, events
import os
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout


load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_name = 'terminal_session'

# Set downloads directory to current location/downloads
downloads = os.path.join(os.getcwd(), "downloads")
os.makedirs(downloads, exist_ok=True)

async def print_chatroom_messages(client, entity, limit):

    messages = await client.get_messages(entity, limit=limit)
    for msg in reversed(messages):
        sender = await msg.get_sender()
        sender_name = getattr(sender, 'username', None) or getattr(sender, 'first_name', 'Unknown')
        if msg.sticker:
            print(f"{sender_name}: [sticker]")
        elif msg.photo:
            print(f"{sender_name}: [image]")
            # file_path = await client.download_media(msg, file=f"{downloads}/{msg.id}")
            # print(f"Downloaded image to: {file_path}")
        elif msg.media:
            print(f"{sender_name}: [media]")
            # file_path = await client.download_media(msg, file=f"{downloads}/{msg.id}")
            # print(f"Downloaded media to: {file_path}")
        else:
            print(f"{sender_name}: {msg.text or '[empty message]'}")

async def main():
    async with TelegramClient(session_name, api_id, api_hash) as client:
        await client.start()
        me = await client.get_me()
        print("Logged in as:", me.username or me.first_name)

        # List chatrooms (dialogs)
        dialogs = await client.get_dialogs(limit=20)
        print("\nYour recent chats:")
        for idx, dialog in enumerate(dialogs):
            name = dialog.name or "(no title)"
            print(f"{idx+1}. {name}")

        # Select chatroom
        while True:
            try:
                choice = int(input("\nEnter chat number to join: ")) - 1
                if 0 <= choice < len(dialogs):
                    selected = dialogs[choice]
                    break
                else:
                    print("Invalid number.")
            except ValueError:
                print("Please enter a valid number.")

        print(f"\nJoined chat: {selected.name or '(no title)'}")
        print("Type ':wq' to quit.")

        session = PromptSession()

        @client.on(events.NewMessage(chats=selected.entity))
        async def handler(event):
            sender = await event.get_sender()
            # Use prompt_toolkit's print to avoid breaking input
            from prompt_toolkit.shortcuts import print_formatted_text
            print_formatted_text(f"\n{sender.username or sender.first_name}: {event.text}")

        await print_chatroom_messages(client, selected.entity, limit=20)

        try:
            with patch_stdout():
                while True:
                    msg = await session.prompt_async("Send message: ")
                    if msg.strip() == ':wq':
                        print("\nReturning to chat list...")
                        return await main()
                    try:
                        await client.send_message(selected.entity, msg)
                    except Exception as e:
                        print("Error:", e)
        except KeyboardInterrupt:
            print("\nbyebye!")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbyebye!")