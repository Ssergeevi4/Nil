from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# таблички "клавиатура"
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
