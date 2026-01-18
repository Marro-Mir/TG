import telebot
import config
from telebot import types # Импортируем типы для создания кнопок
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Настройка доступа
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Открываем таблицу и конкретный лист
sheet = client.open("Smiylia_bot").worksheet("photo_catalog") 

# ОБЯЗАТЕЛЬНО: Создаем переменную ДО того, как она понадобится функциям
data_cache = sheet.get_all_records()

# При запуске бота скачать всё
all_items = sheet.get_all_records() # Скачивает всю таблицу в список словарей

 # --- 1. Твой вспомогательный инструмент (ставим ПЕРЕД обработчиком кнопок. Перед тем где они открываются) ---
def get_item_by_id(item_id):
    # Ищем товар в сохраненном списке
    for row in data_cache:

# ПРИНТ 1: Посмотрим, какие ключи видит бот в таблице
        # (выполнится один раз для первой строки)
        if row == data_cache[0]:
            print(f"Ключи в таблице: {list(row.keys())}")
            
        # ПРИНТ 2: С чем бот сравнивает нажатую кнопку
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

user_carts = {} # Здесь будем хранить товары: {user_id: [список товаров]}   # хранение корзины пользователя
bot = telebot.TeleBot(config.TOKEN)
# Присваиваем значение из конфига локальной переменной
ADMIN_ID = config.ADMIN_ID # Мой ID

@bot.message_handler(commands=['start'])
def start(message):
    # Создаем каркас для кнопок
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # Создаем сами кнопки
    btn1 = types.KeyboardButton("🎈 Посмотреть каталог")
    btn2 = types.KeyboardButton("💰 Прайс-лист")
    btn3 = types.KeyboardButton("📞 Связаться с мастером")
    btn4 = types.KeyboardButton("📸 Наши соц сети")
    btn_cart = types.KeyboardButton("🛒 Корзина")
    
    # Добавляем кнопки в каркас
    markup.add(btn1, btn2, btn3, btn4, btn_cart)
    
    # Отправляем сообщение с кнопками
    bot.send_message(message.chat.id, 
                     f"Привет, {message.from_user.first_name}! \nЯ SmileTime - помощник студии аэродизайна. Чем могу помочь? \n\nДля навигации в боте нажмите: 4 квадратика справа в строке сообщений 㗊 для выбора товаров и услуг, нажмите на 3 полосочки ☰ для помощи. Или просто напишите сообщение в этот чат и мастер ответит вам =) \n\n Ждём ваших заказов 🤗" , 
                     reply_markup=markup)

# Обработчик команды /help
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

@bot.message_handler(content_types=['contact'])
def contact(message):
    user_id = message.from_user.id
    # Проверяем, есть ли что-то в корзине
    items = "\n— ".join(user_carts.get(user_id, ["Товары не определены"]))
    phone = message.contact.phone_number

    # Сообщение админу
    admin_text = (
        f"🔔 <b>НОВЫЙ ЗАКАЗ С НОМЕРОМ!</b>\n\n"
        f"👤 Клиент: {message.from_user.first_name}\n"
        f"📞 Номер: <code>{phone}</code>\n"
        f"📦 Товары:\n— {items}"
    )
    bot.send_message(ADMIN_ID, admin_text, parse_mode='HTML')

    # Очищаем корзину и благодарим клиента
    user_carts[user_id] = []
    bot.send_message(message.chat.id, "✅ Заявка отправлена! Мастер скоро вам позвонит.", 
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

# Обработка нажатий на кнопки
@bot.message_handler(content_types=['text'])
def get_text_messages(message):
# Список кнопок, которые НЕ надо пересылать админу
    menu_buttons = ["🎈 Посмотреть каталог", "💰 Прайс-лист", "📞 Связаться с мастером", "📸 Наши соц сети", "🛒 Корзина", "❌ Пропустить"]

    if message.text == "🎈 Посмотреть каталог":
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
        
        # bot.send_message(message.chat.id, "Выберите категорию декора:", reply_markup=markup)
        return  # ВАЖНО: останавливаем функцию, чтобы не сработала пересылка!

    elif message.text == "💰 Прайс-лист":
        bot.send_message(message.chat.id, "Минимальный заказ от 2000р. \nГелиевые шары от 150р/шт.")
        return # Останавливаем
    elif message.text == "📞 Связаться с мастером":
        bot.send_message(message.chat.id, "Напишите нам в Telegram: @username")
        return # Останавливаем

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

        # --- 2. Теперь логика пересылки (если это не кнопка) ---
    
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
        
        # --- 2. Основной обработчик кнопок ---
        # Обработка нажатий на инлайн-кнопки (callback)
@bot.callback_query_handler(func=lambda call: True)
def callback_worker(call):
    print(f"--- Нажата кнопка: {call.data} ---")

    item = None
    # --- УРОВЕНЬ 1: ШАРЫ ИЛИ ИГРУШКИ ---
    if call.data == "balloons":
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton(text="💐 Букеты", callback_data="sub_bouquets")
        btn2 = types.InlineKeyboardButton(text="📸 Фотозоны", callback_data="sub_zones")
        btn_back = types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
        markup.add(btn1, btn2)
        markup.add(btn_back)
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text="Раздел 🎈 Шары. Выберите категорию:", reply_markup=markup)
        return

    elif call.data == "big_toys":
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

    elif call.data == "bears_brown_white": 
        item = get_item_by_id("bears_brown_white") 
        # Карточка №2 для Мишек
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

        # --- Обработка добавления в корзину ---
    elif "add_" in call.data:
        item_name = call.data.replace("add_", "")
        user_id = call.from_user.id
        
        if user_id not in user_carts:
            user_carts[user_id] = []
        
        user_carts[user_id].append(item_name)
        
        bot.answer_callback_query(call.id, text=f"✅ {item_name} добавлен в корзину!")

    # --- КНОПКА НАЗАД В САМОЕ НАЧАЛО ---
    elif call.data == "back_to_main":
        markup = types.InlineKeyboardMarkup()
        btn_balloons = types.InlineKeyboardButton(text="🎈 Шары", callback_data="balloons")
        btn_toys = types.InlineKeyboardButton(text="🧸 Игрушки", callback_data="big_toys")
        markup.add(btn_balloons, btn_toys)
        
        # Если было фото — удаляем его, чтобы вернуться к чистому тексту
        if call.message.content_type == 'photo':
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Что вас интересует?", reply_markup=markup)
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                 text="Что вас интересует?", reply_markup=markup)

        # очистка корзины
    elif call.data == "clear_cart":
        user_id = call.from_user.id
        user_carts[user_id] = []
        bot.answer_callback_query(call.id, "Корзина очищена 🗑️") 

   # --- ОБРАБОТКА ЗАКАЗОВ (Запрос контакта) ---
    elif call.data == "checkout":
        # Создаем кнопки для телефона
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        btn_phone = types.KeyboardButton(text="📱 Отправить номер", request_contact=True)
        btn_skip = types.KeyboardButton(text="❌ Продолжить без номера")
        markup.add(btn_phone, btn_skip)
        
        bot.send_message(call.message.chat.id, 
                         "Чтобы мастер мог с вами связаться, отправьте номер телефона или нажмите 'Продолжить без номера':", 
                         reply_markup=markup)
        bot.answer_callback_query(call.id)
        

print("Бот запущен и ждет кнопок!")
# non_stop=True — бот будет пытаться переподключиться сам, использовать без infinity так -> bot.polling(non_stop=True) .
# skip_pending=True — бот проигнорирует те сообщения, что ему слали, пока он был «в обмороке» (чтобы он не спамил ответами сразу после включения).
bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)