import os
import json
import random
import asyncio
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
WALLETS_FILE = "wallets.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- РАБОТА С КОШЕЛЬКАМИ ---
def load_wallets():
    if not os.path.exists(WALLETS_FILE):
        return {}
    try:
        with open(WALLETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_wallets(data):
    with open(WALLETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_coins(user_id: int, amount: int):
    wallets = load_wallets()
    str_id = str(user_id)
    wallets[str_id] = wallets.get(str_id, 0) + amount
    save_wallets(wallets)
    return wallets[str_id]

def get_balance(user_id: int):
    wallets = load_wallets()
    return wallets.get(str(user_id), 0)

# --- СПИСОК РАНДОМНЫХ УГОЩЕНИЙ И ЦЕН ---
TREATS = [
    {"name": "🍺 Ледяной Квас", "cost": 10},
    {"name": "🌯 Сочную Шаурму", "cost": 25},
    {"name": "🥟 Жирный Чебурек", "cost": 15},
    {"name": "⚡ Энергос", "cost": 20},
    {"name": "🥐 Сосиску в тесте", "cost": 12},
    {"name": "☕ Доширак с сосиской", "cost": 30}
]

# --- РЕАКЦИИ СУДЬИ НА ПОДНОШЕНИЯ ---
REACTIONS = [
    "😋 **Судья в один миг умял угощение:** «Ох, душа поёт! За такую вкуснотень снимаю с тебя 1% вины!»",
    "💥 **Судья громко отрыгнул в микрофон:** «Ну всё, заседание официально становится веселым!»",
    "🤝 **Судья утер усы:** «Вот это донат! Назначаю тебя Почетным Взяточником этого чата!»",
    "🤌 **Судья оценил подгон:** «Еда сработала! Судья добрый, но вердикт уже запечатан. Деньги не возвращаются!»",
    "👑 **Судья закинулся едой:** «За такое подношение объявляю тебя неприконовенным на следующие 5 минут!»",
    "🚬 *Судья сыто откинулся на кресле:* «Чёрт, как же хорошо... Прощаю тебе твои грехи!»"
]

# --- DUMMY SERVER ДЛЯ RENDER ---
async def handle_ping(request):
    return web.Response(text="Court Bot Alive!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- КОМАНДЫ ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "🏛 **Добро пожаловать в Базарный Суд!**\n\n"
        "• Вызвать суд: `/суд` в ответ (reply) на сообщение игрока.\n"
        "• Проверить баланс: `/кошелек`\n"
        "• Кормить судью через кнопки под вердиктами!"
    )

@dp.message(Command("кошелек", "bal"))
async def wallet_cmd(message: types.Message):
    coins = get_balance(message.from_user.id)
    await message.answer(f"💰 **Ваш капитал:** {coins} Судебных Издержек")

@dp.message(Command("суд"))
async def court_cmd(message: types.Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Вызови `/суд` **в ответ (reply)** на сообщение того, с кем споришь!")
        return

    accuser = message.from_user
    defendant = message.reply_to_message.from_user

    if accuser.id == defendant.id:
        await message.answer("🤡 Ты пытаешься засудить себя? Суд признает тебя сумасшедшим!")
        return

    add_coins(accuser.id, 50)
    add_coins(defendant.id, 50)

    # Достаем текст сообщения подсудимого
    target_text = message.reply_to_message.text or message.reply_to_message.caption or "[медиа-файл без текста]"

    # Формируем имя или юзернейм свидетеля (того, на чьё сообщение ответили, или истца)
    witness = f"@{accuser.username}" if accuser.username else accuser.first_name

    status = await message.answer("⚖️ **СУД ИДЁТ! ВСЕМ ВСТАТЬ!**")
    await asyncio.sleep(2)
    
    await status.edit_text(f"🔍 *Анализируем улику:* «{target_text[:30]}...»")
    await asyncio.sleep(2)

    guilty_user = random.choice([accuser, defendant])
    victim_user = defendant if guilty_user == accuser else accuser

    # Динамические вердикты с привязкой к тексту и свидетелю
    CRAZY_VERDICTS = [
        f"⚖️ **ВЕРДИКТ:** {{guilty}} полностью виновен!\n👉 **Доказательство:** Его фраза «<i>{target_text}</i>» признана бредом. Свидетель <b>{witness}</b> подтвердил это под присягой!",
        f"⚖️ **ВЕРДИКТ:** {{guilty}} пытался отмазаться фразой «<i>{target_text}</i>», но Судью не провести!\n👉 **Наказание:** Обращаться к {{victim}} «Мой Господин» до конца дня.",
        f"⚖️ **ВЕРДИКТ:** Проанализировав высер «<i>{target_text}</i>», Суд решил, что виновен {{guilty}}, а <b>{witness}</b> проходит как соучастник!",
        f"⚖️ **ВЕРДИКТ:** Истец {{victim}} в шоке от фразы «<i>{target_text}</i>». {{guilty}} признается виновным в уничтожении чужой психики!"
    ]

    verdict_template = random.choice(CRAZY_VERDICTS)
    verdict_text = verdict_template.format(
        guilty=guilty_user.mention_html(),
        victim=victim_user.mention_html()
    )

    full_response = (
        f"{verdict_text}\n\n"
        f"🪙 *Участники процесса получают по +50 коинов за моральный ущерб!*"
    )

    # Рандомное угощение для кнопки
    treat = random.choice(TREATS)
    button_text = f"{treat['name']} Судье ({treat['cost']} коинов)"
    callback_data = f"buy_{treat['cost']}_{treat['name']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=button_text, callback_data=callback_data)
    ]])

    await status.edit_text(full_response, parse_mode="HTML", reply_markup=kb)

# --- ОБРАБОТКА НАЖАТИЯ НА КНОПКУ УГОЩЕНИЯ ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_treat(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    _, cost_str, treat_name = call.data.split("_", 2)
    cost = int(cost_str)

    current_balance = get_balance(user_id)

    if current_balance < cost:
        await call.answer(f"❌ У тебя нет {cost} коинов на {treat_name}! Иди судись!", show_alert=True)
        return

    add_coins(user_id, -cost)
    reaction_text = random.choice(REACTIONS)
    
    await call.answer(f"✅ Угощение {treat_name} куплено!")
    await call.message.reply(
        f"👤 {call.from_user.mention_html()} подогнал Судье **{treat_name}** за **{cost} коинов**!\n\n{reaction_text}",
        parse_mode="HTML"
    )

async def main():
    await start_dummy_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
