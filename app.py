import asyncio
import os
import mimetypes
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.completion import Completer, Completion
from PIL import Image
import colorama
colorama.init()

# --- Config & Constants ---
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = 'terminal_session'
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
AUTO_DOWNLOAD_IMAGE = os.getenv("AUTO_DOWNLOAD_IMAGE", "true").lower() == "true"
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", "30"))
ASCII_COLOR = os.getenv("ASCII_COLOR", "true").lower() == "true"

# --- Utility Functions ---
def get_display_name(sender):
    first = getattr(sender, 'first_name', None)
    last = getattr(sender, 'last_name', None)
    if first and last:
        return f"{first} {last}"
    return first or last or ""

def get_photo_ext(photo):
    mime = getattr(photo, 'mime_type', None)
    ext = mimetypes.guess_extension(mime) if mime else None
    return ext or '.jpg'

def image_to_ascii(image_path, width=30):
    chars = "@%#*+=-:. "
    try:
        img = Image.open(image_path)
        w, h = img.size
        aspect_ratio = h / w
        char_aspect = 0.5
        new_height = int(aspect_ratio * width * char_aspect)
        img = img.resize((width, new_height)).convert('RGB')
        pixels = list(img.getdata())
        ascii_str = ""
        for i, (r, g, b) in enumerate(pixels):
            if i % width == 0 and i != 0:
                ascii_str += "\n"
            gray = int(0.299*r + 0.587*g + 0.114*b)
            char = chars[gray * len(chars) // 256]
            if ASCII_COLOR:
                ascii_str += f"\033[38;2;{r};{g};{b}m{char}\033[0m"
            else:
                ascii_str += char
        return ascii_str
    except Exception as e:
        return f"[Failed to convert image to ASCII: {e}]"

async def get_usernames(client, entity):
    usernames = set()
    async for user in client.iter_participants(entity):
        if user.username:
            usernames.add(user.username)
    return sorted(usernames)

async def get_message_ids(client, entity, limit):
    messages = await client.get_messages(entity, limit=limit)
    return [msg.id for msg in messages]

async def print_chatroom_messages(client, entity, limit=CHAT_HISTORY_LIMIT):
    messages = await client.get_messages(entity, limit=limit)
    for msg in reversed(messages):
        await print_message(client, entity, msg)

async def print_message(client, entity, msg):
    sender = await msg.get_sender()
    username = getattr(sender, 'username', None)
    display_name = get_display_name(sender)
    sender_str = f"{display_name} ({username})" if username else display_name or "Unknown"
    reply_info = await get_reply_info(client, entity, msg.reply_to_msg_id) if msg.reply_to_msg_id else ""
    if msg.sticker:
        print(f"[{msg.id}] {sender_str}: {reply_info}[sticker]")
    elif msg.photo:
        ext = get_photo_ext(msg.photo)
        image_path = f"{DOWNLOADS_DIR}/{msg.photo.id}{ext}"
        if AUTO_DOWNLOAD_IMAGE and not os.path.exists(image_path):
            file_path = await client.download_media(msg.photo, file=image_path)
            print(f"Downloaded image to: {file_path}")
        if os.path.exists(image_path) and AUTO_DOWNLOAD_IMAGE:
            ascii_art = image_to_ascii(image_path)
            print(f"[{msg.id}] {sender_str}: {reply_info}\n{ascii_art}\n{msg.text}")
        elif not AUTO_DOWNLOAD_IMAGE:
            print(f"[{msg.id}] {sender_str}: {reply_info}[image] {msg.text}")
        else:
            print(f"[{msg.id}] {sender_str}: {reply_info}[image] (image not found)")
    elif msg.media:
        print(f"[{msg.id}] {sender_str}: {reply_info}[media] {msg.text}")
    else:
        print(f"[{msg.id}] {sender_str}: {reply_info}{msg.text}")

async def get_reply_info(client, entity, reply_to_msg_id):
    try:
        reply_msg = await client.get_messages(entity, ids=reply_to_msg_id)
        reply_sender = await reply_msg.get_sender()
        reply_display_name = get_display_name(reply_sender)
        return f"(reply > {reply_display_name or 'Unknown'}) "
    except Exception:
        return f"(reply > [{reply_to_msg_id}]) "

# --- Completers ---
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
        if text.startswith('@'):
            prefix = text[1:]
            for username in self.usernames:
                if username and username.startswith(prefix):
                    yield Completion(username, start_position=-len(prefix))
        elif text.startswith('/r '):
            prefix = text[3:]
            for mid in self.message_ids:
                if str(mid).startswith(prefix):
                    yield Completion(str(mid), start_position=-len(prefix))

# --- Main Logic ---
async def main():
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        await client.start()
        me = await client.get_me()
        print("Logged in as:", me.username or me.first_name)
        handler_ref = None

        while True:
            dialogs = await client.get_dialogs(limit=30)
            filtered_dialogs = [
                d for d in dialogs
                if (isinstance(d.entity, User) and not d.entity.bot)
                or isinstance(d.entity, Chat)
                or (isinstance(d.entity, Channel) and getattr(d.entity, "megagroup", False))
            ]
            print("\nYour recent chats:")
            for idx, dialog in enumerate(filtered_dialogs):
                print(f"{idx+1}. {dialog.name or '(no title)'}")

            # Select chatroom
            selected = await select_chat(filtered_dialogs)
            usernames = await get_usernames(client, selected.entity)
            message_ids = await get_message_ids(client, selected.entity, CHAT_HISTORY_LIMIT)
            session = PromptSession(completer=ChatCompleter(usernames, message_ids))

            if handler_ref:
                client.remove_event_handler(handler_ref)

            @client.on(events.NewMessage(chats=selected.entity))
            async def handler(event):
                await print_message(client, selected.entity, event)

            handler_ref = handler

            await print_chatroom_messages(client, selected.entity, limit=CHAT_HISTORY_LIMIT)
            print(f"\nJoined chat: {selected.name or '(no title)'}")
            print("Type ':wq' to quit.")

            try:
                with patch_stdout():
                    while True:
                        msg = await session.prompt_async("Send message (or @someone, or /r [msg_id] [message]): ")
                        if msg.strip() == ':wq':
                            print("\nReturning to chat list...")
                            break
                        if await handle_special_commands(client, selected, msg, me, session):
                            continue
                        try:
                            await client.send_message(selected.entity, msg)
                        except Exception as e:
                            print("Error:", e)
            except KeyboardInterrupt:
                print("\nbyebye!")
                return

async def select_chat(filtered_dialogs):
    while True:
        try:
            choice = int(input("\nEnter chat number to join: ")) - 1
            if 0 <= choice < len(filtered_dialogs):
                return filtered_dialogs[choice]
            print("Invalid number.")
        except ValueError:
            print("Please enter a valid number.")

async def handle_special_commands(client, selected, msg, me, session):
    if msg.startswith('/r '):
        parts = msg.split(' ', 2)
        if len(parts) < 3:
            print("Usage: /r [msg_id] [message]")
            return True
        reply_id = int(parts[1])
        reply_message = parts[2]
        try:
            sent = await client.send_message(selected.entity, reply_message, reply_to=reply_id)
            display_name = get_display_name(me)
            sender_str = f"{me.username} ({display_name})" if me.username else display_name or "Unknown"
            print(f"[{sent.id}] {sender_str}: (reply > {reply_id}) {reply_message}")
        except Exception as e:
            print(f"Reply failed: {e}")
        return True

    if msg.startswith('@'):
        parts = msg.split(' ', 1)
        if len(parts) < 2:
            print("Usage: @[username] [message]")
            return True
        at_username = parts[0][1:]
        at_message = parts[1]
        async for user in client.iter_participants(selected.entity):
            if user.username == at_username:
                await client.send_message(selected.entity, f"@{at_username} {at_message}")
                break
        else:
            print(f"User @{at_username} not found in this chat.")
        return True
    return False

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbyebye!")