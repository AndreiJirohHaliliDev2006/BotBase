from pyrogram import Client, Filters
from ..config import MAX_UPDATE_THRESHOLD, ANTIFLOOD_SENSIBILITY, BAN_TIME, ADMINS, BYPASS_FLOOD, FLOOD_NOTICE, \
    FLOOD_PERCENTAGE, CACHE, PRIVATE_ONLY, DELETE_MESSAGES, bot, user_banned, FLOOD_CLEARED, FLOOD_USER_CLEARED, \
    ERROR, NONNUMERIC_ID, check_user_banned
from collections import defaultdict
import logging
import time
from ..methods import MethodWrapper

# Some variables for runtime configuration

MESSAGES = defaultdict(list)  # Internal variable for the antiflood module
BANNED_USERS = Filters.user()  # Filters where the antiflood will put banned users
BYPASS_USERS = Filters.user(list(ADMINS.keys())) if BYPASS_FLOOD else Filters.user()
ADMINS = Filters.user(list(ADMINS.keys()))
FILTER = Filters.private if PRIVATE_ONLY else ~Filters.user()
wrapper = MethodWrapper(bot)


def is_flood(updates: list):
    """
    Calculates if a sequence of
    updates corresponds to a flood
    """

    genexpr = [i <= ANTIFLOOD_SENSIBILITY for i in
               ((updates[i + 1] - timestamp) if i < (MAX_UPDATE_THRESHOLD - 1) else (timestamp - updates[i - 1]) for
                i, timestamp in enumerate(updates))]
    return sum(genexpr) >= int((len(genexpr) / 100) * FLOOD_PERCENTAGE)


@Client.on_message(FILTER & ~BYPASS_USERS & ~user_banned(), group=-1)
def anti_flood(client, update):
    """Anti flood module"""

    user_id = update.from_user.id
    chat = update.chat.id
    date = update.date
    message_id = update.message_id
    if isinstance(MESSAGES[user_id], tuple):
        chat, date = MESSAGES[user_id]
        if time.time() - date >= BAN_TIME:
            logging.warning(f"{user_id} has waited at least {BAN_TIME} seconds in {chat} and can now text again")
            BANNED_USERS.remove(user_id)
            del MESSAGES[user_id]
    elif len(MESSAGES[user_id]) >= MAX_UPDATE_THRESHOLD - 1:  # -1 to avoid acting on the next update
        MESSAGES[user_id].append({chat: (date, message_id)})
        logging.info(f"MAX_UPDATE_THRESHOLD ({MAX_UPDATE_THRESHOLD}) Reached for {user_id}")
        user_data = MESSAGES.pop(user_id)
        timestamps = [list(*d.values())[0] for d in user_data]
        updates = [list(*d.values())[1] for d in user_data]
        if is_flood(timestamps):
            logging.warning(f"Flood detected from {user_id} in chat {chat}")
            if user_id in CACHE:
                del CACHE[user_id]
            BANNED_USERS.add(user_id)
            MESSAGES[user_id] = chat, time.time()
            if FLOOD_NOTICE:
                wrapper.send_message(user_id, FLOOD_NOTICE)
            if DELETE_MESSAGES:
                wrapper.delete_messages(chat, updates)
        else:
            if user_id in MESSAGES:
                del MESSAGES[user_id]
    else:
        MESSAGES[user_id].append({chat: (date, message_id)})


@Client.on_message(FILTER & ADMINS & ~Filters.edited & Filters.command("clearflood"))
def clear_flood(_, message):
    if len(message.command) == 1:
        global MESSAGES    # Ew...
        MESSAGES = defaultdict(list)
        for user in BANNED_USERS.copy():
            BANNED_USERS.remove(user)
        wrapper.send_message(message.chat.id, FLOOD_CLEARED)
    else:
        for user in message.command[1:]:
            if not user.isdigit():
                wrapper.send_message(message.chat.id, f"{ERROR}: {NONNUMERIC_ID}")
                return
            BANNED_USERS.discard(int(user))
            MESSAGES.pop(int(user), None)
        wrapper.send_message(message.chat.id, FLOOD_USER_CLEARED.format(user=", ".join((f"{usr}" for usr in message.command[1:]))))
