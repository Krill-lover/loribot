import os
import json
import datetime
import pytz
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram import Router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import requests
import random
import asyncio

# Загрузка конфиденциальных данных из .env
load_dotenv()

# Получаем токен и проверяем его
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Токен бота не найден! Проверьте файл .env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL", "deepseek/deepseek-chat-v3-0324:free")

ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '1862652984').split(',') if id.strip()]
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID', '-1001234567890'))

DATA_FILE = "homework.json"
SUBSCRIBERS_FILE = "subscribers.json"
MEDIA_DIR = "static/media"
MEHIK_FILE = "mehiks.json"
os.makedirs(MEDIA_DIR, exist_ok=True)

# Создание бота с безопасным указанием parse_mode
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

scheduler = AsyncIOScheduler()
scheduler.start()

# 📦 Безопасные функции работы с файлами и JSON

# 📦 Безопасные функции работы с файлами и JSON

def load_homework():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_homework(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(list(subs), f)

SUBSCRIBERS = load_subscribers()


def chat_once(prompt: str):
    if not OPENROUTER_API_KEY:
        return {"status": "error", "message": "API ключ не найден"}

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            message_text = data["choices"][0]["message"]["content"]
            return {"status": "success", "message": message_text}
        else:
            return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# 🐣 Мехик — виртуальный Тамагочи-помощник
DEFAULT_MEHIK = {"mood": 100, "hunger": 50, "energy": 100, "stage": 1, "last_update": str(datetime.datetime.now())}

def load_mehiks():
    if os.path.exists(MEHIK_FILE):
        with open(MEHIK_FILE, "r") as f:
            return json.load(f)
    return {}

def save_mehiks(data):
    with open(MEHIK_FILE, "w") as f:
        json.dump(data, f, indent=2)

def update_mehik(user_id):
    mehiks = load_mehiks()
    mehik = mehiks.get(str(user_id), DEFAULT_MEHIK.copy())
    last = datetime.datetime.fromisoformat(mehik["last_update"])
    now = datetime.datetime.now()
    hours_passed = (now - last).total_seconds() // 3600
    mehik["hunger"] = min(100, mehik["hunger"] + int(hours_passed * 5))
    mehik["energy"] = max(0, mehik["energy"] - int(hours_passed * 3))
    mehik["mood"] = max(0, mehik["mood"] - int(hours_passed * 2))
    mehik["last_update"] = str(now)

    if mehik["mood"] > 90 and mehik["energy"] > 80 and mehik["hunger"] < 30:
        mehik["stage"] = min(3, mehik.get("stage", 1) + 1)

    mehiks[str(user_id)] = mehik
    save_mehiks(mehiks)
    return mehik

@router.message(Command("hello"))
async def mehik_hello(message: Message):
    mehik = update_mehik(message.from_user.id)
    mood = mehik["mood"]
    hunger = mehik["hunger"]
    energy = mehik["energy"]
    stage = mehik.get("stage", 1)

    mood_emoji = "😊" if mood > 70 else "😐" if mood > 40 else "😢" if mood > 20 else "💀"
    hunger_emoji = "🍎" if hunger < 30 else "🍞" if hunger < 60 else "🍔"
    energy_emoji = "⚡️" if energy > 70 else "😴" if energy < 40 else "🔋"
    stage_emoji = {1: "🥚", 2: "🐣", 3: "🤖"}.get(stage, "❓")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 ДЗ", callback_data="homework"),
         InlineKeyboardButton(text="🧠 Спросить AI", callback_data="ask")],
        [InlineKeyboardButton(text="💡 Проекты", callback_data="ideas"),
         InlineKeyboardButton(text="🔍 Найти деталь", callback_data="find")],
        [InlineKeyboardButton(text="🍎 Покормить", callback_data="feed"),
         InlineKeyboardButton(text="🎮 Поиграть", callback_data="play"),
         InlineKeyboardButton(text="😴 Спать", callback_data="sleep")]
    ])

    await message.answer(
        f"Привет, я <b>Мехик</b> {stage_emoji} — твой милый помощник!\n"
        f"Я здесь, чтобы подсказывать ДЗ, проекты, детали и вдохновлять тебя становиться инженером!\n\n"
        f"📊 <b>Состояние:</b>\nНастроение: {mood} {mood_emoji}\nГолод: {hunger} {hunger_emoji}\nЭнергия: {energy} {energy_emoji}",
        reply_markup=keyboard
    )

# База идей и поиск
PROJECT_CATEGORIES = {
    "робототехника": ["Сделай манипулятор на серво", "Гиробалансир на Arduino"],
    "умный дом": ["Контроль света по датчику движения", "Автоматическое окно на сервоприводе"],
    "другое": ["Сенсорный орган на базе Pi", "Мобильное приложение для управления"]
}

@router.message(F.text & ~F.text.startswith("/"))
async def answer_neural_message(message: Message):
    user_prompt = message.text.strip()
    await message.answer("🤖Mecha думает...")
    result = chat_once(user_prompt)
    if result["status"] == "success":
        await message.answer(result["message"])
    else:
        await message.answer(f"⚠️ Ошибка при обращении к нейросети: {result['message']}")



@router.message(Command("ideas"))
async def ideas(message: Message):
    categories = list(PROJECT_CATEGORIES.keys())
    keyboard = InlineKeyboardBuilder()
    for cat in categories:
        keyboard.button(text=cat.title(), callback_data=f"idea_{cat}")
    await message.answer("💡 Выбери категорию проекта:", reply_markup=keyboard.as_markup())

@router.callback_query(F.data.startswith("idea_"))
async def show_idea(callback: CallbackQuery):
    cat = callback.data.replace("idea_", "")
    idea = random.choice(PROJECT_CATEGORIES.get(cat, ["Идей пока нет"]))
    await callback.message.answer(f"🔧 <b>Проект ({cat.title()}):</b>\n{idea}")
    await callback.answer()

@router.message(Command("find"))
async def find_parts(message: Message):
    query = message.text.replace("/find", "").strip()
    if not query:
        return await message.answer("🔍 Напиши запрос после /find")

    await message.answer("📦 Ищу на AliExpress, Ozon, Wildberries...")

    # Имитация — здесь будет реальный парсинг
    results = [f"🔹 {query} — AliExpress", f"🔹 {query} — Ozon", f"🔹 {query} — WB"]
    await message.answer("\n".join(results))

# Остальной код не изменён


@scheduler.scheduled_job("cron", hour=20, minute=0, timezone=pytz.timezone("Asia/Yekaterinburg"))
async def send_daily():
    data = load_homework()
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    if tomorrow in data:
        hw = data[tomorrow]
        text = f"📘 Домашка на завтра ({tomorrow}):\n\n{hw['text']}"
        try:
            await bot.send_message(GROUP_CHAT_ID, text)
        except Exception as e:
            print(f"[Ошибка] Не удалось отправить в группу: {e}")

        for uid in SUBSCRIBERS:
            try:
                await bot.send_message(uid, text)
            except Exception as e:
                print(f"[Ошибка] Не удалось отправить {uid}: {e}")

@router.message(Command("start"))
async def start(message: Message):
    await message.answer("👋 Привет! Я MechaHelper. Набери /help чтобы увидеть список команд.")

@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "📘 Команды MechaHelper:\n"
        "/homework — домашка на завтра\n"
        "/calendar — список всех ДЗ\n"
        "/subscribe — включить уведомления\n"
        "/unsubscribe — выключить уведомления\n"
        "/help — список команд"
    )

@router.message(Command("subscribe"))
async def subscribe(message: Message):
    SUBSCRIBERS.add(message.from_user.id)
    save_subscribers(SUBSCRIBERS)
    await message.answer("✅ Вы подписались на уведомления о домашке!")

@router.message(Command("unsubscribe"))
async def unsubscribe(message: Message):
    if message.from_user.id in SUBSCRIBERS:
        SUBSCRIBERS.remove(message.from_user.id)
        save_subscribers(SUBSCRIBERS)
        await message.answer("❌ Вы отписались от уведомлений.")
    else:
        await message.answer("Вы не были подписаны.")

@router.message(Command("homework"))
async def homework(message: Message):
    data = load_homework()
    date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    if date in data:
        hw = data[date]
        response = f"📘 Домашка на <b>{date}</b>:\n\n{hw['text']}"
        await message.answer(response)
        if "file" in hw:
            path = os.path.join(MEDIA_DIR, hw["file"])
            if hw["file"].endswith(".jpg") or hw["file"].endswith(".png"):
                await message.answer_photo(types.FSInputFile(path))
            elif hw["file"].endswith(".mp4"):
                await message.answer_video(types.FSInputFile(path))
            else:
                await message.answer_document(types.FSInputFile(path))
    else:
        await message.answer("🏖 На завтра пока нет ДЗ.")

@router.message(Command("calendar"))
async def calendar_command(message: Message):
    data = load_homework()
    if not data:
        return await message.answer("📭 Нет заданий.")

    builder = InlineKeyboardBuilder()
    for date in sorted(data):
        builder.button(text=date, callback_data=f"calendar:{date}")

    await message.answer("📅 Выберите дату:", reply_markup=builder.as_markup())

@router.callback_query(lambda c: c.data.startswith("calendar:"))
async def calendar_callback(callback: CallbackQuery):
    date = callback.data.split(":")[1]
    data = load_homework()

    if date not in data:
        return await callback.message.edit_text("⚠️ Задание не найдено.")

    hw = data[date]
    text = f"📘 ДЗ на <b>{date}</b>:\n\n{hw['text']}"
    await callback.message.edit_text(text)

    # Отправка медиафайла, если есть
    if "file" in hw:
        path = os.path.join(MEDIA_DIR, hw["file"])
        try:
            if hw["file"].endswith(".jpg") or hw["file"].endswith(".png"):
                await callback.message.answer_photo(types.FSInputFile(path))
            elif hw["file"].endswith(".mp4"):
                await callback.message.answer_video(types.FSInputFile(path))
            else:
                await callback.message.answer_document(types.FSInputFile(path))
        except Exception as e:
            await callback.message.answer("⚠️ Не удалось отправить файл.")


@router.message(Command("delete"))
async def delete_hw(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Формат: /delete YYYY-MM-DD")
    date = parts[1]
    data = load_homework()
    if date in data:
        if "file" in data[date]:
            try:
                os.remove(os.path.join(MEDIA_DIR, data[date]["file"]))
            except:
                pass
        del data[date]
        save_homework(data)
        await message.answer(f"❌ Домашка на {date} удалена.")
    else:
        await message.answer("Такой даты нет в базе.")


@router.message(Command("sethomework"))
async def set_homework(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Только админ может использовать эту команду.")
        return

    text = message.text.replace("/sethomework", "").strip()
    date = datetime.date.today() + datetime.timedelta(days=1)

    # Если указана дата в начале текста (формат YYYY-MM-DD)
    if text[:10].count("-") == 2:
        try:
            date = datetime.datetime.strptime(text[:10], "%Y-%m-%d").date()
            text = text[11:].strip()
        except ValueError:
            pass

    date_str = date.isoformat()
    data = load_homework()
    hw = {"text": text}

    # Сохраняем медиафайл (если есть)
    if message.document:
        file_name = f"{date_str}_{message.document.file_name}"
        await bot.download(message.document, destination=os.path.join(MEDIA_DIR, file_name))
        hw["file"] = file_name

    elif message.photo:
        file_name = f"{date_str}_photo.jpg"
        await bot.download(message.photo[-1], destination=os.path.join(MEDIA_DIR, file_name))
        hw["file"] = file_name

    elif message.video:
        file_name = f"{date_str}_video.mp4"
        await bot.download(message.video, destination=os.path.join(MEDIA_DIR, file_name))
        hw["file"] = file_name

    data[date_str] = hw
    save_homework(data)

    await message.answer(f"✅ Домашка на {date_str} сохранена!")



# Авторассылка в 20:00
scheduler = AsyncIOScheduler()
scheduler.start()


@router.message()
async def echo_all(message: Message):
    await message.answer("📩 Бот получил сообщение, но не понял. Напиши /hello")

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))