import asyncio
from telethon import TelegramClient, events
import os
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.completion import Completer, Completion
import mimetypes
from PIL import Image
from telethon.tl.types import User, Chat, Channel


load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
session_name = 'terminal_session'

# Set downloads directory to current location/downloads
downloads = os.path.join(os.getcwd(), "downloads")
os.makedirs(downloads, exist_ok=True)

auto_download_image = os.getenv("AUTO_DOWNLOAD_IMAGE", "true").lower() == "true"
chat_history_limit = int(os.getenv("CHAT_HISTORY_LIMIT", "30"))
ascii_color = os.getenv("ASCII_COLOR", "true").lower() == "true"

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

async def print_chatroom_messages(client, entity, limit=chat_history_limit):
    messages = await client.get_messages(entity, limit=limit)
    for msg in reversed(messages):
        sender = await msg.get_sender()
        username = getattr(sender, 'username', None)
        display_name = get_display_name(sender)
        if username:
            sender_str = f"{display_name} ({username})" if display_name else username
        else:
            sender_str = display_name or "Unknown"

        # Handling of reply
        reply_info = ""
        if msg.reply_to_msg_id:
            try:
                reply_msg = await client.get_messages(entity, ids=msg.reply_to_msg_id)
                reply_sender = await reply_msg.get_sender()
                reply_username = getattr(reply_sender, 'username', None)
                reply_display_name = get_display_name(reply_sender)
                if reply_username:
                    reply_info = f"(reply > {reply_display_name}) "
                else:
                    reply_info = f"(reply > {reply_display_name or 'Unknown'}) "
            except Exception:
                reply_info = f"(reply > [{msg.reply_to_msg_id}]) "

        if msg.sticker:
            print(f"[{msg.id}] {sender_str}: {reply_info}[sticker]")
        elif msg.photo:
            ext = get_photo_ext(msg.photo)
            image_path = f"{downloads}/{msg.photo.id}{ext}"
            if auto_download_image and not os.path.exists(image_path):
                file_path = await client.download_media(msg.photo, file=image_path)
                print(f"Downloaded image to: {file_path}")
            # Convert to ASCII Art and display
            if os.path.exists(image_path) and auto_download_image:
                ascii_art = image_to_ascii(image_path)
                print(f"[{msg.id}] {sender_str}: {reply_info}\n{ascii_art}\n{msg.text}")
            elif not auto_download_image:
                print(f"[{msg.id}] {sender_str}: {reply_info}[image] {msg.text}")
            else:
                print(f"[{msg.id}] {sender_str}: {reply_info}[image] (image not found)")
        elif msg.media:
            print(f"[{msg.id}] {sender_str}: {reply_info}[media] {msg.text}")
        else:
            print(f"[{msg.id}] {sender_str}: {reply_info}{msg.text}")

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

class ChatCompleter(Completer):
    def __init__(self, usernames, message_ids):
        self.usernames = usernames
        self.message_ids = message_ids

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        # @username Completion
        if text.startswith('@'):
            prefix = text[1:]
            for username in self.usernames:
                if username and username.startswith(prefix):
                    yield Completion(username, start_position=-len(prefix))
        # /r [msg_id] Completion
        elif text.startswith('/r '):
            prefix = text[3:]
            for mid in self.message_ids:
                if str(mid).startswith(prefix):
                    yield Completion(str(mid), start_position=-len(prefix))

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
            dialogs = await client.get_dialogs(limit=10)
            # 過濾私人聊天與群組
            filtered_dialogs = []
            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, User) and not entity.bot:
                    filtered_dialogs.append(dialog)
                elif isinstance(entity, Chat):
                    filtered_dialogs.append(dialog)
                elif isinstance(entity, Channel) and getattr(entity, "megagroup", False):
                    filtered_dialogs.append(dialog)

            print("\nYour recent chats:")
            for idx, dialog in enumerate(filtered_dialogs):
                name = dialog.name or "(no title)"
                print(f"{idx+1}. {name}")

            # Select chatroom
            while True:
                try:
                    choice = int(input("\nEnter chat number to join: ")) - 1
                    if 0 <= choice < len(filtered_dialogs):
                        selected = filtered_dialogs[choice]
                        break
                    else:
                        print("Invalid number.")
                except ValueError:
                    print("Please enter a valid number.")

            # Retrieve all usernames from the chatroom
            usernames = await get_usernames(client, selected.entity)

            # Retrieve all message IDs from the chatroom
            messages = await client.get_messages(selected.entity, limit=chat_history_limit)
            message_ids = [msg.id for msg in messages]

            session = PromptSession(completer=ChatCompleter(usernames, message_ids))

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

                # Handling of reply
                reply_info = ""
                if event.reply_to_msg_id:
                    try:
                        reply_msg = await client.get_messages(selected.entity, ids=event.reply_to_msg_id)
                        reply_sender = await reply_msg.get_sender()
                        reply_username = getattr(reply_sender, 'username', None)
                        reply_display_name = get_display_name(reply_sender)
                        if reply_username:
                            reply_info = f"(reply > {reply_display_name}) "
                        else:
                            reply_info = f"(reply > {reply_display_name or 'Unknown'}) "
                    except Exception:
                        reply_info = f"(reply > [{event.reply_to_msg_id}]) "

                if event.sticker:
                    print_formatted_text(f"[{event.id}] {sender_str}: {reply_info}[sticker]")
                elif event.photo:
                    ext = get_photo_ext(event.photo)
                    image_path = f"{downloads}/{event.photo.id}{ext}"
                    if auto_download_image and not os.path.exists(image_path):
                        file_path = await client.download_media(event.photo, file=image_path)
                        print(f"Downloaded image to: {file_path}")
                    # Generate and display ASCII Art
                    if os.path.exists(image_path) and auto_download_image:
                        ascii_art = image_to_ascii(image_path)
                        print_formatted_text(f"[{event.id}] {sender_str}: {reply_info}[image]\n{ascii_art}\n{event.text}")
                    elif not auto_download_image:
                        print_formatted_text(f"[{event.id}] {sender_str}: {reply_info}[image] {event.text}")
                    else:
                        print_formatted_text(f"[{event.id}] {sender_str}: {reply_info}[image] (image not found)")
                elif event.media:
                    print_formatted_text(f"[{event.id}] {sender_str}: {reply_info}[media] {event.text}")
                else:
                    print_formatted_text(f"[{event.id}] {sender_str}: {reply_info}{event.text}")

            handler_ref = handler

            await print_chatroom_messages(client, selected.entity, limit=chat_history_limit)

            print(f"\nJoined chat: {selected.name or '(no title)'}")
            print("Type ':wq' to quit.")

            try:
                with patch_stdout():
                    while True:
                        msg = await session.prompt_async("Send message (or @someone, or /r [msg_id] [message]): ")
                        if msg.strip() == ':wq':
                            print("\nReturning to chat list...")
                            break
                        
                        if msg.startswith('/r '):
                            parts = msg.split(' ', 2)
                            if len(parts) < 3:
                                print("Usage: /r [msg_id] [message]")
                                continue
                            reply_id = int(parts[1])
                            reply_message = parts[2]
                            try:
                                sent = await client.send_message(selected.entity, reply_message, reply_to=reply_id)
                                # Show reply message you just sent
                                me = await client.get_me()
                                display_name = get_display_name(me)
                                sender_str = f"{me.username} ({display_name})" if me.username else display_name or "Unknown"
                                print(f"[{sent.id}] {sender_str}: (reply > {reply_id}) {reply_message}")
                            except Exception as e:
                                print(f"Reply failed: {e}")
                            continue

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

def image_to_ascii(image_path, width=30):
    chars = "@%#*+=-:. "
    try:
        img = Image.open(image_path)
        w, h = img.size
        aspect_ratio = h / w
        char_aspect = 0.5
        new_height = int(aspect_ratio * width * char_aspect)
        img = img.resize((width, new_height))
        img = img.convert('RGB')
        pixels = list(img.getdata())
        ascii_str = ""
        for i in range(len(pixels)):
            if i % width == 0 and i != 0:
                ascii_str += "\n"
            r, g, b = pixels[i]
            gray = int(0.299*r + 0.587*g + 0.114*b)
            char = chars[gray * len(chars) // 256]
            if ascii_color:
                # coloured
                ascii_str += f"\033[38;2;{r};{g};{b}m{char}\033[0m"
            else:
                # gray
                ascii_str += char
        return ascii_str
    except Exception as e:
        return f"[Failed to convert image to ASCII: {e}]"

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbyebye!")