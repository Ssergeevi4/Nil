from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command                                                 # фильтрация событий
from aiogram.fsm.context import FSMContext                                          # Для роботы с состояниями (ожидание ботом ввода)
from aiogram.fsm.state import State, StatesGroup                                    # Для определения состояний
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove  # Клава
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta                                            # Для работы с датами
from random import choice
import json

# Telegram токен
with open("D:/TOKEN/TOKEN.json", "r") as file:
    config = json.load(file)
TOKEN = config["telegram_token"]
bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot)
router = Router() #роутер (обработки сообщений)

# Подключение к Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('TelegramBot.json', scopes=scope)
client = gspread.authorize(creds)

# Открываем таблицу
spreadsheet = client.open('Tg_bot')           # Google таблица
users_sheet = spreadsheet.worksheet('Users')  # Вкладка с пользователями
tasks_sheet = spreadsheet.worksheet('Tasks')  # Вкладка с задачами
chats_sheet = spreadsheet.worksheet('Chats')  # Вкладка с чатами

#Состояния
class TaskStates(StatesGroup):
    waiting_for_task = State()          # Ожидание ввода задачи
    waiting_for_executive = State()     # Состояние для выбора "ответственного"
    waiting_for_deadline = State()      # Состояние для дедлайна
    waiting_for_chat = State()          # Состояние для выбора чата
    waiting_for_confirm = State()       # Состояние для подтверждения задачи

#таблички "клавиатура"
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить задачу")],
        [KeyboardButton(text="Список задач")]
    ],
    resize_keyboard=True  # Уменьшает размер кнопок под экран
)

user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Список задач")]
    ],
    resize_keyboard=True
)
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отмена")]
    ],
    resize_keyboard=True
)

deadline_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сегодня"),
         KeyboardButton(text="Завтра"),
         KeyboardButton(text="Через неделю"),
         KeyboardButton(text="Ввести вручную"),
         KeyboardButton(text="Отмена")]
    ],
    resize_keyboard=True
)

confirm_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Всё верно"),
        KeyboardButton(text="Исправить")]
    ],
    resize_keyboard=True

)

# Список пользователей для выбора ответственного
def get_chat():
    chats = chats_sheet.get_all_values()[1:]                                 #пропуск заголовка
    if not chats:
        return None
    keyboard = [[KeyboardButton(text=chat[0])] for chat in chats if chat[0]] # Выбор только юсернейма
    keyboard.append([KeyboardButton(text="Отмена")])                         # Кнопка отмены
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Проверка, является ли пользователь админом
def check_if_admin(username):
    data = users_sheet.get_all_values() # данные из таблицы
    for row in data[1:]:                # пропускаем заголовок
        if row[0] == username:          # проверка имени пользователя
            return row[1] == 'admin'    # True если admin
    return False                        # False если нет

# Получение списка задач
def get_tasks():
    tasks = tasks_sheet.get_all_values()[1:]  # Пропускаем заголовок
    if not tasks:
        return 'Задач пока нет.'
    # Строка с задачей, ответственным и дедлайном
    return '\n'.join([f'{task[0]}. {task[1]} (Ответственный: @{task[2] if len(task) > 2 else "Не назначен"}, Дедлайн: {task[3] if len(task) > 3 else "Не указан"})' for task in tasks])

#Ответственный
def get_users():
    users = users_sheet.get_all_values()[1:]                                # Пропускаем заголовок
    keyboard = [[KeyboardButton(text=users[0])] for users in users[0:]]     # Выбор только юсернейма
    keyboard.append([KeyboardButton(text="Отмена")])                        # Кнопка отмены
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Обработчик команды /start
@router.message(Command('start'))
async def start_command(message: types.Message):
    username = message.from_user.username  # Получаем Telegram-username
    if not username:
        await message.reply('У вас нет username в Telegram. Установите его в настройках.')
        return

    if check_if_admin(username):
        await message.reply(
            f'Привет, {username}! Вы администратор, вам доступны следующие команды.\n',
            reply_markup=admin_keyboard         # Клава для админа
        )
    else:
        tasks_list = get_tasks()
        await message.reply(
            f'Привет, {username}! Нажмите кнопку ниже, чтобы увидеть задачи.\n',
            reply_markup=user_keyboard         # Клава для пользователя
        )

# Обработчик команды add_task (admin)
@router.message(lambda message: message.text == "Добавить задачу")
async def add_task_button(message: types.Message, state: FSMContext):
    username = message.from_user.username
    if not check_if_admin(username):
        await message.reply('У вас нет прав для добавления задач.', reply_markup=user_keyboard)
        return

    await state.set_state(TaskStates.waiting_for_task)
    await message.reply('Теперь напишите задачу, которую хотите добавить.', reply_markup=cancel_keyboard)


#ввод
@router.message(TaskStates.waiting_for_task)
async def process_task(message: types.Message, state: FSMContext):
    username = message.from_user.username
    task_description = message.text.strip()  # Получаем описание задачи после команды

    if task_description == "Отмена":
        await state.clear()         # завершение состояния
        await message.reply('Добавление задачи отменено.',
                            reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard)
        return

    if not task_description:
        await message.reply('Задача не может быть пустой. Напишите задачу.', reply_markup=cancel_keyboard)
        return

# Сохраняем задачу во временные данные состояния
    await state.update_data(task_description=task_description)
    print(f"Сохранено task_description: {task_description}") ####### Отладка
    await state.set_state(TaskStates.waiting_for_executive)
    await message.reply("Выберите ответственного:", reply_markup=get_users())

# обработка ответственного
@router.message(TaskStates.waiting_for_executive)
async def process_executive(message: types.Message, state: FSMContext):
    username = message.from_user.username
    executive = message.text.strip()

    if executive == "Отмена":
        await state.clear()         # завершение состояния
        await message.reply("Добавление задачи отменено.", reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard)
        return

# Проверка, есть ли пользователь в списке
    user = [row[0] for row in users_sheet.get_all_values()[1:]]
    if executive not in user:
        await message.reply("Такого пользователя нет в списке!", reply_markup=get_users())
        return

    await state.update_data(executive=executive)
    print(f"Сохранено executive: {executive}") ######## Отладка
    await state.set_state(TaskStates.waiting_for_deadline)
    await message.reply("Укажите дедлайн:", reply_markup=deadline_keyboard)

@router.message(TaskStates.waiting_for_deadline)
async def process_deadline(message: types.Message, state: FSMContext):
    username = message.from_user.username
    deadline_i = message.text.strip()
    if deadline_i == "Отмена":
        await state.clear()         # завершение состояния
        await message.reply("Добавление задачи отменено", reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard)
        return

#выбор дат
    today = datetime.now()
    if deadline_i == "Сегодня":
        deadline = today.strftime("%d.%m.%Y")
    elif deadline_i == "Завтра":
        deadline = (today + timedelta(days=1)).strftime("%d.%m.%Y")
    elif deadline_i == "Через неделю":
        deadline = (today + timedelta(days=7)).strftime("%d.%m.%Y")
    elif deadline_i == "Ввести в ручную":
        await message.reply("Введите дату в формате дд.мм.гггг", reply_markup=cancel_keyboard)
        return  # ожидание ввода
    else:
        # проверка даты на корректность
        try:
            deadline = datetime.strptime(deadline_i, "%d.%m.%Y").strftime("%d.%m.%Y")
        except ValueError:
            await message.reply("Неверный формат даты! (Пример - 11.11.2025)", reply_markup=cancel_keyboard)
            return

    await state.update_data(deadline=deadline)
    print(f"Сохранено deadline: {deadline}") ##### Отладка
    await state.set_state(TaskStates.waiting_for_chat)
    chat = get_chat()
    if chat:
        await message.reply("Выберите чат для отправки задачи:", reply_markup=chat)
    else:
        await message.reply("'Список чатов пуст. Задача не будет отправлена в чат.", reply_markup=admin_keyboard)
        await save_clear(message, state)

#выбор чата
@router.message(TaskStates.waiting_for_chat)
async def process_chat(message: types.Message, state: FSMContext):
    username = message.from_user.username
    chat_name = message.text.strip()
    if chat_name == "Отмена":
        await save_clear(message, state)
        return

#проверка наличия чата
    chat = {row[0]: row[1] for row in chats_sheet.get_all_values()[1:] if row[0]}
    if chat_name not in chat:
        await message.reply("Такого чата нет в списке.", reply_markup=get_chat())
        return
    chat_link = chat[chat_name]
    data = await state.get_data()
    print(f"Данные перед сохранением и отправкой: {data}") ######### Отладка
    if not all(key in data for key in ["task_description","executive", "deadline"]):
        await message.reply("Ошибка: не все данные задачи заполнены.", reply_markup=admin_keyboard)
        await state.clear()         # завершение состояния
        return

    await state.update_data(chat_link=chat_link, chat_name=chat_name)
    task_description = data["task_description"]
    executive = data["executive"]
    deadline = data["deadline"]
    confirm_message = (f"Проверьте данные задачи:\n"
        f"Описание: {task_description}\n"
        f"Ответственный: @{executive}\n"
        f"Дедлайн: {deadline}\n"
        f"Чат: {chat_name}\n"
        "Всё верно?")
    await state.set_state(TaskStates.waiting_for_confirm)
    await message.reply(confirm_message, reply_markup=confirm_keyboard)

@router.message(TaskStates.waiting_for_confirm)
async def process_confirm(message: types.Message, state: FSMContext):
    username = message.from_user.username
    choice = message.text.strip()
    if choice == "Исправить":
        await state.clear()         # завершение состояния
        await message.reply("Заполните задачу заново.", reply_markup=admin_keyboard)
        return
    if choice != "Всё верно":
        await message.reply("Выберите одну из кнопок.", reply_markup=confirm_keyboard)
        return

    data = await state.get_data()
    task_description = data["task_description"]
    executive = data["executive"]
    deadline = data["deadline"]                         # Извлечение " - " из состояния
    chat_link = data["chat_link"]
    chat_name = data["chat_name"]

    print(f"Состояние перед TtC: {await state.get_data()}")
    await TtC(chat_link, state)                     #отправляет задачу в чат
    await save_clear(message, state)                #сохр и очищ
    task_message = f"Техническое задание:\nОписание: {task_description}\nОтветственный: @{executive}\nДедлайн: {deadline}"
    await bot.send_message(chat_id=message.from_user.id, text=task_message)
    await message.reply(f"Задача отправлена в чат {chat_name}.", reply_markup=admin_keyboard)

#сохранение задачи
async def save_clear(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_description = data['task_description']
    executive = data['executive']
    deadline = data['deadline']
    username = message.from_user.username

    # Добавляем задачу в таблицу
    tasks = tasks_sheet.get_all_values()[1:]    # Все задачи, кроме заголовка
    new_task_id = len(tasks) + 1                # Новый ID задачи
    tasks_sheet.append_row([new_task_id, task_description, executive, deadline])
    await message.reply(f'Задача "{task_description}" добавлена с ID {new_task_id}. Ответственный: @{executive}. Дедлайн: {deadline}.',
    reply_markup = admin_keyboard if check_if_admin(username) else user_keyboard)
    await state.clear()                         # завершение состояния

#отправка в чат
async def TtC(chat_link, state: FSMContext):
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

#Список задач
@router.message(lambda message: message.text == "Список задач")
async def show_tasks(message: types.Message):
    tasks_list = get_tasks()
    username = message.from_user.username
    await message.reply(
        f'Текущие задачи:\n{tasks_list}',
        reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard
    )


# Регистрируем роутер в диспетчере
dp.include_router(router)

# Запуск бота
async def main():
    print('Бот запущен...')
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())