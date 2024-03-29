from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
from aiogram.types import Message
from aiogram import executor
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton
import aiosqlite
import pytz
import time
from datetime import datetime, timezone
import asyncio

API_TOKEN = '7070823778:AAH9yYNf99tOtSxYfKAueqvlS_Km9VMI-h0'
OPERATORS = ['989037374']
CHANNEL_NAME = '-1002007209581'

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class Form(StatesGroup):
    waiting_for_question = State()
class QuestionState(StatesGroup):
    waiting_for_question = State()


async def on_startup(dp):
    async with aiosqlite.connect('users.db') as db:
        await db.execute("""
		CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY,
			username TEXT,
			is_operator BOOLEAN,
			last_action TIMESTAMP
		)
	""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            operator_id INTEGER, 
            status TEXT, 
            question TEXT,
            channel_message_id INTEGER
        )
    """)
        await db.commit()
        for operator_id in OPERATORS:
            await db.execute("INSERT OR IGNORE INTO users (id, is_operator) VALUES (?, ?)",
                             (operator_id, True))
            await db.commit()


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    args = message.get_args()
    if args.startswith('ticket_'):
        ticket_id = args.split('_')[1]
        user_id = message.from_user.id

        async with aiosqlite.connect('users.db') as db:
            cursor = await db.execute("SELECT is_operator FROM users WHERE id = ?", (user_id,))
            is_operator = await cursor.fetchone()

            if is_operator and is_operator[0]:
                confirm_button = InlineKeyboardMarkup().add(InlineKeyboardButton("Взять тикет", callback_data=f"confirm_take_{ticket_id}"))
                await message.answer(f"Вы уверены, что хотите взять тикет #{ticket_id}?", reply_markup=confirm_button)
            else:
                await message.answer("Извините, эта функция доступна только операторам.")

    elif str(message.from_user.id) not in OPERATORS:
        await send_welcome(message)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton('Завершить диалог'))
        await message.answer("*Вы являетесь оператором\.* Пожалуйста, перейдите в канал для приема тикетов\.\n\nhttps://t\.me/\+7X4aYo5LQLxmNTYy", reply_markup=markup,parse_mode="MarkdownV2")

async def send_welcome(message: types.Message):
    async with aiosqlite.connect('users.db') as db:
        user_id = message.from_user.id
        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        user = await cursor.fetchone()

        if not user:
            await db.execute("INSERT INTO users (id, last_action) VALUES (?, '2000-01-01 00:00:00')", (user_id,))
            await db.commit()
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('❓ Задать вопрос'), KeyboardButton('📚 База знаний'))
    await message.answer("Привет\! Это \- бот технической поддержки\.\nПожалуйста, перед тем как задать вопрос, *ознакомьтесь с нашей базой знаний\.* Скорее всего, там вы найдете ответ на свой вопрос\.", reply_markup=markup, parse_mode="MarkdownV2")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('confirm_take'))
async def handle_confirm_take(callback_query: types.CallbackQuery):
    ticket_id = callback_query.data.split('_')[2]
    operator_id = callback_query.from_user.id

    async with aiosqlite.connect('users.db') as db:
        await db.execute("UPDATE tickets SET operator_id = ?, status = 'в обработке' WHERE id = ?", (operator_id, ticket_id))
        await db.commit()

        cursor = await db.execute("SELECT user_id, channel_message_id FROM tickets WHERE id = ?", (ticket_id,))
        user_id, channel_message_id = await cursor.fetchone()

        if user_id:
            await bot.send_message(user_id, "Оператор найден и уже рассматривает вашу проблему. Пожалуйста, подождите.")
            if channel_message_id:
                await bot.edit_message_text(chat_id=CHANNEL_NAME, message_id=channel_message_id, text=f"Тикет #{ticket_id} взят оператором", reply_markup=None)

            await callback_query.message.edit_text(f"Вы взяли тикет \#{ticket_id}\. Теперь можно общаться с пользователем\.\n\nДля завершения диалога используйте кнопку *Завершить диалог*", reply_markup=None,parse_mode="MarkdownV2")


@dp.message_handler(lambda message: message.text == "📚 База знаний")
async def show_knowledge_base_categories(message: types.Message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(text="⚛️ Атомы", callback_data="category_atoms"),
               types.InlineKeyboardButton(text="👦 Молекулы", callback_data="category_molecules"),
               types.InlineKeyboardButton(text="🐜 Муравьи", callback_data="category_ants"))
    await message.answer("Выберите категорию:", reply_markup=markup)

user_last_choice = {}
@dp.callback_query_handler(lambda c: c.data.startswith('category_'))
async def show_subcategories(callback_query: types.CallbackQuery):
    action = callback_query.data.split('_')[1]
    user_last_choice[callback_query.from_user.id] = callback_query.data
    markup = types.InlineKeyboardMarkup(row_width=1)

    if action == "atoms":
        markup.add(types.InlineKeyboardButton(text="Протоны", callback_data="atoms_protons"),
                   types.InlineKeyboardButton(text="Электроны", callback_data="atoms_electrons"),
                   types.InlineKeyboardButton(text="Нейтроны", callback_data="atoms_neutrons"))
        text = "⚛️ Атомы: выберите интересующую тему"

    elif action == "molecules":
        markup.add(types.InlineKeyboardButton(text="Вода H2O", callback_data="molecules_water"),
                   types.InlineKeyboardButton(text="Углекислый газ CO2", callback_data="molecules_co2"),
                   types.InlineKeyboardButton(text="Озон O3", callback_data="molecules_o3"))
        text = "👦 Молекулы: выберите интересующую тему"

    elif action == "ants":
        markup.add(types.InlineKeyboardButton(text="Образ жизни муравьев", callback_data="ants_lifestyle"),
                   types.InlineKeyboardButton(text="Питание муравьев", callback_data="ants_food"),
                   types.InlineKeyboardButton(text="Муравьи и экосистема", callback_data="ants_ecosystem"))
        text = "🐜 Муравьи: выберите интересующую тему"
    markup.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data ="go_back_to_categories"))


    await bot.edit_message_text(text=text, chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'go_back_to_categories')
async def go_back_to_categories(callback_query: types.CallbackQuery):
    await show_knowledge_base_categories(callback_query.message)
    await callback_query.message.delete()

@dp.callback_query_handler(lambda c: c.data.startswith('atoms_') or
                                     c.data.startswith('molecules_') or
                                     c.data.startswith('ants_'))
async def show_information(callback_query: types.CallbackQuery):
    data = callback_query.data
    info = "Информация не найдена."

    if data == "atoms_protons":
        info = "Протон – это субатомная частица, имеющая положительный электрический заряд."
    elif data == "atoms_electrons":
        info = "Электрон – это субатомная частица, имеющая отрицательный электрический заряд."
    elif data == "atoms_neutrons":
        info = "Нейтрон – это субатомная частица без электрического заряда."

    elif data == "molecules_water":
        info = "Вода (H2O) – это молекула, состоящая из двух атомов водорода и одного атома кислорода."
    elif data == "molecules_co2":
        info = "Углекислый газ (CO2) – это молекула, состоящая из одного атома углерода и двух атомов кислорода."
    elif data == "molecules_o3":
        info = "Озон (O3) – это молекула, состоящая из трех атомов кислорода, играет важную роль в защите Земли от ультрафиолетового излучения."

    elif data == "ants_lifestyle":
        info = "Муравьи – это социальные насекомые, живущие колониями. Есть рабочие муравьи, солдаты, и королева."
    elif data == "ants_food":
        info = "Муравьи могут питаться растительной пищей, другими насекомыми, а также подсластителями, которые вырабатываются некоторыми растениями и насекомыми."
    elif data == "ants_ecosystem":
        info = "Муравьи играют ключевую роль в экосистемах как разлагатели органического вещества, опылители растений и как пища для других видов животных."

    await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                text=info,
                                reply_markup=types.InlineKeyboardMarkup())

@dp.message_handler(user_id=OPERATORS)
async def forward_to_user(message: types.Message):
    if message.text.startswith('Завершить диалог'):
        await cmd_stop(message)
    else:
        operator_id = message.from_user.id

        async with aiosqlite.connect('users.db') as db:
            cursor = await db.execute("SELECT id, user_id FROM tickets WHERE operator_id = ? AND status = 'в обработке'", (operator_id,))
            ticket_info = await cursor.fetchone()

            if ticket_info:
                _, user_id = ticket_info
                await bot.send_message(user_id, message.text)
            else:
                await message.reply("В настоящее время у вас нет активных тикетов.")

@dp.message_handler(lambda message: message.text == "❓ Задать вопрос")
async def ask_question(message: types.Message):
    await QuestionState.waiting_for_question.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, selective=True).add("❌ Закрыть вопрос")
    await message.reply("Прежде чем задавать вопрос, рекомендуем поискать ответ на него в нашей *Базе знаний*\. Чтобы вернуться к ней, нажмите *❌ Закрыть вопрос*\.\n\n Если ответ там не был найден, задайте его здесь:", reply_markup=markup, parse_mode="MarkdownV2")


@dp.message_handler(Text(equals='❌ Закрыть вопрос', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id

    async with aiosqlite.connect('users.db') as db:
        cursor = await db.execute("""
            SELECT id, operator_id, channel_message_id FROM tickets
            WHERE user_id = ? AND status != 'закрыт'
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        ticket_info = await cursor.fetchone()
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton('❓ Задать вопрос'), KeyboardButton('📚 База знаний'))
        if ticket_info:
            ticket_id, operator_id, channel_message_id = ticket_info

            if operator_id:
                await bot.send_message(operator_id, f"Пользователь закрыл тикет \#{ticket_id}\. *Диалог завершен\.*",parse_mode="MarkdownV2")

            await db.execute("UPDATE tickets SET status = 'закрыт' WHERE id = ?", (ticket_id,))
            await db.commit()

            if channel_message_id:
                await bot.edit_message_text(chat_id=CHANNEL_NAME, message_id=channel_message_id,
                                            text=f"Пользователь закрыл тикет #{ticket_id}")
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(KeyboardButton('❓ Задать вопрос'), KeyboardButton('📚 База знаний'))
            await message.answer("Вопрос закрыт. Пожалуйста, пользуйтесь кнопками.",reply_markup=markup)
        else:
            await message.answer("Вопрос закрыт. Пожалуйста, пользуйтесь кнопками.",reply_markup=markup)


knowledge_base = [
    {"keywords": ["протон", "заряд", "электричество", "протоном", "положительный","положительным", "заряда", "зарядом", "зарядами","положительными"],
     "answer": "Протон – это субатомная частица, имеющая положительный электрический заряд."},
    {"keywords": ["электрон", "заряд", "электричество", "протоном", "отрицательный","отрицательным", "заряда", "зарядом", "зарядами","отрицательными"],
     "answer": "Электрон – это субатомная частица, имеющая отрицательный электрический заряд."},
    {"keywords": ["нейтрон", "нейтральный", "заряд", "нейтрона", "нейтронами", "нейтроном", "заряда", "зарядом", "зарядами"],
     "answer": "Нейтрон – это субатомная частица без электрического заряда."},

    {"keywords": ["вода", "h2o", "молекула", "воды", "молекулы", "водой"],
     "answer": "Вода (H2O) – это молекула, состоящая из двух атомов водорода и одного атома кислорода."},
    {"keywords": ["углекислый газ", "co2", "молекула", "молекулы", "углекислый", "углекислого", "углекислым", "газ", "газом", "газами", "газа", "сектор газа", "палестина"],
     "answer": "Углекислый газ (CO2) – это молекула, состоящая из одного атома углерода и двух атомов кислорода."},
    {"keywords": ["озон", "o3", "молекула", "о3", "молекулы", "озоновый", "озона", "озоном", "роль", "ультрафиолет", "ультрафиолетового", "ультрафиолетовый"],
     "answer": "Озон (O3) – это молекула, состоящая из трех атомов кислорода, играет важную роль в защите Земли от ультрафиолетового излучения."},

    {"keywords": ["муравьи", "образ жизни", "образ", "жизни", "муравей", "муравья"],
     "answer": "Муравьи – это социальные насекомые, живущие колониями. Есть рабочие муравьи, солдаты, и королева."},
    {"keywords": ["питание", "муравьи", "муравей", "муравья", "питается", "ест", "жрет", "употребляет", "потребляет"],
     "answer": "Муравьи могут питаться растительной пищей, другими насекомыми, а также подсластителями, которые вырабатываются некоторыми растениями и насекомыми."},
    {"keywords": ["муравьи", "экосистема", "муравей", "муравья", "система", "эко", "роль", "зачем"],
     "answer": "Муравьи играют ключевую роль в экосистемах как разлагатели органического вещества, опылители растений и как пища для других видов животных."},
]

def search_knowledge(query):
    query_words = set(query.lower().split())
    results = []

    for item in knowledge_base:
        if query_words & set(item["keywords"]):
            results.append(item["answer"])

    return results

@dp.callback_query_handler(lambda c: c.data and c.data == 'yes_call')
async def yes_call(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton('Да, позовите оператора', callback_data='handle_operator'))
    await bot.send_message(user_id,"Вы уверены, что информации *нет в базе знаний* и необходим оператор?\nЕсли вы не уверены, пожалуйста, нажмите *❌ Закрыть вопрос* и проверьте наличие нужной вам информации в базе знаний\.", reply_markup=inline_kb, parse_mode="MarkdownV2")

@dp.callback_query_handler(lambda c: c.data and c.data == 'handle_operator')
async def handle_operator_callback(callback_query: types.CallbackQuery):

    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    question_text = user_questions.get(user_id, "Нужна помощь оператора")
    if not await check_user_timeout(user_id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton('❓ Задать вопрос'), KeyboardButton('📚 База знаний'))
        await bot.send_message(user_id,"Пожалуйста, подождите 60 секунд перед повторным обращением к оператору.",reply_markup=markup)
        return
    else:
        await bot.send_message(user_id, "*Ищем вам оператора\.\.\.* Подождите, пожалуйста\.", parse_mode="MarkdownV2")
        async with aiosqlite.connect('users.db') as db:
            cursor = await db.execute("INSERT INTO tickets (user_id, status, question) VALUES (?, ?, ?)",
                                      (user_id, "открыт", question_text))
            ticket_id = cursor.lastrowid
            await db.commit()

        ticket_link = f"https://t.me/antihypesupportbot?start=ticket_{ticket_id}"
        call_operator_btn = InlineKeyboardMarkup().add(InlineKeyboardButton("Взять тикет", url=ticket_link))

        sent_message = await bot.send_message(CHANNEL_NAME,f"Пользователь @{username} ({user_id}) создал тикет #{ticket_id}:\n\n{question_text}\n\nНажмите кнопку ниже, чтобы взять тикет.",reply_markup=call_operator_btn)
        async with aiosqlite.connect('users.db') as db:
            await db.execute("UPDATE tickets SET channel_message_id = ? WHERE id = ?", (sent_message.message_id, ticket_id))
            await db.commit()
        await update_user_last_action(user_id)



user_questions = dict()
@dp.message_handler(state=QuestionState.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    await state.finish()
    await state.update_data(question_text=message.text)
    user_id = message.from_user.id
    username = message.from_user.username
    question_text = message.text
    user_questions[user_id] = question_text
    inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton('🧑‍💻 Обратиться к оператору', callback_data='yes_call'))
    results = search_knowledge(message.text.lower())

    if results:
        answers = "\n\n".join(results)
        # Отправка результатов с ограничением для избежания слишком длинных сообщений
        await message.answer(f"Вот что бот по вашему вопросу:\n\n{answers}\n\nЕсли ответ на ваш вопрос не найден, воспользуйтесь кнопкой ниже для вызова оператора.",reply_markup=inline_kb)
    else:
        await message.answer("🤕 Упс, не можем найти вашу проблему\. Возможно, *она есть в нашей базе знаний\.* Нажмите Обратиться к оператору, если ее там действительно нет\.",reply_markup=inline_kb,parse_mode="MarkdownV2")
        await state.finish()

@dp.message_handler(lambda message: message.text.lower() == "оператор" or message.text.lower() == "обратиться к оператору" or message.text.lower() == "живой человек")
async def handle_operator_request(message: types.Message):

    await message.answer("*Ищем вам оператора\.\.\.* Подождите, пожалуйста\.", parse_mode="MarkdownV2")
    async with aiosqlite.connect('users.db') as db:
        cursor = await db.execute("INSERT INTO tickets (user_id, status, question) VALUES (?, ?, ?)",
                                  (message.from_user.id, "открыт", message.text))
        ticket_id = cursor.lastrowid
        await db.commit()

    ticket_link = f"https://t.me/antihypesupportbot?start=ticket_{ticket_id}"
    call_operator_btn = InlineKeyboardMarkup().add(InlineKeyboardButton("Взять тикет", url=ticket_link))

    sent_message = await bot.send_message(CHANNEL_NAME,
                                          f"Пользователь @{message.from_user.username} ({message.from_user.id}) создал тикет #{ticket_id}:\n\n{message.text}\n\nНажмите кнопку ниже, чтобы взять тикет.",
                                          reply_markup=call_operator_btn)

    async with aiosqlite.connect('users.db') as db:
        await db.execute("UPDATE tickets SET channel_message_id = ? WHERE id = ?", (sent_message.message_id, ticket_id))
        await db.commit()



@dp.callback_query_handler(lambda c: c.data and c.data.startswith('take_ticket'))
async def handle_ticket_take(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    if user_id in OPERATORS:
        async with aiosqlite.connect('users.db') as db:
            cursor = await db.execute("SELECT id FROM tickets WHERE status = 'открыт' ORDER BY id DESC LIMIT 1")
            ticket = await cursor.fetchone()

            if ticket:
                ticket_id = ticket[0]
                await db.execute("UPDATE tickets SET operator_id = ?, status = 'в обработке' WHERE id = ?",
                                 (user_id, ticket_id))
                await db.commit()

                await bot.answer_callback_query(callback_query.id, f"Вы взяли тикет #{ticket_id}.")

                await bot.edit_message_text(chat_id=CHANNEL_NAME, message_id=callback_query.message.message_id,
                                            text=f"Тикет #{ticket_id} взят оператором.",
                                            reply_markup=None)
            else:
                await bot.answer_callback_query(callback_query.id, "Свободных тикетов нет.", show_alert=True)
    else:
        await bot.answer_callback_query(callback_query.id, "Вы не являетесь оператором.", show_alert=True)


@dp.message_handler(Text(equals='Завершить диалог', ignore_case=True), state='*')
async def cmd_stop(message: Message):
    operator_id = message.from_user.id
    if str(operator_id) in OPERATORS:
        async with aiosqlite.connect('users.db') as db:
            cursor = await db.execute("""
                SELECT id, user_id, channel_message_id FROM tickets
                WHERE operator_id = ? AND status = 'в обработке'
            """, (operator_id,))
            ticket_info = await cursor.fetchone()

            if ticket_info:
                ticket_id, user_id, channel_message_id = ticket_info

                await db.execute("UPDATE tickets SET status = 'закрыт' WHERE id = ?", (ticket_id,))
                await db.commit()

                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(KeyboardButton('❓ Задать вопрос'), KeyboardButton('📚 База знаний'))
                await bot.send_message(user_id, "*Оператор завершил этот диалог\.* Если у вас есть дополнительные вопросы, пожалуйста, обратитесь снова\.",reply_markup=markup, parse_mode="MarkdownV2")
                if channel_message_id:
                    await bot.edit_message_text(chat_id=CHANNEL_NAME, message_id=channel_message_id,
                                                text=f"Оператор закрыл тикет #{ticket_id}")
                await message.reply("Вы успешно завершили диалог.")
            else:
                await message.reply("У вас нет активных диалогов.")
    else:
        await message.reply("Вы не являетесь оператором.")


@dp.message_handler(lambda message: message.chat.type == 'private')
async def forward_to_operator(message: types.Message):
    user_id = message.from_user.id

    async with aiosqlite.connect('users.db') as db:
        cursor = await db.execute(
            "SELECT operator_id FROM tickets WHERE user_id = ? AND status = 'в обработке' LIMIT 1", (user_id,))
        operator_info = await cursor.fetchone()

        if operator_info:
            operator_id = operator_info[0]
            await bot.send_message(operator_id, f"Пользователь: {message.text}")
        else:
            await message.reply(
                "В настоящий момент ни один оператор не связан с вашим вопросом\. Пожалуйста, подождите ответа или нажмите кнопку *❓ Задать вопрос*, если вы этого еще не сделали", parse_mode="MarkdownV2")

async def update_user_last_action(user_id: int):
    async with aiosqlite.connect('users.db') as db:
        await db.execute("UPDATE users SET last_action = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        await db.commit()

async def check_user_timeout(user_id: int) -> bool:
    async with aiosqlite.connect('users.db') as db:
        cursor = await db.execute("SELECT last_action FROM users WHERE id = ?", (user_id,))
        last_action_row = await cursor.fetchone()
        if last_action_row is None:
            return True
        last_action = last_action_row[0]
        if last_action:
            last_action_time = datetime.strptime(last_action, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            current_time = datetime.now(timezone.utc)
            if (current_time - last_action_time).total_seconds() < 60:
                return False
        return True

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup(dp))
    executor.start_polling(dp, skip_updates=True)
