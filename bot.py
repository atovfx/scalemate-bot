"""
Scalemate Bot — Your Telegram Second Brain 🧠
"""

import os
import io
import logging
import tempfile
import secrets
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatAction

from openai import AsyncOpenAI

import database as db

# ── Config ─────────────────────────────────────────────

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Team Channel Config ────────────────────────────────
# https://t.me/c/3549058526/75 → chat_id = -1003549058526, topic = 75
TEAM_CHANNEL_ID = -1003549058526
TEAM_TOPIC_ID = 75

# Allowed group — the bot will leave any other group
ALLOWED_GROUP_ID = -1003549058526

# ── 5 Access Keys ─────────────────────────────────────

ACCESS_KEYS = [
    ("SCALE-ALPHA-7X9K2", "Alpha"),
    ("SCALE-BRAVO-4M8P1", "Bravo"),
    ("SCALE-DELTA-2R6W5", "Delta"),
    ("SCALE-GAMMA-9T3N8", "Gamma"),
    ("SCALE-OMEGA-6J1V4", "Omega"),
]

# ── Available Models ───────────────────────────────────

MODELS = {
    "gpt-4o": "⚡ GPT-4o — Rapide & puissant",
    "gpt-4o-mini": "🪶 GPT-4o Mini — Léger & économique",
    "gpt-4-turbo": "🚀 GPT-4 Turbo — Haute performance",
    "gpt-4.1": "🧠 GPT-4.1 — Dernier modèle",
    "gpt-4.1-mini": "🔹 GPT-4.1 Mini — Compact & efficace",
    "gpt-4.1-nano": "🔸 GPT-4.1 Nano — Ultra-léger",
    "o4-mini": "💎 o4-mini — Raisonnement avancé",
    "gpt-3.5-turbo": "💬 GPT-3.5 Turbo — Classique",
}

# ── Helpers ────────────────────────────────────────────

async def send_styled(update: Update, text: str, parse_mode=ParseMode.HTML):
    """Send a well-formatted message."""
    await update.message.reply_text(text, parse_mode=parse_mode)


async def require_auth(update: Update) -> bool:
    """Check if user is authorized. Returns True if NOT authorized (should stop)."""
    user_id = update.effective_user.id
    if db.is_authorized(user_id):
        return False
    await send_styled(
        update,
        "<b>🔒 Accès restreint</b>\n\n"
        "Ce bot est privé. Tu as besoin d'une clé d'accès.\n\n"
        "Utilise : <code>/auth TA-CLE</code>\n\n"
        "<i>Contacte l'admin pour obtenir une clé.</i>",
    )
    return True


async def notify_team_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int, action: str, detail: str):
    """Send a recap to the team channel when a task event happens."""
    username = db.get_username(user_id)
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M")

    if action == "task_added":
        emoji = "📋"
        title = "NOUVELLE TÂCHE"
        status_line = "🆕 <b>Prévue</b>"
    elif action == "task_done":
        emoji = "✅"
        title = "TÂCHE TERMINÉE"
        status_line = "✅ <b>Complétée</b>"
    else:
        return

    msg = (
        f"{emoji} <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{username}</b>\n"
        f"📌 {detail}\n"
        f"{status_line}\n"
        f"🕐 {now} UTC\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await context.bot.send_message(
            chat_id=TEAM_CHANNEL_ID,
            message_thread_id=TEAM_TOPIC_ID,
            text=msg,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Failed to send team notification: {e}")


# ── /auth ──────────────────────────────────────────────

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.first_name or update.effective_user.username or str(user_id)

    if db.is_authorized(user_id):
        await send_styled(update, "<b>✅ Tu es déjà autorisé !</b>\n\n<i>Tape /start pour commencer.</i>")
        return

    if not context.args:
        await send_styled(update, "⚠️ <b>Usage :</b> <code>/auth TA-CLE-DACCES</code>")
        return

    key = context.args[0].strip()
    label = db.use_access_key(key, user_id, username)

    if label:
        await send_styled(
            update,
            f"<b>🎉 Bienvenue dans Scalemate !</b>\n\n"
            f"Clé <code>{label}</code> activée avec succès.\n\n"
            f"Tape /start pour découvrir toutes les fonctionnalités !",
        )
    else:
        await send_styled(
            update,
            "<b>❌ Clé invalide ou déjà utilisée</b>\n\n"
            "<i>Vérifie ta clé ou contacte l'admin.</i>",
        )


# ── /keys (admin) ─────────────────────────────────────

async def keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all access keys and their status (admin only - first authorized user)."""
    user_id = update.effective_user.id
    if not db.is_authorized(user_id):
        return

    conn = db.get_connection()
    keys = conn.execute("SELECT * FROM access_keys ORDER BY label").fetchall()
    conn.close()

    lines = []
    for k in keys:
        if k["used_by"]:
            name = db.get_username(k["used_by"])
            lines.append(f"  🔴 <code>{k['key']}</code>\n       {k['label']} — utilisée par <b>{name}</b>")
        else:
            lines.append(f"  🟢 <code>{k['key']}</code>\n       {k['label']} — <i>disponible</i>")

    msg = "<b>🔑 Clés d'accès Scalemate</b>\n\n" + "\n\n".join(lines)
    await send_styled(update, msg)


# ── Group protection ──────────────────────────────────

async def track_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave any group the bot is added to, except the allowed one."""
    result = update.my_chat_member
    if result is None:
        return

    new_status = result.new_chat_member.status
    chat = result.chat

    # Bot was added to a group
    if new_status in ("member", "administrator"):
        if chat.type in ("group", "supergroup") and chat.id != ALLOWED_GROUP_ID:
            logger.info(f"Bot added to unauthorized group {chat.id} ({chat.title}). Leaving.")
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        "<b>🔒 Accès non autorisé</b>\n\n"
                        "Ce bot est réservé à un groupe spécifique.\n"
                        "<i>Je quitte ce groupe automatiquement.</i>"
                    ),
                    parse_mode=ParseMode.HTML,
                )
                await context.bot.leave_chat(chat.id)
            except Exception as e:
                logger.error(f"Failed to leave chat {chat.id}: {e}")


# ── /start ─────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not db.is_authorized(user_id):
        await send_styled(
            update,
            "<b>🧠 Scalemate — Second Brain</b>\n\n"
            "🔒 Ce bot est privé.\n\n"
            "Pour y accéder, utilise ta clé :\n"
            "<code>/auth TA-CLE-DACCES</code>\n\n"
            "<i>Contacte l'admin si tu n'as pas de clé.</i>",
        )
        return

    user = update.effective_user
    welcome = f"""
<b>🧠 Scalemate — Ton Second Brain</b>

Salut <b>{user.first_name}</b> ! Je suis ton assistant personnel.

<b>━━━ Ce que je peux faire ━━━</b>

💬  <b>Discuter</b> — Envoie-moi un message, je te réponds avec l'IA
🎤  <b>Vocaux</b> — Envoie un vocal, je le transcris et te réponds
🖼  <b>Images</b> — Envoie une image, je l'analyse

<b>━━━ Commandes ━━━</b>

📋  /task <code>titre</code> — Ajouter une tâche
✅  /tasks — Voir tes tâches
📝  /note <code>texte</code> — Sauvegarder une note
🗂  /notes — Voir tes notes
⏰  /remind <code>HH:MM message</code> — Créer un rappel
🔔  /reminders — Voir tes rappels
🤖  /model — Changer de modèle IA
🧹  /clear — Effacer l'historique de conversation
📊  /stats — Voir tes statistiques
📦  /export — Exporter tes données
🔑  /keys — Voir les clés d'accès
❓  /help — Afficher l'aide

<i>Envoie-moi n'importe quoi pour commencer !</i>
"""
    await send_styled(update, welcome)


# ── /help ──────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    help_text = """
<b>📖 Guide Scalemate</b>

<b>━━━ Chat IA ━━━</b>
Envoie un message texte → je te réponds
Envoie un vocal 🎤 → je transcris + réponds
Envoie une image 🖼 → je l'analyse + réponds

<b>━━━ Tâches ━━━</b>
<code>/task Acheter du pain</code> → Ajoute une tâche
<code>/tasks</code> → Liste tes tâches en cours
<code>/done 3</code> → Marque la tâche #3 comme faite
<code>/deltask 3</code> → Supprime la tâche #3
💡 <i>Quand tu ajoutes ou termines une tâche, la team est prévenue dans le channel !</i>

<b>━━━ Notes ━━━</b>
<code>/note Idée pour le projet X</code> → Sauvegarde une note
<code>/note #travail Réunion à 14h</code> → Note avec tag
<code>/notes</code> → Toutes tes notes
<code>/notes travail</code> → Notes du tag "travail"
<code>/delnote 2</code> → Supprime la note #2

<b>━━━ Rappels ━━━</b>
<code>/remind 14:30 Appeler le médecin</code> → Rappel aujourd'hui
<code>/remind 2025-12-25 09:00 Joyeux Noël</code> → Rappel à une date
<code>/reminders</code> → Voir les rappels actifs
<code>/delremind 1</code> → Supprimer un rappel

<b>━━━ Modèles ━━━</b>
<code>/model</code> → Choisir un modèle IA

<b>━━━ Divers ━━━</b>
<code>/clear</code> → Reset la conversation
<code>/stats</code> → Tes statistiques
<code>/export</code> → Exporter tes notes
<code>/keys</code> → Voir les clés d'accès
"""
    await send_styled(update, help_text)


# ── /model ─────────────────────────────────────────────

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    current_model = db.get_user_model(user_id)

    keyboard = []
    for model_id, label in MODELS.items():
        check = " ✓" if model_id == current_model else ""
        keyboard.append(
            [InlineKeyboardButton(f"{label}{check}", callback_data=f"model:{model_id}")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"<b>🤖 Choisis ton modèle IA</b>\n\n"
        f"Modèle actuel : <code>{current_model}</code>\n\n"
        f"<i>Sélectionne un modèle ci-dessous :</i>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )


async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("model:"):
        return

    model_id = data.split(":", 1)[1]
    user_id = query.from_user.id

    if not db.is_authorized(user_id):
        await query.edit_message_text("🔒 Non autorisé.")
        return

    if model_id not in MODELS:
        await query.edit_message_text("❌ Modèle inconnu.")
        return

    db.set_user_model(user_id, model_id)

    await query.edit_message_text(
        f"<b>✅ Modèle mis à jour</b>\n\n"
        f"🤖 <code>{model_id}</code>\n"
        f"{MODELS[model_id]}\n\n"
        f"<i>Tes prochaines conversations utiliseront ce modèle.</i>",
        parse_mode=ParseMode.HTML,
    )


# ── /task & /tasks ─────────────────────────────────────

async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    text = " ".join(context.args) if context.args else ""

    if not text:
        await send_styled(update, "⚠️ <b>Usage :</b> <code>/task Titre de la tâche</code>")
        return

    task_id = db.add_task(user_id, text)
    await send_styled(
        update,
        f"<b>✅ Tâche ajoutée</b>\n\n"
        f"<code>#{task_id}</code> — {text}\n\n"
        f"<i>Utilise /done {task_id} quand c'est terminé</i>",
    )

    # Notify team channel
    if update.effective_chat.type == "private":
        await notify_team_channel(context, user_id, "task_added", text)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    show_all = context.args and context.args[0] == "all"
    tasks = db.get_tasks(user_id, show_done=show_all)

    if not tasks:
        await send_styled(
            update,
            "📋 <b>Aucune tâche en cours</b>\n\n<i>Ajoute une tâche avec /task</i>",
        )
        return

    lines = []
    for t in tasks:
        status = "✅" if t["done"] else "⬜"
        lines.append(f"  {status} <code>#{t['id']}</code> — {t['title']}")

    header = "📋 <b>Toutes tes tâches</b>" if show_all else "📋 <b>Tâches en cours</b>"
    msg = f"{header}\n\n" + "\n".join(lines) + "\n\n<i>/done ID pour compléter · /deltask ID pour supprimer</i>"
    await send_styled(update, msg)


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    if not context.args:
        await send_styled(update, "⚠️ <b>Usage :</b> <code>/done ID</code>")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await send_styled(update, "⚠️ L'ID doit être un nombre.")
        return

    # Get task title before completing
    conn = db.get_connection()
    task_row = conn.execute(
        "SELECT title FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
    ).fetchone()
    conn.close()

    if db.complete_task(user_id, task_id):
        await send_styled(update, f"<b>✅ Tâche #{task_id} terminée !</b>\n\n<i>Bien joué 💪</i>")

        # Notify team channel
        if update.effective_chat.type == "private" and task_row:
            await notify_team_channel(context, user_id, "task_done", task_row["title"])
    else:
        await send_styled(update, f"❌ Tâche #{task_id} introuvable.")


async def deltask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    if not context.args:
        await send_styled(update, "⚠️ <b>Usage :</b> <code>/deltask ID</code>")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await send_styled(update, "⚠️ L'ID doit être un nombre.")
        return

    if db.delete_task(user_id, task_id):
        await send_styled(update, f"🗑 <b>Tâche #{task_id} supprimée</b>")
    else:
        await send_styled(update, f"❌ Tâche #{task_id} introuvable.")


# ── /note & /notes ─────────────────────────────────────

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    text = " ".join(context.args) if context.args else ""

    if not text:
        await send_styled(update, "⚠️ <b>Usage :</b> <code>/note Ton texte ici</code>\n\n<i>Ajoute un tag avec #tag en début</i>")
        return

    tag = "general"
    if text.startswith("#"):
        parts = text.split(" ", 1)
        if len(parts) > 1:
            tag = parts[0][1:]
            text = parts[1]

    note_id = db.add_note(user_id, text, tag)
    await send_styled(
        update,
        f"<b>📝 Note sauvegardée</b>\n\n"
        f"<code>#{note_id}</code> [{tag}] — {text}\n\n"
        f"<i>/notes pour voir toutes tes notes</i>",
    )


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    tag = context.args[0] if context.args else None
    notes = db.get_notes(user_id, tag)

    if not notes:
        label = f' avec le tag "{tag}"' if tag else ""
        await send_styled(
            update,
            f"📝 <b>Aucune note{label}</b>\n\n<i>Ajoute une note avec /note</i>",
        )
        return

    lines = []
    for n in notes:
        date = n["created_at"][:10] if n["created_at"] else ""
        lines.append(f"  📌 <code>#{n['id']}</code> [{n['tag']}] {n['content']}\n       <i>{date}</i>")

    header = f"📝 <b>Notes — {tag}</b>" if tag else "📝 <b>Toutes tes notes</b>"
    msg = f"{header}\n\n" + "\n\n".join(lines) + "\n\n<i>/delnote ID pour supprimer</i>"
    await send_styled(update, msg)


async def delnote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    if not context.args:
        await send_styled(update, "⚠️ <b>Usage :</b> <code>/delnote ID</code>")
        return

    try:
        note_id = int(context.args[0])
    except ValueError:
        await send_styled(update, "⚠️ L'ID doit être un nombre.")
        return

    if db.delete_note(user_id, note_id):
        await send_styled(update, f"🗑 <b>Note #{note_id} supprimée</b>")
    else:
        await send_styled(update, f"❌ Note #{note_id} introuvable.")


# ── /remind & /reminders ──────────────────────────────

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = " ".join(context.args) if context.args else ""

    if not text:
        await send_styled(
            update,
            "⚠️ <b>Usage :</b>\n"
            "<code>/remind 14:30 Message du rappel</code>\n"
            "<code>/remind 2025-12-25 09:00 Message</code>",
        )
        return

    parts = text.split(" ", 2)

    try:
        # Try date + time format: 2025-12-25 14:30 Message
        if len(parts) >= 3 and "-" in parts[0]:
            date_str = parts[0]
            time_str = parts[1]
            message = parts[2] if len(parts) > 2 else "Rappel !"
            remind_at = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            # Time only format: 14:30 Message
            time_parts = text.split(" ", 1)
            time_str = time_parts[0]
            message = time_parts[1] if len(time_parts) > 1 else "Rappel !"
            now = datetime.utcnow()
            remind_time = datetime.strptime(time_str, "%H:%M").time()
            remind_at = datetime.combine(now.date(), remind_time)
            if remind_at <= now:
                remind_at += timedelta(days=1)
    except ValueError:
        await send_styled(
            update,
            "⚠️ <b>Format invalide</b>\n\n"
            "Utilise : <code>/remind HH:MM Message</code>\n"
            "Ou : <code>/remind YYYY-MM-DD HH:MM Message</code>",
        )
        return

    remind_at_str = remind_at.strftime("%Y-%m-%d %H:%M:%S")
    reminder_id = db.add_reminder(user_id, chat_id, message, remind_at_str)

    display_time = remind_at.strftime("%d/%m/%Y à %H:%M")
    await send_styled(
        update,
        f"<b>⏰ Rappel programmé</b>\n\n"
        f"<code>#{reminder_id}</code> — {message}\n"
        f"📅 {display_time}\n\n"
        f"<i>Je te préviendrai à l'heure dite !</i>",
    )


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    reminders = db.get_user_reminders(user_id)

    if not reminders:
        await send_styled(
            update,
            "🔔 <b>Aucun rappel actif</b>\n\n<i>Crée un rappel avec /remind</i>",
        )
        return

    lines = []
    for r in reminders:
        dt = datetime.strptime(r["remind_at"], "%Y-%m-%d %H:%M:%S")
        display = dt.strftime("%d/%m/%Y %H:%M")
        lines.append(f"  ⏰ <code>#{r['id']}</code> — {r['message']}\n       📅 {display}")

    msg = "<b>🔔 Rappels actifs</b>\n\n" + "\n\n".join(lines) + "\n\n<i>/delremind ID pour annuler</i>"
    await send_styled(update, msg)


async def delremind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    if not context.args:
        await send_styled(update, "⚠️ <b>Usage :</b> <code>/delremind ID</code>")
        return

    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await send_styled(update, "⚠️ L'ID doit être un nombre.")
        return

    if db.delete_reminder(user_id, reminder_id):
        await send_styled(update, f"🗑 <b>Rappel #{reminder_id} annulé</b>")
    else:
        await send_styled(update, f"❌ Rappel #{reminder_id} introuvable.")


# ── /clear ─────────────────────────────────────────────

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    db.clear_conversation(user_id)
    await send_styled(
        update,
        "<b>🧹 Conversation effacée</b>\n\n<i>On repart de zéro !</i>",
    )


# ── /stats ─────────────────────────────────────────────

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id

    tasks = db.get_tasks(user_id, show_done=True)
    tasks_done = sum(1 for t in tasks if t["done"])
    tasks_pending = len(tasks) - tasks_done

    notes = db.get_notes(user_id)
    reminders = db.get_user_reminders(user_id)
    model = db.get_user_model(user_id)

    await send_styled(
        update,
        f"<b>📊 Tes statistiques</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Tâches en cours : <b>{tasks_pending}</b>\n"
        f"✅ Tâches terminées : <b>{tasks_done}</b>\n"
        f"📝 Notes : <b>{len(notes)}</b>\n"
        f"⏰ Rappels actifs : <b>{len(reminders)}</b>\n"
        f"🤖 Modèle IA : <code>{model}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
    )


# ── /export ────────────────────────────────────────────

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id

    lines = ["═══ SCALEMATE EXPORT ═══\n"]

    # Tasks
    tasks = db.get_tasks(user_id, show_done=True)
    if tasks:
        lines.append("── TÂCHES ──")
        for t in tasks:
            status = "✅" if t["done"] else "⬜"
            lines.append(f"  {status} #{t['id']} — {t['title']}")
        lines.append("")

    # Notes
    notes = db.get_notes(user_id)
    if notes:
        lines.append("── NOTES ──")
        for n in notes:
            lines.append(f"  📌 #{n['id']} [{n['tag']}] {n['content']}")
        lines.append("")

    # Reminders
    reminders = db.get_user_reminders(user_id)
    if reminders:
        lines.append("── RAPPELS ──")
        for r in reminders:
            lines.append(f"  ⏰ #{r['id']} — {r['remind_at']} — {r['message']}")
        lines.append("")

    content = "\n".join(lines)
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = f"scalemate_export_{datetime.utcnow().strftime('%Y%m%d')}.txt"

    await update.message.reply_document(document=buf, caption="📦 <b>Export Scalemate</b>", parse_mode=ParseMode.HTML)


# ── Chat with AI ───────────────────────────────────────

async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    # Only respond in private chats
    if update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Save user message
    db.save_message(user_id, "user", user_text)

    # Build messages
    system_prompt = db.get_system_prompt(user_id)
    model = db.get_user_model(user_id)
    history = db.get_conversation(user_id)

    messages = [{"role": "system", "content": system_prompt}] + history

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
        )
        reply = response.choices[0].message.content

        # Save assistant reply
        db.save_message(user_id, "assistant", reply)

        # Send the reply — try HTML first, fallback to plain text
        try:
            await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        await send_styled(
            update,
            f"<b>❌ Erreur IA</b>\n\n<code>{str(e)[:200]}</code>\n\n"
            f"<i>Vérifie ton modèle avec /model</i>",
        )


# ── Voice Messages ─────────────────────────────────────

async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Download voice file
    voice = update.message.voice or update.message.audio
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        # Transcribe with Whisper
        with open(tmp_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="fr",
            )

        transcribed_text = transcript.text

        await send_styled(
            update,
            f"<b>🎤 Transcription</b>\n\n<i>{transcribed_text}</i>\n\n━━━━━━━━━━━━━━━━━━━━",
        )

        # Now process as a normal message
        db.save_message(user_id, "user", transcribed_text)

        system_prompt = db.get_system_prompt(user_id)
        model = db.get_user_model(user_id)
        history = db.get_conversation(user_id)
        messages = [{"role": "system", "content": system_prompt}] + history

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
        db.save_message(user_id, "assistant", reply)

        try:
            await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await send_styled(update, f"<b>❌ Erreur transcription</b>\n\n<code>{str(e)[:200]}</code>")
    finally:
        os.unlink(tmp_path)


# ── Image Messages ─────────────────────────────────────

async def image_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await require_auth(update):
        return

    user_id = update.effective_user.id

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Get the highest resolution photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    # Download to memory
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    buf.seek(0)

    import base64
    image_data = base64.b64encode(buf.read()).decode("utf-8")

    caption = update.message.caption or "Analyse cette image et décris ce que tu vois."

    model = db.get_user_model(user_id)
    # Use a vision-capable model
    vision_model = model if model in ("gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4.1", "gpt-4.1-mini") else "gpt-4o"

    try:
        response = await client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=1500,
        )
        reply = response.choices[0].message.content

        db.save_message(user_id, "user", f"[Image] {caption}")
        db.save_message(user_id, "assistant", reply)

        try:
            await update.message.reply_text(
                f"<b>🖼 Analyse d'image</b>\n\n{reply}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await update.message.reply_text(f"🖼 Analyse d'image\n\n{reply}")

    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        await send_styled(update, f"<b>❌ Erreur analyse image</b>\n\n<code>{str(e)[:200]}</code>")


# ── Document handler ───────────────────────────────────

async def document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle documents — save as note or analyze."""
    if await require_auth(update):
        return

    user_id = update.effective_user.id
    doc = update.message.document

    if doc.mime_type and doc.mime_type.startswith("image/"):
        # Treat as image
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        file = await context.bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)

        import base64
        image_data = base64.b64encode(buf.read()).decode("utf-8")
        caption = update.message.caption or "Analyse cette image."
        model = db.get_user_model(user_id)
        vision_model = model if model in ("gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4.1", "gpt-4.1-mini") else "gpt-4o"

        try:
            response = await client.chat.completions.create(
                model=vision_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                    ],
                }],
                max_tokens=1500,
            )
            reply = response.choices[0].message.content
            try:
                await update.message.reply_text(f"<b>🖼 Analyse</b>\n\n{reply}", parse_mode=ParseMode.HTML)
            except Exception:
                await update.message.reply_text(f"🖼 Analyse\n\n{reply}")
        except Exception as e:
            await send_styled(update, f"<b>❌ Erreur</b>\n\n<code>{str(e)[:200]}</code>")
        return

    # For text documents, save as note
    await send_styled(
        update,
        f"<b>📎 Document reçu</b>\n\n"
        f"<code>{doc.file_name}</code> ({doc.file_size} bytes)\n\n"
        f"<i>J'ai sauvegardé la référence. Ajoute une légende pour que je l'analyse !</i>",
    )


# ── Reminder checker job ──────────────────────────────

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job to check and send pending reminders."""
    reminders = db.get_pending_reminders()
    for r in reminders:
        try:
            await context.bot.send_message(
                chat_id=r["chat_id"],
                text=(
                    f"<b>🔔 RAPPEL</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{r['message']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                ),
                parse_mode=ParseMode.HTML,
            )
            db.mark_reminder_sent(r["id"])
        except Exception as e:
            logger.error(f"Failed to send reminder {r['id']}: {e}")


# ── Main ───────────────────────────────────────────────

def main():
    db.init_db()
    db.seed_access_keys(ACCESS_KEYS)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Group protection — leave unauthorized groups
    app.add_handler(ChatMemberHandler(track_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("auth", auth_command))
    app.add_handler(CommandHandler("keys", keys_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("deltask", deltask_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("delnote", delnote_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("delremind", delremind_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("export", export_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(model_callback, pattern=r"^model:"))

    # Messages (private only for AI chat)
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_message))
    app.add_handler(MessageHandler(filters.PHOTO, image_message))
    app.add_handler(MessageHandler(filters.Document.ALL, document_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))

    # Reminder job — checks every 30 seconds
    app.job_queue.run_repeating(check_reminders, interval=30, first=5)

    # Set bot commands for the menu
    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("start", "🚀 Démarrer le bot"),
            BotCommand("auth", "🔑 S'authentifier avec une clé"),
            BotCommand("help", "❓ Aide & commandes"),
            BotCommand("model", "🤖 Changer de modèle IA"),
            BotCommand("task", "📋 Ajouter une tâche"),
            BotCommand("tasks", "✅ Voir tes tâches"),
            BotCommand("done", "✔️ Terminer une tâche"),
            BotCommand("note", "📝 Sauvegarder une note"),
            BotCommand("notes", "🗂 Voir tes notes"),
            BotCommand("remind", "⏰ Créer un rappel"),
            BotCommand("reminders", "🔔 Voir tes rappels"),
            BotCommand("clear", "🧹 Effacer la conversation"),
            BotCommand("stats", "📊 Statistiques"),
            BotCommand("export", "📦 Exporter tes données"),
            BotCommand("keys", "🔑 Voir les clés d'accès"),
        ])

    app.post_init = post_init

    logger.info("🧠 Scalemate Bot is running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
