<img width="752" height="456" alt="image" src="https://github.com/user-attachments/assets/1bd098a7-af7f-4420-916d-8d1299320ee4" />
<img width="646" height="366" alt="image" src="https://github.com/user-attachments/assets/8d1442ce-53cb-4ca6-aa0e-10b24ff659de" />



# Telegram Terminal Chat Client

A terminal-based Telegram chat client built with [Telethon](https://github.com/LonamiWebs/Telethon).  
Supports message sending, @mention with tab completion, reply by message ID, auto image download, ASCII art image display, and more.

## Features

- Switch between multiple chats
- @username mention with tab completion
- `/r [msg_id] [message]` to reply to a specific message (msg_id supports tab completion)
- Auto-download images (configurable via `.env`)
- Display stickers, images (as ASCII art), and media messages
- Show reply target for each message
- `.env` configuration support

## Dependencies

- Python 3.7 or higher
- telethon
- python-dotenv
- prompt_toolkit
- pillow

## Installation

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Create a `.env` file**

   Example:

   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   AUTO_DOWNLOAD_IMAGE=true
   CHAT_HISTORY_LIMIT=30
   ASCII_COLOR=true
   ```

   - Get your `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org/)
   - Set `AUTO_DOWNLOAD_IMAGE=false` to disable auto image download
   - `CHAT_HISTORY_LIMIT` controls how many messages and chats are loaded (default is 50 if not set)
   - `ASCII_COLOR` controls whether images are displayed as colored ASCII art (`true`) or grayscale (`false`)

3. **Run the program**

   ```bash
   python app.py
   ```

## Usage

- After selecting a chat, type your message and press Enter to send
- Use `@username message` to mention someone (tab completion supported)
- Use `/r [msg_id] message` to reply to a specific message (tab completion supported for msg_id)
- Type `:wq` to return to the chat list
- Images are auto-downloaded to the `downloads` folder (if enabled)
- Images and stickers are displayed as ASCII art in the terminal (color or grayscale based on `.env` setting)

## License

MIT License
