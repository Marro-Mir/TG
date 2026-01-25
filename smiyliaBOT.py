import telebot
import config
from telebot import types # Импортируем типы для создания кнопок
import gspread
from oauth2client.service_account import ServiceAccountCredentials

user_carts = {} # Здесь будем хранить товары: {user_id: [список товаров]}   # хранение корзины пользователя
user_phones = {}

# Настройка доступа гугла
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Открываем таблицу и конкретный лист
sheet = client.open("Smiylia_bot").worksheet("photo_catalog") 
# лист юзеров
users_sheet = client.open("Smiylia_bot").worksheet("users")
# лист заказов
orders_sheet = client.open("Smiylia_bot").worksheet("orders")

# ОБЯЗАТЕЛЬНО: Создаем переменную списка кэша ДО того, как она понадобится функциям. Для заиси данных из гугла в телегу, чтобы не тупило.
data_cache = sheet.get_all_records()

# При запуске бота скачать всё
all_items = sheet.get_all_records() # Скачивает всю таблицу в список словарей, чтобы не тупило

 # --- 1. Твой вспомогательный инструмент (ставим ПЕРЕД обработчиком кнопок. Перед тем где открываются карточки) ---
def get_item_by_id(item_id):
    # Ищем товар в сохраненном списке
    for row in data_cache:

        # ПРИНТ 1(проверка): Посмотрим, какие ключи видит бот в таблице
        # (выполнится один раз для первой строки)
        if row == data_cache[0]:
            print(f"Ключи в таблице: {list(row.keys())}")
            
        # ПРИНТ 2(проверка): С чем бот сравнивает нажатую кнопку
        print(f"Сравниваю: таблицу '{row.get('ID товара')}' и кнопку '{item_id}'")

        # Проверяем столбец 'ID' (название должно совпадать с заголовком в таблице!)
        if str(row.get('ID товара')) == item_id.strip():
            # Превращаем ссылки в список (для альбомов)
            photos = [p.strip() for p in str(row.get('Ссылка на фото', '')).split(',')]
            
            return {
                "name": row.get('Название'),
                "photos": photos,
                "desc": row.get('Описание'),
                "price": row.get('Цена')
            }
    return None

# --- 2. Основной связывающий блок. Через ТГ айдишники и токены ---
bot = telebot.TeleBot(config.TOKEN)
# Присваиваем значение из конфига локальной переменной
ADMIN_ID = config.ADMIN_ID # Мой ID

# --- 3. регистрация юзера
from datetime import datetime

def register_user(message):
    user_id = str(message.from_user.id)
    # Читаем ID из первой колонки (User ID)
    # Предполагаем, что users_sheet уже определен в начале файла
    existing_ids = users_sheet.col_values(1) 
    
    if user_id not in existing_ids:
        # Собираем данные по твоим колонкам: 
        # User ID, Имя, Username, Телефон, Last Visit, Дата заказа, Дата выезда
        new_row = [
            user_id,                                      # User ID
            message.from_user.first_name,                 # Имя
            f"@{message.from_user.username}" if message.from_user.username else "нет", 
            "Не указан",                                  # Телефон (заполним при заказе)
            datetime.now().strftime("%d.%m.%Y %H:%M"),    # Last Visit
            "",                                           # Дата заказа
            ""                                            # Дата выезда
        ]
        users_sheet.append_row(new_row)
        print(f"✅ Новый пользователь записан: {message.from_user.first_name}")
    else:
        # Если юзер уже есть, можно просто обновить ему время последнего визита
        # Находим строку юзера (индекс начинается с 1)
        row_index = existing_ids.index(user_id) + 1
        users_sheet.update_cell(row_index, 5, datetime.now().strftime("%d.%m.%Y %H:%M"))


# --- 4. ХЕНДЛЕРЫ Блок объявления начальных кнопок и при использовании /start ---
@bot.message_handler(commands=['start'])
def start(message):
    # Регистрируем пользователя в таблице 
    try:
        с
    except Exception as e:
        print(f"Ошибка при регистрации юзера: {e}")

    # Создаем каркас для кнопок
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # Создаем сами кнопки
    btn1 = types.KeyboardButton("🎈 Каталог")
    btn2 = types.KeyboardButton("💰 Прайс-лист")
    btn3 = types.KeyboardButton("📞 Связаться с мастером")
    btn4 = types.KeyboardButton("📸 Наши соц сети")
    btn_cart = types.KeyboardButton("🛒 Корзина")
    
    # Добавляем кнопки в каркас
    markup.add(btn1, btn2, btn3, btn4, btn_cart)
    
    # Отправляем сообщение с кнопками
    bot.send_message(message.chat.id, 
                     f"Привет, {message.from_user.first_name}! \nЯ SmileTime - помощник студии аэродизайна. Чем могу помочь? \n\nНавигация в боте: \n* нажмите 4 квадратика справа в строке сообщений 㗊 для выбора товаров и услуг \n* нажмите на 3 полосочки ☰ для помощи \n* или просто напишите сообщение в этот чат и мастер ответит вам =) \n\n Ждём ваших заказов 🤗" , 
                     reply_markup=markup)

# --- 5. ХЕНДЛЕР Обработчик команды /help ---
@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "<b>🆘 Помощь и контакты</b>\n\n"
        "1. Используйте кнопки внизу экрана для навигации.\n"
        "2. Если кнопки пропали, нажмите на значок квадратиков в поле ввода сообщения 㗊.\n"
        "3. Вы можете написать свой вопрос прямо сюда, и мастер ответит вам.\n\n"
        "📞 Прямая связь: +7 (XXX) XXX-XX-XX\n"
        "💬 Личка мастера: @твой_ник"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

# --- 6. ХЕНДЛЕР Обработчик команды /refresh только для админа. Обновление данных из таблицы ---
@bot.message_handler(commands=['refresh'])
def refresh_data(message):
    # Проверяем, что пишет именно админ
    if message.from_user.id == config.ADMIN_ID:
        try:
            global data_cache
            # Отправляем сообщение, чтобы ты видела — процесс пошел
            msg = bot.send_message(message.chat.id, "🔄 Обновляю данные из таблицы...")
            
            # Заново скачиваем всё из Google Sheets
            data_cache = sheet.get_all_records()
            
            # Редактируем старое сообщение, когда всё готово
            bot.edit_message_text("✅ Данные успешно обновлены! Теперь бот использует актуальную информацию из таблицы.", 
                                  message.chat.id, msg.message_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка при обновлении: {e}")
    else:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")

# --- 7. ХЕНДЛЕР Обработчик команды /admin_orders только для админа. Поиск заказов по дате.
@bot.message_handler(commands=['admin_orders'])
def start_order_search(message):
    msg = bot.send_message(message.chat.id, "🔍 Введите дату для поиска заказов (например, 25.01.2026):")
    bot.register_next_step_handler(msg, process_date_search)

def process_date_search(message):
    search_date = message.text.strip()
    # Берем данные из листа orders
    data = orders_sheet.get_all_records()
    
    results = []
    for row in data:
        # Ищем по колонке "Дата заказа"
        if str(row.get('Дата заказа')) == search_date:
            results.append(f"🎈 {row.get('Имя')}: {row.get('Товары')} ({row.get('Время')})")

    if results:
        report = f"📅 Список заказов на {search_date}:\n\n" + "\n".join(results)
        bot.send_message(message.chat.id, report)
    else:
        bot.send_message(message.chat.id, f"На {search_date} заказов в таблице не найдено.")

# --- 6. Обработчик команды "contact - Оформить заказ". Отправка Админу ---
# --- ОБРАБОТКА КОНТАКТА И ПЕРЕХОД К ДАТЕ ---
@bot.message_handler(content_types=['contact'])
def global_phone_handler(message):
    user_id = message.from_user.id
    
    # Если юзер нажал на кнопку "Отправить номер"
    if message.contact:
        phone = message.contact.phone_number
        user_phones[user_id] = phone
        # Вызываем твой старый обработчик, чтобы он записал всё в таблицу Users
        contact_handler(message) 
        
    # Если юзер нажал на кнопку "❌ Продолжить без номера"
    elif message.text == "❌ Продолжить без номера":
        skip_phone(message)
        
        
    # Если юзер просто что-то написал текстом (например, сам ввел номер)
    else:
        user_phones[user_id] = message.text
        ask_order_date(message)

def contact_handler(message):
    phone = message.contact.phone_number
    # Сохраняем телефон сразу в таблицу юзеров (по желанию)
    user_id = str(message.from_user.id)
    phone = message.contact.phone_number
    #Сохраняем в память для листа Orders ---
    user_phones[user_id] = phone

    #Сохраняем в таблицу Users
    try:
        user_id_str = str(user_id)
        existing_ids = users_sheet.col_values(1)
        if user_id_str in existing_ids:
            row_index = existing_ids.index(user_id_str) + 1
            users_sheet.update_cell(row_index, 4, phone) # 4 колонка - Телефон
    except Exception as e:
        print(f"Ошибка при записи телефона в таблицу: {e}")
    
    # Переходим к следующему шагу
    ask_order_date(message)

# Если нажали "Продолжить без номера" (обработай это в текстовом хендлере) 
# это страховка, нужна для ситуации: пользователь нажал «Оформить», увидел кнопки, но отвлекся. Позже он заходит в чат, видит кнопку «❌ Продолжить без номера» в клавиатуре и нажимает её.
@bot.message_handler(func=lambda message: message.text == "❌ Продолжить без номера")
def skip_phone(message):
    user_id = message.from_user.id
    # Записываем, что номера нет, чтобы в таблицу Orders ушло "Не указан"
    user_phones[user_id] = "Не указан" 
    # Переходим к следующему шагу
    ask_order_date(message)

# --- ЦЕПОЧКА ВОПРОСОВ ---

def ask_order_date(message):
    msg = bot.send_message(message.chat.id, "📅 Введите дату заказа (в формате ДД.ММ.ГГГГ, например: 25.01.2026):", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, ask_order_time)

def ask_order_time(message):
    order_date = message.text.strip()
    msg = bot.send_message(message.chat.id, "⏰ Введите удобное время (например: 14:00):")
    bot.register_next_step_handler(msg, ask_order_address, order_date)

def ask_order_address(message, order_date):
    order_time = message.text.strip()
    msg = bot.send_message(message.chat.id, "🏠 Введите адрес доставки или напишите 'Самовывоз':")
    bot.register_next_step_handler(msg, ask_order_info, order_date, order_time)

def ask_order_info(message, order_date, order_time):
    address = message.text.strip()
    msg = bot.send_message(message.chat.id, "🎂 Укажите пол и возраст именинника (или пропустите, написав '-'):")
    bot.register_next_step_handler(msg, finalize_order, order_date, order_time, address)

def finalize_order(message, user_date, user_time, address):
    extra_info = message.text.strip()
    user_id = message.from_user.id
    
    # Собираем список товаров из корзины в одну строку
    cart_items = ", ".join(user_carts.get(user_id, ["Пусто"]))
    
    # Готовим данные для новой строки в листе orders
    # Порядок: ID заказа, Дата заказа, Имя, Username, Телефон, Товары, Время, Адрес, Именинник
    new_order_row = [
        #str(datetime.now().timestamp()),             # ID заказа (уникальный номер) в Unix Timestamp (количество секунд) формате
        datetime.now().strftime("%d.%m.%Y %H:%M:%S"), # ID заказа
        user_date,                                    # Дата заказа (которую ввел юзер)
        message.from_user.first_name,                 # Имя
        f"@{message.from_user.username}",             # Username
        user_phones.get(user_id, "Спросить в ЛС"),    # Ищем в памяти, если нет — пишем текст
        cart_items,                                   # Товары из корзины
        user_time,                                    # Время
        address,                                      # Адрес
        extra_info                                    # Инфо об имениннике
    ]
    
    # ДОБАВЛЯЕМ НОВУЮ СТРОКУ В ТАБЛИЦУ
    orders_sheet.append_row(new_order_row)
    
    # Уведомляем клиента
    bot.send_message(message.chat.id, "✨ Спасибо! Ваш заказ записан. Мастер скоро свяжется с вами.")
    
    # Уведомляем тебя (Мастера)
    admin_id = config.ADMIN_ID  # СВОЙ ID
    admin_msg = (f"🔔 НОВЫЙ ЗАКАЗ в таблице!\n"
                 f"📅 Дата: {user_date}\n"
                 f"🛍 Товары: {cart_items}\n"
                 f"📍 Адрес: {address}\n"
                 f"📜 Инфо: {extra_info}")
    bot.send_message(admin_id, admin_msg)

    # 2. Шлем "ЗАГЛУШКУ", которую админ сможет "Реплайнуть"
    # Мы используем forward_message, чтобы админ видел, кому отвечать
    bot.send_message(ADMIN_ID, "--- Ниже сообщение для ответа клиенту ---")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)

    # Очищаем корзину после заказа
    user_carts[user_id] = []

'''
@bot.message_handler(content_types=['contact'])
def contact(message):
    user_id = message.from_user.id
    # Проверяем, есть ли что-то в корзине
    items = "\n— ".join(user_carts.get(user_id, ["Товары не определены"]))
    phone = message.contact.phone_number

    # 1. Сообщение админу при отправке С НОМЕРОМ
    admin_text = (
        f"🔔 <b>НОВЫЙ ЗАКАЗ С НОМЕРОМ!</b>\n\n"
        f"👤 Клиент: <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>\n"
        f"📞 Номер: <code>{phone}</code>\n"
        f"📦 Товары:\n— {items}"
    )
    bot.send_message(ADMIN_ID, admin_text, parse_mode='HTML')

    # 2. Очищаем корзину и благодарим клиента
    user_carts[user_id] = []
    bot.send_message(message.chat.id, "✅ Заявка отправлена! Мастер скоро свяжется с вами.", 
                     reply_markup=types.ReplyKeyboardRemove())

# Обработка если нажали "❌ Продолжить без номера"
@bot.message_handler(func=lambda message: message.text == "❌ Продолжить без номера")
def skip_phone(message):
    user_id = message.from_user.id
    items = "\n— ".join(user_carts.get(user_id, ["Товары не определены"]))
    
    # 1. Сначала шлем админу ПОЛНУЮ информацию о заказе (красиво)
    order_info = (
        f"🔔 <b>ЗАКАЗ БЕЗ НОМЕРА!</b>\n\n"
        f"👤 Клиент: @{message.from_user.username if message.from_user.username else message.from_user.first_name}\n"
        f"📦 Товары:\n— {items}"
    )
    bot.send_message(ADMIN_ID, order_info, parse_mode='HTML')
    
    # 2. Шлем "ЗАГЛУШКУ", которую админ сможет "Реплайнуть"
    # Мы используем forward_message, чтобы админ видел, кому отвечать
    bot.send_message(ADMIN_ID, "--- Ниже сообщение для ответа клиенту ---")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    
    # 3. Очищаем корзину и отвечаем клиенту
    user_carts[user_id] = []
    bot.send_message(message.chat.id, "✅ Заявка отправлена! Мастер напишет вам в Telegram.", 
                     reply_markup=types.ReplyKeyboardRemove())
'''

# --- 7. Обработка нажатий на кнопки меню ---
@bot.message_handler(content_types=['text'])
def get_text_messages(message):
# Список кнопок, которые НЕ надо пересылать админу
    menu_buttons = ["🎈 Каталог", "💰 Прайс-лист", "📞 Связаться с мастером", "📸 Наши соц сети", "🛒 Корзина", "❌ Пропустить"]

    if message.text == "🎈 Каталог":
        markup = types.InlineKeyboardMarkup()
        # Кнопка с "коллбэком" (внутренняя команда для бота)
        btn_balloons = types.InlineKeyboardButton(text="🎈 Шары", callback_data="balloons")
        btn_toys = types.InlineKeyboardButton(text="🧸 Ростовые Игрушки", callback_data="big_toys")
        markup.add(btn_balloons, btn_toys)
        
        bot.send_message(message.chat.id, "Что вас интересует?", reply_markup=markup)
        return
    if message.text == "📸 Наши соц сети":
        # Создаем инлайн-клавиатуру (кнопки под сообщением)
        markup = types.InlineKeyboardMarkup()
        # Кнопка-ссылка (например, на соц сети или сайт)
        #btn_vk = types.InlineKeyboardButton(text="📸 Наш ВК", url="https://vk.ru/smiletime40")
        bot.send_message(message.chat.id, "Загляните в наш ВК: https://vk.ru/smiletime40", reply_markup=markup)
        
        # Добавляем кнопки (row - значит каждая в новой строке, или просто .add)
        #markup.add(btn_vk)
        return  # ВАЖНО: останавливаем функцию, чтобы не сработала пересылка!

    if message.text == "💰 Прайс-лист":
        bot.send_message(message.chat.id, "Минимальный заказ от 2000р. \nГелиевые шары от 150р/шт.")
        return # Останавливаем
    if message.text == "📞 Связаться с мастером":
        bot.send_message(message.chat.id, "Напишите нам в Telegram: @username")
        return # Останавливаем
    # Кнопки пока нет, оставила на будущее. Например для отзывов использовать
    if message.text == "❌ Пропустить":
        bot.send_message(message.chat.id, "Хорошо! Если возникнут вопросы, просто напишите их сюда в чат.", reply_markup=types.ReplyKeyboardRemove())

    if message.text == "🛒 Корзина":
        user_id = message.from_user.id
        if user_id not in user_carts or not user_carts[user_id]:
            bot.send_message(message.chat.id, "Ваша корзина пока пуста 🤷‍♀️")
        else:
            cart_items = "\n— ".join(user_carts[user_id])
            markup = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")
            btn_clear = types.InlineKeyboardButton(text="🗑️ Очистить", callback_data="clear_cart")
            markup.add(btn_confirm, btn_clear)
            
            bot.send_message(message.chat.id, f"<b>Ваши товары:</b>\n\n— {cart_items}", 
                             parse_mode='HTML', reply_markup=markup)

# --- 8. ЛОГИКА ПЕРЕСЫЛКИ СООБЩЕНИЙ ОТ/К МАСТЕРА (если это не кнопка). ---
    
    # Если пишет АДМИН в ответ на пересланное сообщение
    if message.chat.id == ADMIN_ID and message.reply_to_message:
        try:
            # Находим ID клиента, которому нужно ответить
            original_user_id = message.reply_to_message.forward_from.id
            bot.send_message(original_user_id, f"Ответ от мастера: {message.text}")
            bot.send_message(ADMIN_ID, "✅ Ответ отправлен!")
        except Exception as e:
            bot.send_message(ADMIN_ID, "Ошибка: Не удалось ответить. Возможно, у клиента закрыт профиль.")

    # Если пишет КЛИЕНТ (и это НЕ кнопка меню)
    elif message.chat.id != ADMIN_ID and message.text not in menu_buttons:
        bot.reply_to(message, "Ваше сообщение отправлено! Скоро вам ответят. 😊")
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        
# --- 9. Основной обработчик кнопок ---
        # Обработка нажатий на инлайн-кнопки (callback)
@bot.callback_query_handler(func=lambda call: True)
def callback_worker(call):
    print(f"--- Нажата кнопка: {call.data} ---")
    item = None

# --- УРОВЕНЬ 1: КАТАЛОГ -> ШАРЫ ИЛИ ИГРУШКИ ---
    if call.data == "balloons": #Шары
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton(text="💐 Букеты", callback_data="sub_bouquets")
        btn2 = types.InlineKeyboardButton(text="📸 Фотозоны", callback_data="sub_zones")
        btn_back = types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
        markup.add(btn1, btn2)
        markup.add(btn_back)
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text="Раздел 🎈 Шары. Выберите категорию:", reply_markup=markup)
        return

    elif call.data == "big_toys": # Ростовые Игрушки
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton(text="🧸 Мишки", callback_data="bears_teddy")
        btn2 = types.InlineKeyboardButton(text="🚀 АэроИгрушки", callback_data="sub_aero")
        btn_back = types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
        markup.add(btn1, btn2)
        markup.add(btn_back)
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text="Раздел 🧸 Игрушки. Выберите категорию:", reply_markup=markup)
        return

# --- УРОВЕНЬ 2: КОНКРЕТНЫЕ ТОВАРЫ (Пример для Букетов) ---
# --- ЛОГИКА ДЛЯ БУКЕТОВ ---
    elif call.data == "sub_bouquets":
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton(text="⬅️ Назад к шарам", callback_data="balloons")
        markup.add(btn_back)
        
        # Сюда можно отправить фото или просто текст с ценами
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text="💐 <b>Наши букеты:</b>\n\n— Ромашки (7 шт): 1400₽\n— Ассорти: 2500₽\n\nДля заказа просто напишите нам!", 
                             parse_mode='HTML', reply_markup=markup)
                             # --- ЛОГИКА ДЛЯ ФОТОЗОН ---
    
# --- ЛОГИКА ДЛЯ ФОТОЗОН ---
    if call.data == "sub_zones":
        # Карточка №1 для Фотозон
        markup = types.InlineKeyboardMarkup()
        btn_next = types.InlineKeyboardButton(text="Следующая ➡️", callback_data="zone_2")
        # Вместо order_bears_teddy пишем add_bears_teddy
        btn_add = types.InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data="add_zone_1")
        btn_back = types.InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")
        markup.add(btn_add)
        markup.add(btn_next)
        markup.add(btn_back)

        # ПРОВЕРКА ДЛЯ ПЛАВНОСТИ:
        if call.message.content_type == 'photo':
            # Если мы УЖЕ смотрим фото (нажали "Назад" со второй фотозоны)
            media = types.InputMediaPhoto("https://drive.google.com/uc?export=download&id=1ZIIh5y1Vh9Tr-6jLrOAFSI1c5wvazqua", 
                                        caption="<b>📸 Фотозона 'Silver Star'</b>\n\n💰 <b>Цена: 8 500 ₽</b>", 
                                        parse_mode='HTML')
            bot.edit_message_media(media, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            # Если мы зашли сюда из ТЕКСТОВОГО меню
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_photo(call.message.chat.id, "https://drive.google.com/uc?export=download&id=1ZIIh5y1Vh9Tr-6jLrOAFSI1c5wvazqua", 
                           caption="<b>📸 Фотозона 'Silver Star'</b>\n\n💰 <b>Цена: 8 500 ₽</b>", 
                           parse_mode='HTML', reply_markup=markup)

    elif call.data == "zone_2":
        # Карточка №2 для Фотозон
        markup = types.InlineKeyboardMarkup()
        btn_prev = types.InlineKeyboardButton(text="⬅️ Предыдущая", callback_data="sub_zones")
        btn_add = types.InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data="add_zone_2")
        btn_back = types.InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")
        markup.add(btn_add)
        markup.add(btn_prev)
        markup.add(btn_back)

        # Меняем фото и текст на вторую карточку
        media = types.InputMediaPhoto("https://drive.google.com/uc?export=download&id=14m2lxriJN1pPqA4xgtlKBp3CVNkOTy8Q", 
                                    caption="<b>📸 Фотозона 'Organic'</b>\n\nРазмер: 3м ширина\nРазнокалиберная гирлянда.\n\n💰 <b>Цена: 12 000 ₽</b>", 
                                    parse_mode='HTML')
        bot.edit_message_media(media, call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- ЛОГИКА ДЛЯ МИШЕК ---
    # Карточка №1 для Мишек
    elif call.data == "bears_teddy":
        item = get_item_by_id("bears_teddy")

        print(f"Результат поиска item: {item}") # Посмотрим, что вернулось сюда

        # ПРОВЕРКА: если item равен None (ничего не нашли)
        if item is None:
            print("⚠ Бот остановился: item пустой")
            bot.answer_callback_query(call.id, "❌ Ошибка: ID 'bears_teddy' не найден в таблице! Пожалуйста, напишите мастеру 'Привет!' в этом чате или в Telegram @smiylia_studio", show_alert=True)
            return  # Останавливаем функцию здесь, чтобы не было ошибок дальше

        if item:
            # Кнопки для карточки №1 для Мишек
            markup = types.InlineKeyboardMarkup()
            btn_next = types.InlineKeyboardButton(text="Следующий ➡️", callback_data="bears_brown_white")
            btn_add = types.InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data="add_bears_teddy")
            btn_back = types.InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")
            markup.add(btn_add)
            markup.add(btn_next)
            markup.add(btn_back)

            caption = f"<b>{item['name']}</b>\n\n{item['desc']}\n\n💰 <b>Цена: от {item['price']} ₽</b>"

         # ПРОВЕРКА ДЛЯ ПЛАВНОСТИ:
        try:
            if len(item['photos']) == 1:
                print("🚀 Режим: Одно фото")
                # Пытаемся заменить старое сообщение на фото
                if call.message.content_type == 'photo':
                    media = types.InputMediaPhoto(item['photos'][0], caption=caption, parse_mode='HTML')
                    bot.edit_message_media(media, call.message.chat.id, call.message.message_id, reply_markup=markup)
                else:
                     # Если старое было текстом - удаляем и шлем новое
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                    bot.send_photo(call.message.chat.id, item['photos'][0], caption=caption, parse_mode='HTML', reply_markup=markup)
        
            elif len(item['photos']) > 1:
                print("🚀 Режим: Альбом")
                bot.delete_message(call.message.chat.id, call.message.message_id)
                media_group = []
                for i, url in enumerate(item['photos']):
                    media_group.append(types.InputMediaPhoto(url, caption=caption if i == 0 else '', parse_mode='HTML'))
            
                bot.send_media_group(call.message.chat.id, media_group)
                bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=markup)

        except Exception as e:
            print(f"❌ Ошибка при отправке: {e}")
           # Если всё сломалось, пробуем просто отправить текст, чтобы юзер не висел
            bot.send_message(call.message.chat.id, f"Ошибка загрузки фото, но вот описание:\n\n{caption}", reply_markup=markup)

    # Карточка №2 для Мишек
    elif call.data == "bears_brown_white": 
        item = get_item_by_id("bears_brown_white") 
        
        markup = types.InlineKeyboardMarkup()
        btn_prev = types.InlineKeyboardButton(text="⬅️ Предыдущий", callback_data="bears_teddy")
        btn_add = types.InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data="add_bears_brown_white")
        btn_back = types.InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")
        markup.add(btn_add)
        markup.add(btn_prev)
        markup.add(btn_back)

        caption = f"<b>{item['name']}</b>\n\n{item['desc']}\n\n💰 <b>Цена: от {item['price']} ₽</b>"

         # ПРОВЕРКА ДЛЯ ПЛАВНОСТИ:
        if call.message.content_type == 'photo':
            # ПРОВЕРКА: Одно фото или несколько?
            if len(item['photos']) == 1:
                # --- РЕЖИМ ОДНОГО ФОТО (Плавный) ---
                if call.message.content_type == 'photo':
                    media = types.InputMediaPhoto(item['photos'][0], caption=caption, parse_mode='HTML')
                    bot.edit_message_media(media, call.message.chat.id, call.message.message_id, reply_markup=markup)
                else:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                    bot.send_photo(call.message.chat.id, item['photos'][0], caption=caption, parse_mode='HTML', reply_markup=markup)
            
            else:
                # --- РЕЖИМ АЛЬБОМА ---
                bot.delete_message(call.message.chat.id, call.message.message_id)
                
                media_group = []
                for i, url in enumerate(item['photos']):
                    media_group.append(types.InputMediaPhoto(url, caption=caption if i == 0 else '', parse_mode='HTML'))
                
                bot.send_media_group(call.message.chat.id, media_group)
                # Кнопки шлем отдельным сообщением под альбом
                bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=markup)

# --- 10. КНОПКА НАЗАД В САМОЕ НАЧАЛО ---
    elif call.data == "back_to_main":
        markup = types.InlineKeyboardMarkup()
        btn_balloons = types.InlineKeyboardButton(text="🎈 Шары", callback_data="balloons")
        btn_toys = types.InlineKeyboardButton(text="🧸 Ростовые Игрушки", callback_data="big_toys")
        markup.add(btn_balloons, btn_toys)
        
        # Если было фото — удаляем его, чтобы вернуться к чистому тексту
        if call.message.content_type == 'photo':
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Что вас интересует?", reply_markup=markup)
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                 text="Что вас интересует?", reply_markup=markup)

# --- 11. Обработка добавления в корзину ---
    elif "add_" in call.data:
        user_phones = {} # Здесь будем временно хранить телефоны по user_id
        item_name = call.data.replace("add_", "")
        user_id = call.from_user.id
        
        if user_id not in user_carts:
            user_carts[user_id] = []
        
        user_carts[user_id].append(item_name)
        
        bot.answer_callback_query(call.id, text=f"✅ {item_name} добавлен в корзину!")

    # Очистка корзины
    elif call.data == "clear_cart":
        user_id = call.from_user.id
        user_carts[user_id] = []
        bot.answer_callback_query(call.id, "Корзина очищена 🗑️") 

# --- 12. ОБРАБОТКА ЗАКАЗОВ (Запрос контакта) ---
    elif call.data == "checkout":
        # Создаем кнопки для телефона
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        btn_phone = types.KeyboardButton(text="📱 Отправить номер", request_contact=True)
        btn_skip = types.KeyboardButton(text="❌ Продолжить без номера")
        markup.add(btn_phone, btn_skip)
        
        msg = bot.send_message(call.message.chat.id, 
                         "Чтобы мастер мог с вами связаться, отправьте номер телефона или нажмите 'Продолжить без номера'", 
                         reply_markup=markup)
        # Бот запоминает, что следующее сообщение (телефон или кнопка)
        # нужно отправить в функцию регистрации телефона
        bot.register_next_step_handler(msg, global_phone_handler) 
        bot.answer_callback_query(call.id)
        
        # Устанавливаем команды для обычных пользователей
bot.set_my_commands([
    types.BotCommand("start", "Запустить бота 🎈"),
    types.BotCommand("help", "Помощь и контакты 📞")
], scope=types.BotCommandScopeDefault())

# Устанавливаем спец-команды только для админа (подставь свой ID из конфига)
bot.set_my_commands([
    types.BotCommand("start", "Запустить бота 🎈"),
    types.BotCommand("refresh", "🔄 Обновить товары из таблиц"),
    types.BotCommand("admin_orders", "📅 Посмотреть заказы по дате")
], scope=types.BotCommandScopeChat(config.ADMIN_ID))

print("Бот запущен и ждет кнопок!")
# non_stop=True — бот будет пытаться переподключиться сам, использовать без infinity так -> bot.polling(non_stop=True) .
# skip_pending=True — бот проигнорирует те сообщения, что ему слали, пока он был «в обмороке» (чтобы он не спамил ответами сразу после включения).
bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True)