import asyncio
from telethon import TelegramClient, events
import os
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.completion import Completer, Completion
import mimetypes


load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_name = 'terminal_session'

# Set downloads directory to current location/downloads
downloads = os.path.join(os.getcwd(), "downloads")
os.makedirs(downloads, exist_ok=True)

def get_display_name(sender):
    first = getattr(sender, 'first_name', None)
    last = getattr(sender, 'last_name', None)
    if first and last:
        return f"{first} {last}"
    elif first:
        return first
    elif last:
        return last
    else:
        return ""

def get_photo_ext(photo):
    # Get the file extension, default is .jpg
    mime = getattr(photo, 'mime_type', None)
    if mime:
        ext = mimetypes.guess_extension(mime)
        if ext:
            return ext
    return '.jpg'

async def print_chatroom_messages(client, entity, limit):

    messages = await client.get_messages(entity, limit=limit)
    for msg in reversed(messages):
        sender = await msg.get_sender()
        username = getattr(sender, 'username', None)
        display_name = get_display_name(sender)
        if username:
            sender_str = f"{display_name} ({username})" if display_name else username
        else:
            sender_str = display_name or "Unknown"
        if msg.sticker:
            print(f"{sender_str}: [sticker]")
        elif msg.photo:
            print(f"{sender_str}: [image] {msg.text}")
            ext = get_photo_ext(msg.photo)
            image_path = f"{downloads}/{msg.photo.id}{ext}"
            if not os.path.exists(image_path):
                file_path = await client.download_media(msg.photo, file=image_path)
                print(f"Downloaded image to: {file_path}")
        elif msg.media:
            print(f"{sender_str}: [media] {msg.text}")
        else:
            print(f"{sender_str}: {msg.text}")

class UsernameCompleter(Completer):
    def __init__(self, usernames):
        self.usernames = usernames

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith('@'):
            prefix = text[1:]
            for username in self.usernames:
                if username and username.startswith(prefix):
                    yield Completion(username, start_position=-len(prefix))

async def get_usernames(client, entity):
    usernames = set()
    async for user in client.iter_participants(entity):
        if user.username:
            usernames.add(user.username)
    return sorted(usernames)

async def main():
    async with TelegramClient(session_name, api_id, api_hash) as client:
        await client.start()
        me = await client.get_me()
        print("Logged in as:", me.username or me.first_name)

        handler_ref = None  # Add a variable record handler

        while True:
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

            # Get all usernames in the chat room
            usernames = await get_usernames(client, selected.entity)
            session = PromptSession(completer=UsernameCompleter(usernames))

            # Remove the old handler before entering the chat room.
            if handler_ref:
                client.remove_event_handler(handler_ref)

            @client.on(events.NewMessage(chats=selected.entity))
            async def handler(event):
                sender = await event.get_sender()
                username = getattr(sender, 'username', None)
                display_name = get_display_name(sender)
                if username:
                    sender_str = f"{username} ({display_name})" if display_name else username
                else:
                    sender_str = display_name or "Unknown"
                from prompt_toolkit.shortcuts import print_formatted_text

                if event.sticker:
                    print_formatted_text(f"{sender_str}: [sticker]")
                elif event.photo:
                    print_formatted_text(f"{sender_str}: [image] {event.text}")
                    ext = get_photo_ext(event.photo)
                    image_path = f"{downloads}/{event.photo.id}{ext}"
                    if not os.path.exists(image_path):
                        file_path = await client.download_media(event.photo, file=image_path)
                        print(f"Downloaded image to: {file_path}")
                elif event.media:
                    print_formatted_text(f"{sender_str}: [media] {event.text}")
                else:
                    print_formatted_text(f"{sender_str}: {event.text}")

            handler_ref = handler

            await print_chatroom_messages(client, selected.entity, limit=50)

            print(f"\nJoined chat: {selected.name or '(no title)'}")
            print("Type ':wq' to quit.")

            try:
                with patch_stdout():
                    while True:
                        msg = await session.prompt_async("Send message (or @someone): ")
                        if msg.strip() == ':wq':
                            print("\nReturning to chat list...")
                            break
                        
                        if msg.startswith('@'):
                            parts = msg.split(' ', 1)
                            if len(parts) < 2:
                                print("Usage: @[username] [message]")
                                continue
                            at_part = parts[0]
                            at_message = parts[1]
                            at_username = at_part[1:]

                            async for user in client.iter_participants(selected.entity):
                                if user.username == at_username:
                                    await client.send_message(selected.entity, f"@{at_username} {at_message}", at_to=None)
                                    session.app.renderer.clear()
                                    break
                            else:
                                print(f"User @{at_username} not found in this chat.")
                            continue
                        try:
                            await client.send_message(selected.entity, msg)
                        except Exception as e:
                            print("Error:", e)
            except KeyboardInterrupt:
                print("\nbyebye!")
                return

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbyebye!")