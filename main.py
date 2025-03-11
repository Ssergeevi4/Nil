from aiogram import Bot, Dispatcher
from utils import dp, bot
from handlers import router


# Регистрируем роутер в диспетчере
dp.include_router(router)


# Запуск бота
async def main():
    print('Бот запущен...')
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
