import gspread
from google.oauth2.service_account import Credentials
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram import types
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from app.keyboards import admin_keyboard, user_keyboard
import json
import os
from dotenv import load_dotenv

# Telegram токен
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise  ValueError("TELEGRAM_TOKEN не найден в переменных окружения")
bot = Bot(token=TOKEN)

# with open("D:/TOKEN/TOKEN.json", "r") as file:
#     config = json.load(file)
# TOKEN = config["telegram_token"]
# bot = Bot(token=TOKEN)

dp = Dispatcher(bot=bot)

# Подключение к Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('../TelegramBot.json', scopes=scope)
client = gspread.authorize(creds)

# Открываем таблицу
spreadsheet = client.open('Tg_bot')  # Google таблица
users_sheet = spreadsheet.worksheet('Users')  # Вкладка с пользователями
tasks_sheet = spreadsheet.worksheet('Tasks')  # Вкладка с задачами
chats_sheet = spreadsheet.worksheet('Chats')  # Вкладка с чатами


# Список пользователей для выбора ответственного
def get_chat():
    chats = chats_sheet.get_all_values()[1:]  # пропуск заголовка
    if not chats:
        return None
    keyboard = [[KeyboardButton(text=chat[0])] for chat in chats if chat[0]]  # Выбор только юсернейма
    keyboard.append([KeyboardButton(text="Отмена")])  # Кнопка отмены
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# Проверка, является ли пользователь админом
def check_if_admin(username):
    data = users_sheet.get_all_values()  # данные из таблицы
    for row in data[1:]:  # пропускаем заголовок
        if row[0] == username:  # проверка имени пользователя
            return row[1] == 'admin'  # True если admin
    return False  # False если нет


# Получение списка задач
def get_tasks():
    tasks = tasks_sheet.get_all_values()[1:]  # Пропускаем заголовок
    if not tasks:
        return 'Задач пока нет.'
    # Строка с задачей, ответственным и дедлайном
    return '\n'.join([
        f'{task[0]}. {task[1]} (Ответственный: @{task[2] if len(task) > 2 else "Не назначен"}, Дедлайн: {task[3] if len(task) > 3 else "Не указан"})'
        for task in tasks])


# Ответственный
def get_users():
    users = users_sheet.get_all_values()[1:]  # Пропускаем заголовок
    keyboard = [[KeyboardButton(text=users[0])] for users in users[0:]]  # Выбор только юсернейма
    keyboard.append([KeyboardButton(text="Отмена")])  # Кнопка отмены
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# сохранение задачи
async def save_clear(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_description = data['task_description']
    executive = data['executive']
    deadline = data['deadline']
    username = message.from_user.username

    # Добавляем задачу в таблицу
    tasks = tasks_sheet.get_all_values()[1:]  # Все задачи, кроме заголовка
    new_task_id = len(tasks) + 1  # Новый ID задачи
    tasks_sheet.append_row([new_task_id, task_description, executive, deadline])
    await message.reply(
        f'Задача "{task_description}" добавлена с ID {new_task_id}. Ответственный: @{executive}. Дедлайн: {deadline}.',
        reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard)
    await state.clear()  # завершение состояния


# отправка в чат
async def TtC(chat_link, state: FSMContext, bot: Bot):
    data = await state.get_data()
    try:
        task_description = data['task_description']
        executive = data['executive']
        deadline = data['deadline']
    except KeyError as e:
        print(f"Ошибка: отсутствует ключ {e} в состоянии {data}")
        return

    task_message = f"Новая задача.\nОписание: {task_description}\nОтветственный: {executive}\nДедлайн: {deadline}"
    # Отправка сообщения в чат
    try:
        await bot.send_message(chat_id=chat_link, text=task_message)
    except Exception as e:
        print(f"Ошибка отправки в чат {chat_link}: {e}")
