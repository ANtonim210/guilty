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

# --- СПИСОК УГОЩЕНИЙ И ЦЕН ---
TREATS = [
    {"name": "🍺 Ледяной Квас", "cost": 10},
    {"name": "🌯 Сочную Шаурму", "cost": 25},
    {"name": "🥟 Жирный Чебурек", "cost": 15},
    {"name": "⚡ Энергос", "cost": 20},
    {"name": "🥐 Сосиску в тесте", "cost": 12},
    {"name": "☕ Доширак с сосиской", "cost": 30}
]

REACTIONS = [
    "😋 <b>Судья в один миг умял угощение:</b> «Ох, душа поёт! За такую вкуснотень снимаю с тебя 1% вины!»",
    "💥 <b>Судья громко отрыгнул в микрофон:</b> «Ну всё, заседание официально становится веселым!»",
    "🤝 <b>Судья утер усы:</b> «Вот это донат! Назначаю тебя Почетным Взяточником этого чата!»",
    "🤌 <b>Судья оценил подгон:</b> «Еда сработала! Судья добрый, но вердикт уже запечатан!»",
    "👑 <b>Судья закинулся едой:</b> «За такое подношение объявляю тебя неприконовенным на следующие 5 минут!»",
    "🚬 <i>Судья сыто откинулся на кресле:</i> «Чёрт, как же хорошо... Прощаю тебе твои грехи!»"
]

# --- DUMMY SERVER ---
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
        "🏛 <b>Добро пожаловать в Базарный Суд!</b>\n\n"
        "• Вызвать суд: <code>/суд</code> в ответ (reply) на сообщение игрока.\n"
        "• Проверить баланс: <code>/кошелек</code>\n"
        "• Кормить и подкупать судью через кнопки под вердиктами!",
        parse_mode="HTML"
    )

@dp.message(Command("кошелек", "bal"))
async def wallet_cmd(message: types.Message):
    coins = get_balance(message.from_user.id)
    await message.answer(f"💰 <b>Ваш капитал:</b> {coins} Судебных Издержек", parse_mode="HTML")

@dp.message(Command("суд"))
async def court_cmd(message: types.Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Вызови <code>/суд</code> <b>в ответ (reply)</b> на сообщение того, с кем споришь!", parse_mode="HTML")
        return

    accuser = message.from_user
    defendant = message.reply_to_message.from_user

    if accuser.id == defendant.id:
        await message.answer("🤡 Ты пытаешься засудить себя? Суд признает тебя сумасшедшим!")
        return

    # Начисляем коины обоим
    add_coins(accuser.id, 50)
    add_coins(defendant.id, 50)

    # Текст сообщения
    target_text = message.reply_to_message.text or message.reply_to_message.caption or "[медиа-файл]"
    if len(target_text) > 40:
        target_text = target_text[:40] + "..."

    status = await message.answer("⚖️ <b>СУД ИДЁТ! ВСЕМ ВСТАТЬ!</b>", parse_mode="HTML")
    await asyncio.sleep(1.5)
    
    await status.edit_text(f"🔍 <i>Изучаем улику подсудимого:</i> «<u>{target_text}</u>»", parse_mode="HTML")
    await asyncio.sleep(1.5)

    guilty_user = random.choice([accuser, defendant])
    victim_user = defendant if guilty_user == accuser else accuser

    # Вердикты с чистым HTML
    CRAZY_VERDICTS = [
        f"⚖️ <b>ВЕРДИКТ:</b> {{guilty}} полностью виновен!\n👉 <b>Доказательство:</b> Фраза «<i>{target_text}</i>» признана полнейшей чушью!\n👉 <b>Наказание:</b> Обращаться к {{victim}} «Мой Господин» до конца дня.",
        f"⚖️ <b>ВЕРДИКТ:</b> {{guilty}} пытался отмазаться фразой «<i>{target_text}</i>», но Судью не провести!\n👉 <b>Наказание:</b> Записать ГС в чат с извинениями прямо сейчас.",
        f"⚖️ <b>ВЕРДИКТ:</b> Проанализировав сообщение «<i>{target_text}</i>», Суд решил, что {{victim}} невиновен, а {{guilty}} получает статус Главного Скуфа!",
        f"⚖️ <b>ВЕРДИКТ:</b> Истец {{victim}} в шоке от фразы «<i>{target_text}</i>». {{guilty}} признается виновным в уничтожении чужой психики!"
    ]

    verdict_template = random.choice(CRAZY_VERDICTS)
    verdict_text = verdict_template.format(
        guilty=guilty_user.mention_html(),
        victim=victim_user.mention_html()
    )

    full_response = (
        f"{verdict_text}\n\n"
        f"🪙 <i>Участники процесса получают по +50 коинов!</i>"
    )

    treat = random.choice(TREATS)
    
    # Две кнопки: Подношение и Перекуп суда
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{treat['name']} ({treat['cost']} к.)", callback_data=f"buy_{treat['cost']}_{treat['name']}")],
        [InlineKeyboardButton(text=f"🚨 Перекупить Суд (100 коинов)", callback_data=f"bribe_{guilty_user.id}_{victim_user.id}")]
    ])

    await status.edit_text(full_response, parse_mode="HTML", reply_markup=kb)

# --- ОБРАБОТКА ПОДНОШЕНИЯ (ЕДА) ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_treat(call: types.CallbackQuery):
    user_id = call.from_user.id
    _, cost_str, treat_name = call.data.split("_", 2)
    cost = int(cost_str)

    current_balance = get_balance(user_id)

    if current_balance < cost:
        await call.answer(f"❌ Не хватает коинов на {treat_name}! Баланс: {current_balance}/{cost}", show_alert=True)
        return

    add_coins(user_id, -cost)
    reaction_text = random.choice(REACTIONS)
    
    await call.answer(f"✅ {treat_name} куплено!")
    await call.message.reply(
        f"👤 {call.from_user.mention_html()} подогнал Судье <b>{treat_name}</b> за <b>{cost} коинов</b>!\n\n{reaction_text}",
        parse_mode="HTML"
    )

# --- ОБРАБОТКА ПЕРЕКУПА СУДА ---
@dp.callback_query(F.data.startswith("bribe_"))
async def process_bribe(call: types.CallbackQuery):
    user_id = call.from_user.id
    _, old_guilty_id, old_victim_id = call.data.split("_")
    
    if get_balance(user_id) < 100:
        await call.answer("❌ Перекуп стоит 100 коинов! У тебя недосчата!", show_alert=True)
        return

    add_coins(user_id, -100)
    
    await call.answer("💰 Взятка принята!")
    await call.message.edit_text(
        f"🚨 <b>СУДЬЯ КОРРУМПИРОВАН!</b> 🚨\n\n"
        f"Игрок {call.from_user.mention_html()} занёс Судье <b>100 коинов</b> в конверте!\n\n"
        f"⚖️ <b>НОВЫЙ ВЕРДИКТ:</b> Предыдущее решение аннулировано! Теперь виновным официально признаётся тот, кто радовался больше всех!",
        parse_mode="HTML"
    )

async def main():
    await start_dummy_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
