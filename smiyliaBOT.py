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

# --- 4. обработка созданий карточек
# Вспомогательная функция для подменю (чтобы не дублировать разметку)
def show_submenu(call, text, buttons):
    markup = types.InlineKeyboardMarkup()
    for btn_text, btn_data in buttons:
        markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=btn_data))
    markup.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

def render_product_card(call, item_id, next_cb=None, prev_cb=None, back_cb="back_to_main"):
    """Универсальная функция для отрисовки любой карточки товара"""
    item = get_item_by_id(item_id)
    
    if not item:
        bot.answer_callback_query(call.id, "❌ Товар не найден в базе", show_alert=True)
        return

    # 1. Сборка кнопок
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"add_{item_id}"))
    
    nav_row = []
    if prev_cb: nav_row.append(types.InlineKeyboardButton(text="⬅️ Предыдущий", callback_data=prev_cb))
    if next_cb: nav_row.append(types.InlineKeyboardButton(text="Следующий ➡️", callback_data=next_cb))
    if nav_row: markup.add(*nav_row)
    
    markup.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb))

    caption = f"<b>{item['name']}</b>\n\n{item['desc']}\n\n💰 <b>Цена: {item['price']} ₽</b>"

    # 2. Логика отображения (фото или альбом)
    try:
        if len(item['photos']) > 1:
            # Если альбом — всегда удаляем старое и шлем заново
            bot.delete_message(call.message.chat.id, call.message.message_id)
            media_group = [types.InputMediaPhoto(url, caption=caption if i == 0 else '', parse_mode='HTML') for i, url in enumerate(item['photos'])]
            bot.send_media_group(call.message.chat.id, media_group)
            bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=markup)
        else:
            # Если одно фото — пытаемся редактировать для плавности
            photo_url = item['photos'][0] if item['photos'] else "https://via.placeholder.com/500"
            if call.message.content_type == 'photo':
                bot.edit_message_media(types.InputMediaPhoto(photo_url, caption=caption, parse_mode='HTML'), 
                                       call.message.chat.id, call.message.message_id, reply_markup=markup)
            else:
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_photo(call.message.chat.id, photo_url, caption=caption, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        print(f"Ошибка рендера: {e}")
        bot.send_message(call.message.chat.id, f"Карточка {item_id} временно недоступна.")

# --- 4. ХЕНДЛЕРЫ Блок объявления начальных кнопок и при использовании /start ---
@bot.message_handler(commands=['start'])
def start(message):
    # Регистрируем пользователя в таблице 
    try:
        register_user(message)
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

@bot.callback_query_handler(func=lambda call: True)

def callback_worker(call):
    print(f"--- Нажата кнопка: {call.data} ---") # Твоя важная отладка
    
    # --- УРОВЕНЬ 1: ГЛАВНЫЕ КАТЕГОРИИ ---
    if call.data == "balloons":
        show_submenu(call, "Раздел 🎈 Шары. Выберите категорию:", [
            ("💐 Букеты", "sub_bouquets"), 
            ("📸 Фотозоны", "sub_zones")
        ])
        
    elif call.data == "big_toys":
        show_submenu(call, "Раздел 🧸 Ростовые Игрушки. Выберите категорию:", [
            ("🧸 Мишки", "bears_teddy"), 
            ("🚀 АэроИгрушки", "sub_aero")
        ])

    # --- УРОВЕНЬ 2: КОНКРЕТНЫЕ ТОВАРЫ И КАРТОЧКИ ---
    
    # БУКЕТЫ (Оставляем твой текстовый вариант, как был)
    elif call.data == "sub_bouquets":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="⬅️ Назад к шарам", callback_data="balloons"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text="💐 <b>Наши букеты:</b>\n\n— Ромашки (7 шт): 1400₽\n— Ассорти: 2500₽\n\nДля заказа просто добавьте их в корзину!", 
                             parse_mode='HTML', reply_markup=markup)

    # ФОТОЗОНЫ (Используем супер-функцию)
    elif call.data == "sub_zones":
        render_product_card(call, "zone_1", next_cb="zone_2", back_cb="balloons")
    elif call.data == "zone_2":
        render_product_card(call, "zone_2", prev_cb="sub_zones", back_cb="balloons")

    # МИШКИ (Используем супер-функцию)
    elif call.data == "bears_teddy":
        render_product_card(call, "bears_teddy", next_cb="bears_brown_white", back_cb="big_toys")
    elif call.data == "bears_brown_white":
        render_product_card(call, "bears_brown_white", prev_cb="bears_teddy", back_cb="big_toys")

    # --- СЛУЖЕБНЫЕ КНОПКИ ---

    # ДОБАВЛЕНИЕ В КОРЗИНУ
    elif "add_" in call.data:
        item_id = call.data.replace("add_", "")
        user_id = call.from_user.id
        if user_id not in user_carts:
            user_carts[user_id] = []
        user_carts[user_id].append(item_id)
        bot.answer_callback_query(call.id, text=f"✅ Добавлено в корзину!")

        # Очистка корзины
    elif call.data == "clear_cart":
        user_id = call.from_user.id
        user_carts[user_id] = []
        bot.answer_callback_query(call.id, "Корзина очищена 🗑️") 

    # НАЗАД В ГЛАВНОЕ МЕНЮ
    # ВЕРНУТЬСЯ В НАЧАЛО
    elif call.data == "back_to_main":
        # Создаем те же кнопки, что были при команде /start
        markup = types.InlineKeyboardMarkup()
        btn_balloons = types.InlineKeyboardButton(text="🎈 Шары", callback_data="balloons")
        btn_toys = types.InlineKeyboardButton(text="🧸 Ростовые Игрушки", callback_data="big_toys")
        markup.add(btn_balloons, btn_toys)

        if call.message.content_type == 'photo':
            # Если мы были в карточке с фото — удаляем её и шлем новое меню текстом
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Что вас интересует?", reply_markup=markup)
        else:
            # Если мы были в текстовом подменю — просто редактируем текст
            bot.edit_message_text(chat_id=call.message.chat.id, 
                                 message_id=call.message.message_id, 
                                 text="Что вас интересует?", 
                                 reply_markup=markup)

    # ОФОРМЛЕНИЕ ЗАКАЗА
    elif call.data == "checkout":
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add(types.KeyboardButton(text="📱 Отправить номер", request_contact=True),
                   types.KeyboardButton(text="❌ Продолжить без номера"))
        msg = bot.send_message(call.message.chat.id, "Оставьте номер для связи:", reply_markup=markup)
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