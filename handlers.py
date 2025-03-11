from aiogram import types, Router
from aiogram.filters import Command  # фильтрация событий
from aiogram.fsm.context import FSMContext
from keyboards import admin_keyboard, user_keyboard, cancel_keyboard, deadline_keyboard, confirm_keyboard
from states import TaskStates
from utils import check_if_admin, get_tasks, get_users, get_chat, save_clear, TtC, users_sheet, chats_sheet
from datetime import datetime, timedelta
from utils import bot

router = Router()


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
            reply_markup=admin_keyboard  # Клава для админа
        )
    else:
        tasks_list = get_tasks()
        await message.reply(
            f'Привет, {username}! Нажмите кнопку ниже, чтобы увидеть задачи.\n',
            reply_markup=user_keyboard  # Клава для пользователя
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


# ввод
@router.message(TaskStates.waiting_for_task)
async def process_task(message: types.Message, state: FSMContext):
    username = message.from_user.username
    task_description = message.text.strip()  # Получаем описание задачи после команды

    if task_description == "Отмена":
        await state.clear()  # завершение состояния
        await message.reply('Добавление задачи отменено.',
                            reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard)
        return

    if not task_description:
        await message.reply('Задача не может быть пустой. Напишите задачу.', reply_markup=cancel_keyboard)
        return

    # Сохраняем задачу во временные данные состояния
    await state.update_data(task_description=task_description)
    print(f"Сохранено task_description: {task_description}")  ####### Отладка
    await state.set_state(TaskStates.waiting_for_executive)
    await message.reply("Выберите ответственного:", reply_markup=get_users())


# обработка ответственного
@router.message(TaskStates.waiting_for_executive)
async def process_executive(message: types.Message, state: FSMContext):
    username = message.from_user.username
    executive = message.text.strip()

    if executive == "Отмена":
        await state.clear()  # завершение состояния
        await message.reply("Добавление задачи отменено.",
                            reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard)
        return

    # Проверка, есть ли пользователь в списке
    user = [row[0] for row in users_sheet.get_all_values()[1:]]
    if executive not in user:
        await message.reply("Такого пользователя нет в списке!", reply_markup=get_users())
        return

    await state.update_data(executive=executive)
    print(f"Сохранено executive: {executive}")  ######## Отладка
    await state.set_state(TaskStates.waiting_for_deadline)
    await message.reply("Укажите дедлайн:", reply_markup=deadline_keyboard)


@router.message(TaskStates.waiting_for_deadline)
async def process_deadline(message: types.Message, state: FSMContext):
    username = message.from_user.username
    deadline_i = message.text.strip()
    if deadline_i == "Отмена":
        await state.clear()  # завершение состояния
        await message.reply("Добавление задачи отменено",
                            reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard)
        return

    # выбор дат
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
    print(f"Сохранено deadline: {deadline}")  ##### Отладка
    await state.set_state(TaskStates.waiting_for_chat)
    chat = get_chat()
    if chat:
        await message.reply("Выберите чат для отправки задачи:", reply_markup=chat)
    else:
        await message.reply("'Список чатов пуст. Задача не будет отправлена в чат.", reply_markup=admin_keyboard)
        await save_clear(message, state)


# выбор чата
@router.message(TaskStates.waiting_for_chat)
async def process_chat(message: types.Message, state: FSMContext):
    username = message.from_user.username
    chat_name = message.text.strip()
    if chat_name == "Отмена":
        await save_clear(message, state)
        return

    # проверка наличия чата
    chat = {row[0]: row[1] for row in chats_sheet.get_all_values()[1:] if row[0]}
    if chat_name not in chat:
        await message.reply("Такого чата нет в списке.", reply_markup=get_chat())
        return
    chat_link = chat[chat_name]
    data = await state.get_data()
    print(f"Данные перед сохранением и отправкой: {data}")  ######### Отладка
    if not all(key in data for key in ["task_description", "executive", "deadline"]):
        await message.reply("Ошибка: не все данные задачи заполнены.", reply_markup=admin_keyboard)
        await state.clear()  # завершение состояния
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
        await state.clear()  # завершение состояния
        await message.reply("Заполните задачу заново.", reply_markup=admin_keyboard)
        return
    if choice != "Всё верно":
        await message.reply("Выберите одну из кнопок.", reply_markup=confirm_keyboard)
        return

    data = await state.get_data()
    task_description = data["task_description"]
    executive = data["executive"]
    deadline = data["deadline"]  # Извлечение " - " из состояния
    chat_link = data["chat_link"]
    chat_name = data["chat_name"]

    print(f"Состояние перед TtC: {await state.get_data()}")
    await TtC(chat_link, state, bot)  # отправляет задачу в чат
    await save_clear(message, state)  # сохр и очищ
    task_message = f"Техническое задание:\nОписание: {task_description}\nОтветственный: @{executive}\nДедлайн: {deadline}"
    await bot.send_message(chat_id=message.from_user.id, text=task_message)
    await message.reply(f"Задача отправлена в чат {chat_name}.", reply_markup=admin_keyboard)


# Список задач
@router.message(lambda message: message.text == "Список задач")
async def show_tasks(message: types.Message):
    tasks_list = get_tasks()
    username = message.from_user.username
    await message.reply(
        f'Текущие задачи:\n{tasks_list}',
        reply_markup=admin_keyboard if check_if_admin(username) else user_keyboard
    )
