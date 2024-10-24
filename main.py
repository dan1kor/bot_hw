import asyncio

import sqlite3


import aioschedule
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram import types
from aiogram.utils.chat_action import ChatActionSender
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup


class Form(StatesGroup):
    waiting_for_deadline_name = State()
    waiting_for_deadline_day = State()
    waiting_for_deadline_time = State()
    waiting_for_deadline_id_to_delete = State()
    waiting_for_deadline_id_to_edit = State()
    waiting_for_action = State()
    waiting_for_change = State()


connection = sqlite3.connect("my_database.db")
cursor = connection.cursor()


def create_database():
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id       INTEGER PRIMARY KEY AUTOINCREMENT
                               UNIQUE
                               NOT NULL,
        user_name      TEXT    UNIQUE
                               NOT NULL,
        chat_id        TEXT    UNIQUE
                               NOT NULL
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS deadlines (
        deadline_id           INTEGER PRIMARY KEY AUTOINCREMENT
                                      UNIQUE
                                      NOT NULL,
        deadline_name         TEXT    NOT NULL,
        user_name               INTEGER,
        deadline_day          TEXT    NOT NULL,
        deadline_time         TEXT    NOT NULL,
        FOREIGN KEY (
            user_name
        )
        REFERENCES users (user_name) 
    );
    ''')
    connection.commit()


def add_user(user_name, chat_id):
    if not get_user_id(user_name):
        cursor.execute('''
        INSERT INTO users (user_name, chat_id)
            VALUES (?, ?)
        ''', (user_name, chat_id))
        connection.commit()
        return f'Добро пожаловать, {user_name}!' \
               f' Надеюсь на продуктивное сотрудничество с вами'
    return f'{user_name}, мы уже знакомы'


def get_user_id(user_name):
    cursor.execute(f'''
    SELECT user_id
    FROM users
    WHERE user_name = '{user_name}'
    ''')
    user_id = cursor.fetchall()
    return user_id


def get_chat_id(user_name):
    cursor.execute(f'''
    SELECT chat_id
    FROM users
    WHERE user_name = {user_name}
    ''')
    chat_id = cursor.fetchone()
    return chat_id[0]


def add_deadline(name, day, time, user_name):
    cursor.execute('''
    INSERT INTO deadlines (deadline_name, user_name, deadline_day, deadline_time)
    VALUES (?, ?, ?, ?)
    ''', (name, user_name, day, time))
    connection.commit()


def get_deadlines(user_name):
    cursor.execute(f'''
        SELECT *
        FROM deadlines
        WHERE user_name = '{user_name}'
        ''')
    deadlines = cursor.fetchall()
    return deadlines


def delete_deadlines(user_name):
    cursor.execute('''
    DELETE FROM deadlines WHERE user_name = ?
    ''', (user_name,))
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='deadlines'")
    connection.commit()


def delete_deadline(dd_id):
    cursor.execute('''
    DELETE FROM deadlines WHERE deadline_id = ?
    ''', (dd_id,))

    cursor.execute("""
        UPDATE deadlines
        SET deadline_id = deadline_id - 1
        WHERE deadline_id > ?
    """, (dd_id,))

    connection.commit()


def edit_deadline_name(dd_id, change):
    cursor.execute("""
            UPDATE deadlines
            SET deadline_name = ?
            WHERE deadline_id = ?
        """, (change, dd_id))
    connection.commit()


def edit_deadline_day(dd_id, change):
    cursor.execute("""
                UPDATE deadlines
                SET deadline_day = ?
                WHERE deadline_id = ?
            """, (change, dd_id))
    connection.commit()


def edit_deadline_time(dd_id, change):
    cursor.execute("""
                    UPDATE deadlines
                    SET deadline_time = ?
                    WHERE deadline_id = ?
                """, (change, dd_id))
    connection.commit()


def get_today_deadlines(date):
    cursor.execute(f'''
            SELECT *
            FROM deadlines
            WHERE deadline_day = '{date}' and user_name = {USER_NAME}
            ''')
    deadlines = cursor.fetchall()
    return deadlines


BOT_TOKEN = ('7682260748:AAHz4vmhuxvOCKjFTyD86fAJqPGMYh30ZaA')
USER_NAME = None

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()


@router.message(Command('start'))
async def send_hello(message: types.Message):
    global USER_NAME
    USER_NAME = message.from_user.username
    create_database()
    fb = add_user(message.from_user.username, message.chat.id)
    await message.answer(fb)


@router.message(Command('help'))
async def send_help(message: types.Message):
    await message.answer('Здесь будет инструкция, когда функционал будет готов')


@router.message(Command('show_user'))
async def send_user_info(message: types.Message):
    user_name = message.from_user.username
    deadlines_counter = get_user_id(user_name)
    await message.answer(f'Ваш ID: {deadlines_counter[0][0]} \n'
                         f'Количество ваших дедлайнов: {len(get_deadlines(user_name))}')


@router.message(Command('set_deadline'))
async def set_deadline_intro(message: types.Message, state: FSMContext):
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        await asyncio.sleep(1)
        await message.answer('Введи название дедлайна')
    await state.set_state(Form.waiting_for_deadline_name)


@router.message(Command('show_deadlines'))
async def send_deadlines(message: types.Message):
    deadlines = get_deadlines(message.from_user.username)
    msg = ''
    if len(deadlines) > 0:
        for dd in deadlines:
            line = f'❌ {str(dd[0])}: {dd[1]} до {dd[4]}, {dd[3]}'
            msg += line + '\n'

        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="Редактировать/удалить дедлайны",
            callback_data="delete_or_edit_deadlines")
        )
        await message.answer(msg, reply_markup=builder.as_markup())
    else:
        await message.answer('Тут пока пусто')


@dp.callback_query(F.data == "delete_or_edit_deadlines")
async def delete_or_edit_deadlines(callback: types.CallbackQuery):
    kb = [
        [
            types.KeyboardButton(text="Редактировать дедлайн"),
            types.KeyboardButton(text="Удалить дедлайн"),
            types.KeyboardButton(text="Удалить все дедлайны")
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выбери, что хочешь"
    )
    await callback.message.answer("Что именно ты хочешь?", reply_markup=keyboard)
    await callback.answer()


@router.message(F.text.lower() == 'редактировать дедлайн')
async def edit_deadline_req(message: types.Message, state: FSMContext):
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        await asyncio.sleep(1)
        await message.answer('Введи номер дд для редактирования', reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Form.waiting_for_deadline_id_to_edit)


@router.message(F.text, Form.waiting_for_deadline_id_to_edit)
async def capture_deadline_id(message: types.Message, state: FSMContext):
    dd_id, user_name = message.text, message.from_user.username

    if not check_deadline_id(dd_id, user_name):
        await message.reply('Введи корректный номер')
        return

    await state.update_data(deadline_id=dd_id)

    kb = [
        [
            types.KeyboardButton(text="Редактировать название"),
            types.KeyboardButton(text="Редактировать дату"),
            types.KeyboardButton(text="Редактировать время")
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выбери, что хочешь"
    )
    await message.answer("Что именно ты хочешь?", reply_markup=keyboard)
    await state.set_state(Form.waiting_for_action)


@router.message(F.text, Form.waiting_for_action)
async def delete_deadline_req(message: types.Message, state: FSMContext):
    if ((message.text.lower() == 'редактировать название')
            or (message.text.lower() == 'редактировать дату')
            or (message.text.lower() == 'редактировать время')):
        await state.update_data(action_id=message.text.lower().split()[1])
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            await asyncio.sleep(1)
            await message.answer(f'Введи нов(ое/ую) {message.text.lower().split()[1]}',
                                 reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Form.waiting_for_change)
    else:
        await message.reply('Такого варианта нет')
        return


@router.message(F.text, Form.waiting_for_change)
async def delete_deadline_req(message: types.Message, state: FSMContext):
    data = await state.get_data()
    action_id = data.get('action_id')
    dd_id = data.get('deadline_id')

    change = message.text
    if action_id == 'название':
        edit_deadline_name(dd_id, change)
    elif action_id == 'дату':
        check_day = check_deadline_day(message.text)
        if not check_day:
            await message.reply('Пожалуйста, введи корректную дату дедлайна в формате день.месяц')
            return
        edit_deadline_day(dd_id, change)
    else:
        check_time = check_deadline_time(message.text)
        if not check_time:
            await message.reply('Пожалуйста, введи корректное время дедлайна в формате часы:день')
            return
        edit_deadline_time(dd_id, change)
    await state.clear()
    await message.answer('Дедлайн успешно редактирован')


@router.message(F.text.lower() == 'удалить дедлайн')
async def delete_deadline_req(message: types.Message, state: FSMContext):
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        await asyncio.sleep(1)
        await message.answer('Введи номер дедлайна для удаления', reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Form.waiting_for_deadline_id_to_delete)


@router.message(F.text, Form.waiting_for_deadline_id_to_delete)
async def capture_deadline_id(message: types.Message, state: FSMContext):
    dd_id, user_name = message.text, message.from_user.username

    if not check_deadline_id(dd_id, user_name):
        await message.reply('Введи корректный номер')
        return

    delete_deadline(dd_id)
    await message.answer('Ваш дедлайн успешно удалён')
    await state.clear()


@router.message(F.text.lower() == 'удалить все дедлайны')
async def delete_all_deadlines_req(message: types.Message):
    delete_deadlines(message.from_user.username)
    await message.answer('Твои дедлайны удалены', reply_markup=types.ReplyKeyboardRemove())


@router.message(F.text, Form.waiting_for_deadline_name)
async def capture_deadline_name(message: types.Message, state: FSMContext):
    await state.update_data(deadline_name=message.text)
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        await asyncio.sleep(1)
        await message.answer('Введи дату дедлайна в формате день.месяц')
    await state.set_state(Form.waiting_for_deadline_day)


@router.message(F.text, Form.waiting_for_deadline_day)
async def capture_deadline_day(message: types.Message, state: FSMContext):
    check_day = check_deadline_day(message.text)
    if not check_day:
        await message.reply('Пожалуйста, введи корректную дату дедлайна в формате день.месяц')
        return
    await state.update_data(deadline_day=check_day)

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        await asyncio.sleep(1)
        await message.answer('Введи время дедлайна в формате часы:минуты')
    await state.set_state(Form.waiting_for_deadline_time)


@router.message(F.text, Form.waiting_for_deadline_time)
async def capture_deadline_time(message: types.Message, state: FSMContext):
    check_time = check_deadline_time(message.text)
    if not check_time:
        await message.reply('Пожалуйста, введи корректное время в формате часы:минуты')
        return
    await state.update_data(deadline_time=check_time)

    data = await state.get_data()
    add_deadline(data.get('deadline_name'), data.get('deadline_day'),
                 data.get('deadline_time'), message.from_user.username)
    await message.answer('Ваш дедлайн успешно добавлен')
    await state.clear()


def check_deadline_day(data):
    try:
        day, month = [int(i) for i in data.split('.')]
    except ValueError:
        return False
    if not (1 <= month <= 12):
        return False
    if month in [1, 3, 5, 7, 8, 10, 12]:
        if 1 <= day <= 31:
            return f'{day}.{month}'
    if month == 2:
        if 1 <= day <= 28:
            return f'{day}.{month}'
    else:
        if 1 <= day <= 30:
            return f'{day}.{month}'
    return False


def check_deadline_time(time):
    try:
        hours, minutes = [int(i) for i in time.split(':')]
    except ValueError:
        return False
    if 0 <= hours <= 23 and 0 <= minutes <= 59:
        return f'{hours}:{minutes}'
    return False


def check_deadline_id(dd_id, user_name):
    try:
        dd_id = int(dd_id)
    except ValueError:
        return False

    if not (1 <= dd_id <= len(get_deadlines(user_name))):
        return False
    return dd_id


def check_deadlines_daily():
    global USER_NAME
    # try:
    #     print('я в чек дедлайнс')
    #     if USER_NAME:
    #         chat_id = get_chat_id(USER_NAME)
    #         print(chat_id)
    #         date = str(datetime.date.today())
    #         cur_day = int(date.split('-')[-1])
    #         cur_month = int(date.split('-')[-2])
    #         date_str = f'{cur_day}.{cur_month}'
    #
    #         msg = 'Сегодняшние дедлайны:\n'
    #         deadlines = get_today_deadlines(date_str)
    #         if len(deadlines) > 0:
    #             for dd in deadlines:
    #                 line = f'❌ {str(dd[0])}: {dd[1]} до {dd[4]}, {dd[3]}'
    #                 msg += line + '\n'
    #         print(msg)
    #         bot.send_message(chat_id=chat_id, text=msg)
    #     else:
    #         print('BOT HAS NOT BEEN STARTED')
    # except Exception as e:
    #     print(f'Error: {e}')


async def schedule_deadline():
    global USER_NAME
    aioschedule.every().day.at('09:00').do(check_deadlines_daily)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(10)


async def main():
    dp.include_router(router)
    asyncio.create_task(schedule_deadline())
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
