import os
import json
import datetime
import pytz
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Загрузка переменных окружения
load_dotenv()

# Получаем токен и проверяем его
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Токен бота не найден! Проверьте файл .env")

ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '1862652984').split(',') if id.strip()]
TZ = os.getenv('TZ', 'Asia/Yekaterinburg')

print(f"Токен загружен: {TOKEN[:10]}...")  # Для отладки

DATA_FILE = "homework.json"
SUBSCRIBERS_FILE = "subscribers.json"
MEDIA_DIR = "media"

os.makedirs(MEDIA_DIR, exist_ok=True)

# Инициализация бота
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


# Загрузка/сохранение ДЗ
def load_homework():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Ошибка загрузки homework.json: {e}")
        return {}


def save_homework(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Ошибка сохранения homework.json: {e}")
        return False


# Подписчики
def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, "r") as f:
                return set(json.load(f))
        return set()
    except (json.JSONDecodeError, IOError) as e:
        print(f"Ошибка загрузки subscribers.json: {e}")
        return set()


def save_subscribers(subs):
    try:
        with open(SUBSCRIBERS_FILE, "w") as f:
            json.dump(list(subs), f)
        return True
    except IOError as e:
        print(f"Ошибка сохранения subscribers.json: {e}")
        return False


SUBSCRIBERS = load_subscribers()


# Команды
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
    if save_subscribers(SUBSCRIBERS):
        await message.answer("✅ Вы подписались на уведомления о домашке!")
    else:
        await message.answer("❌ Ошибка при сохранении подписки.")


@router.message(Command("unsubscribe"))
async def unsubscribe(message: Message):
    if message.from_user.id in SUBSCRIBERS:
        SUBSCRIBERS.remove(message.from_user.id)
        if save_subscribers(SUBSCRIBERS):
            await message.answer("❌ Вы отписались от уведомлений.")
        else:
            await message.answer("❌ Ошибка при сохранении изменений.")
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
            try:
                if hw["file"].endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    await message.answer_photo(types.FSInputFile(path))
                elif hw["file"].endswith(('.mp4', '.mov', '.avi')):
                    await message.answer_video(types.FSInputFile(path))
                else:
                    await message.answer_document(types.FSInputFile(path))
            except Exception as e:
                await message.answer("⚠️ Не удалось отправить файл.")
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
    builder.adjust(2)

    await message.answer("📅 Выберите дату:", reply_markup=builder.as_markup())


@router.callback_query(lambda c: c.data.startswith("calendar:"))
async def calendar_callback(callback: CallbackQuery):
    date = callback.data.split(":")[1]
    data = load_homework()

    if date not in data:
        return await callback.answer("⚠️ Задание не найдено.", show_alert=True)

    hw = data[date]
    text = f"📘 ДЗ на <b>{date}</b>:\n\n{hw['text']}"
    await callback.message.edit_text(text)

    if "file" in hw:
        path = os.path.join(MEDIA_DIR, hw["file"])
        try:
            if hw["file"].endswith(('.jpg', '.jpeg', '.png', '.gif')):
                await callback.message.answer_photo(types.FSInputFile(path))
            elif hw["file"].endswith(('.mp4', '.mov', '.avi')):
                await callback.message.answer_video(types.FSInputFile(path))
            else:
                await callback.message.answer_document(types.FSInputFile(path))
        except Exception as e:
            await callback.message.answer("⚠️ Не удалось отправить файл.")

    await callback.answer()


@router.message(Command("delete"))
async def delete_hw(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ У вас нет прав для этой команды.")

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
        if save_homework(data):
            await message.answer(f"❌ Домашка на {date} удалена.")
        else:
            await message.answer("❌ Ошибка при сохранении данных.")
    else:
        await message.answer("Такой даты нет в базе.")


@router.message(Command("sethomework"))
async def set_homework(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ У вас нет прав для этой команды.")

    if not (message.text or message.caption or message.document or message.photo or message.video):
        return await message.answer("❌ Нет данных для сохранения. Добавьте текст или файл.")

    text_content = message.text or message.caption or ""
    text_content = text_content.replace("/sethomework", "").strip()

    date = datetime.date.today() + datetime.timedelta(days=1)

    if text_content and text_content[:10].count("-") == 2:
        try:
            date = datetime.datetime.strptime(text_content[:10], "%Y-%m-%d").date()
            text_content = text_content[11:].strip()
        except ValueError:
            pass

    date_str = date.isoformat()
    data = load_homework()
    hw = {"text": text_content}

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
    if save_homework(data):
        await message.answer(f"✅ Домашка на {date_str} сохранена!")
    else:
        await message.answer("❌ Ошибка при сохранении домашнего задания.")


# Основная функция
async def main():
    print("Запуск бота...")

    # Инициализируем планировщик
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(TZ))

    # Добавляем задание для ежедневной отправки
    @scheduler.scheduled_job("cron", hour=20, minute=0)
    async def send_daily():
        print("Проверка домашнего задания для отправки...")
        data = load_homework()
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        if tomorrow in data:
            hw = data[tomorrow]
            print(f"Отправка ДЗ на {tomorrow} для {len(SUBSCRIBERS)} подписчиков")
            for uid in SUBSCRIBERS:
                try:
                    await bot.send_message(uid, f"📘 Домашка на завтра ({tomorrow}):\n\n{hw['text']}")
                    if "file" in hw:
                        path = os.path.join(MEDIA_DIR, hw["file"])
                        try:
                            if hw["file"].endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                await bot.send_photo(uid, types.FSInputFile(path))
                            elif hw["file"].endswith(('.mp4', '.mov', '.avi')):
                                await bot.send_video(uid, types.FSInputFile(path))
                            else:
                                await bot.send_document(uid, types.FSInputFile(path))
                        except Exception as e:
                            print(f"Ошибка отправки файла: {e}")
                except Exception as e:
                    print(f"Ошибка отправки сообщения пользователю {uid}: {e}")
        else:
            print("На завтра нет домашнего задания")

    # Запускаем планировщик
    scheduler.start()
    print("Планировщик запущен")

    # Запускаем бота
    print("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())