# 🧠 Scalemate Bot — Telegram Second Brain

A powerful Telegram bot that acts as your personal second brain — powered by OpenAI.

## Features

- **AI Chat** — Conversational AI with memory (GPT-4o, GPT-4.1, etc.)
- **Voice Messages** — Send voice notes, get transcription + AI response
- **Image Analysis** — Send screenshots or photos for AI analysis
- **Task Manager** — Create, complete, and track your tasks
- **Notes** — Save quick notes with tags
- **Reminders** — Set timed reminders that ping you
- **Model Switching** — Switch between 8+ OpenAI models on the fly
- **Data Export** — Export all your data anytime

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show all commands |
| `/model` | Switch AI model |
| `/task <title>` | Add a task |
| `/tasks` | View tasks |
| `/done <id>` | Complete a task |
| `/note <text>` | Save a note |
| `/notes [tag]` | View notes |
| `/remind HH:MM msg` | Set a reminder |
| `/reminders` | View reminders |
| `/clear` | Clear conversation |
| `/stats` | Your statistics |
| `/export` | Export data |

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables:
```
TELEGRAM_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```

Run:
```bash
python bot.py
```

## Deploy to Heroku

```bash
heroku create scalemate-bot
heroku config:set TELEGRAM_TOKEN=xxx OPENAI_API_KEY=xxx
git push heroku main
heroku ps:scale worker=1
```

## Tech Stack

- Python 3.12
- python-telegram-bot 21.x
- OpenAI API (GPT-4o, Whisper)
- SQLite
