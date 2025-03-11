from aiogram.fsm.state import State, StatesGroup


# Состояния
class TaskStates(StatesGroup):
    waiting_for_task = State()  # Ожидание ввода задачи
    waiting_for_executive = State()  # Состояние для выбора "ответственного"
    waiting_for_deadline = State()  # Состояние для дедлайна
    waiting_for_chat = State()  # Состояние для выбора чата
    waiting_for_confirm = State()  # Состояние для подтверждения задачи
