"""
Парсер для CoinMarketCap AI - ПРОТЕСТИРОВАННАЯ ВЕРСИЯ 1.0
✅ 24/7 публикации по умному расписанию
✅ Отслеживание истории публикаций
✅ Динамические слоты с fallback на самый старый вопрос
✅ Группировка вариаций вопросов (up/down market)
✅ Retry логика и обработка ошибок
✅ Полное логирование и обработка edge cases
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import time
import json
import traceback
from datetime import datetime, timezone
import requests
import os
import sys
import random
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Глобальные настройки
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '2'))

# Telegram настройки
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or '8323539910:AAG6DYij-FuqT7q-ovsBNNgEnWH2V6FXhoM'
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID') or '-1003445906500'

# GitHub настройки для картинок
GITHUB_IMAGES_URL = "https://raw.githubusercontent.com/BRKME/coinmarketcap-parser/main/Images1/"
IMAGE_FILES = [f"{i}.jpg" for i in range(10, 101)]  # 10.jpg до 100.jpg (91 картинка)

# Расписание публикаций (час UTC : тип вопроса)
SCHEDULE = {
    0: "kols",           # What are KOLs discussing?
    1: "sentiment",      # What is the market sentiment?
    2: "market_direction", # Why is the market up/down?
    3: "DYNAMIC",        # Динамический слот
    4: "kols",
    5: "bullish",        # What cryptos are showing bullish momentum?
    6: "market_direction",
    7: "events",         # What upcoming events may impact crypto?
    8: "kols",
    9: "DYNAMIC",        # Динамический слот
    10: "market_direction",
    11: "narratives",    # What are the trending narratives?
    12: "kols",
    13: "altcoins",      # Are altcoins outperforming Bitcoin?
    14: "market_direction",
    15: "DYNAMIC",       # Динамический слот
    16: "kols",
    17: "sentiment",
    18: "market_direction",
    19: "events",
    20: "kols",
    21: "DYNAMIC",       # Динамический слот
    22: "market_direction",
    23: "narratives"
}

# Группы вопросов (для обработки вариаций)
QUESTION_GROUPS = {
    "market_direction": [
        "Why is the market up today?",
        "Why is the market down today?"
    ],
    "kols": ["What are KOLs discussing?"],
    "sentiment": ["What is the market sentiment?"],
    "events": ["What upcoming events may impact crypto?"],
    "bullish": ["What cryptos are showing bullish momentum?"],
    "narratives": ["What are the trending narratives?"],
    "altcoins": ["Are altcoins outperforming Bitcoin?"]
}

# Маппинг вопросов на заголовки и хэштеги для Telegram
QUESTION_DISPLAY_CONFIG = {
    "What are KOLs discussing?": {
        "title": "Crypto Insights",
        "hashtags": "#CryptoTwitter #KOLs #Alpha"
    },
    "What is the market sentiment?": {
        "title": "Daily Market Sentiment",
        "hashtags": "#FearAndGreed #CryptoSentiment #Bitcoin"
    },
    "What upcoming events may impact crypto?": {
        "title": "Upcoming Crypto Events",
        "hashtags": "#CryptoEvents #CryptoCalendar"
    },
    "What cryptos are showing bullish momentum?": {
        "title": "Bullish Crypto Watchlist",
        "hashtags": "#Altseason #Bullish #CryptoGems"
    },
    "What are the trending narratives?": {
        "title": "Trending Crypto Narratives",
        "hashtags": "#CryptoNarratives #RWA #AIcrypto"
    },
    "Why is the market up today?": {
        "title": "Market Analysis",
        "hashtags": "#Bitcoin #CryptoMarket #BullRun"
    },
    "Why is the market down today?": {
        "title": "Market Analysis",
        "hashtags": "#Bitcoin #CryptoMarket #Correction"
    },
    "Are altcoins outperforming Bitcoin?": {
        "title": "Altcoin Performance",
        "hashtags": "#Altcoins #Bitcoin #AltcoinSeason"
    }
}

def get_question_group(question_text):
    """Определяет к какой группе относится вопрос"""
    if not question_text:
        return "dynamic"
    
    question_lower = question_text.lower()
    
    # Проверяем market direction (up/down)
    if "why is the market" in question_lower and ("up" in question_lower or "down" in question_lower):
        return "market_direction"
    
    # Проверяем остальные группы
    if "kol" in question_lower:
        return "kols"
    if "sentiment" in question_lower:
        return "sentiment"
    if "upcoming events" in question_lower or "events" in question_lower and "impact" in question_lower:
        return "events"
    if "bullish" in question_lower and "momentum" in question_lower:
        return "bullish"
    if "trending narratives" in question_lower or "narratives" in question_lower:
        return "narratives"
    if "altcoins" in question_lower and "bitcoin" in question_lower:
        return "altcoins"
    
    return "dynamic"

def load_publication_history():
    """Загружает историю публикаций из JSON файла"""
    try:
        if os.path.exists('publication_history.json'):
            with open('publication_history.json', 'r', encoding='utf-8') as f:
                history = json.load(f)
                logger.info(f"✓ История публикаций загружена: {len(history.get('last_published', {}))} групп")
                return history
    except Exception as e:
        logger.warning(f"⚠️ Ошибка загрузки истории: {e}")
    
    logger.info("📝 Создание новой истории публикаций")
    return {
        "last_published": {},
        "last_dynamic_question": "",
        "dynamic_published_at": ""
    }

def save_publication_history(history):
    """Сохраняет историю публикаций в JSON файл"""
    try:
        with open('publication_history.json', 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.info("✓ История публикаций обновлена")
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка сохранения истории: {e}")
        return False

def get_oldest_question_group(history):
    """Находит группу вопроса которая публиковалась дольше всего назад"""
    last_published = history.get("last_published", {})
    
    all_groups = ["kols", "sentiment", "market_direction", "events", "bullish", "narratives", "altcoins"]
    
    if not last_published:
        logger.info("📊 История пуста, возвращаю 'kols'")
        return "kols"
    
    oldest_group = None
    oldest_time = None
    
    for group in all_groups:
        timestamp_str = last_published.get(group)
        
        if not timestamp_str:
            logger.info(f"📊 Группа '{group}' никогда не публиковалась")
            return group
            
        try:
            pub_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if oldest_time is None or pub_time < oldest_time:
                oldest_time = pub_time
                oldest_group = group
        except Exception as e:
            logger.warning(f"⚠️ Ошибка парсинга даты для {group}: {e}")
            return group
    
    logger.info(f"📊 Самая старая группа: {oldest_group} (опубликована {oldest_time})")
    return oldest_group if oldest_group else "kols"

def find_question_by_group(questions_list, group_name):
    """Находит вопрос из списка по группе"""
    if not questions_list:
        logger.warning("⚠️ Пустой список вопросов")
        return None
    
    for q in questions_list:
        if get_question_group(q) == group_name:
            logger.info(f"✓ Найден вопрос для группы '{group_name}': {q}")
            return q
    
    logger.warning(f"⚠️ Не найден вопрос для группы '{group_name}'")
    return None

def send_telegram_message(message, parse_mode='HTML'):
    """Отправляет сообщение в Telegram с разбивкой на части при необходимости"""
    try:
        # Проверка на пустые значения
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN.strip() == "" or TELEGRAM_CHAT_ID.strip() == "":
            logger.error("✗ Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
            return False
        
        max_length = 4000
        
        if len(message) <= max_length:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': parse_mode
            }
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code == 200:
                logger.info("✓ Сообщение отправлено в Telegram")
                return True
            else:
                logger.error(f"✗ Ошибка отправки в Telegram: {response.status_code} - {response.text}")
                return False
        else:
            logger.info(f"📨 Сообщение длинное ({len(message)} chars), разбиваю на части...")
            parts = []
            current_part = ""
            
            for line in message.split('\n'):
                if len(current_part) + len(line) + 1 > max_length:
                    if current_part:
                        parts.append(current_part)
                        current_part = line
                    else:
                        for i in range(0, len(line), max_length - 100):
                            parts.append(line[i:i + max_length - 100])
                else:
                    current_part = current_part + "\n" + line if current_part else line
            
            if current_part:
                parts.append(current_part)
            
            for i, part in enumerate(parts, 1):
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': part,
                    'parse_mode': parse_mode
                }
                response = requests.post(url, data=payload, timeout=10)
                logger.info(f"  ✓ Часть {i}/{len(parts)} отправлена")
                time.sleep(0.5)
            
            return True
            
    except Exception as e:
        logger.error(f"✗ Ошибка при отправке в Telegram: {e}")
        traceback.print_exc()
        return False

def send_telegram_photo_with_caption(photo_url, caption, parse_mode='HTML'):
    """Отправляет фото с подписью в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        
        logger.info(f"🔍 Попытка отправить фото: {photo_url}")
        logger.info(f"📏 Длина caption: {len(caption)} символов")
        
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'photo': photo_url
        }
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info("✓ Фото отправлено в Telegram")
            time.sleep(1)
            send_telegram_message(caption, parse_mode)
            return True
        else:
            logger.warning(f"⚠️ Ошибка отправки фото: {response.status_code} - {response.text}")
            logger.info("⚠️ Отправляю только текст без фото")
            send_telegram_message(caption, parse_mode)
            return False
                
    except Exception as e:
        logger.error(f"✗ Ошибка при отправке фото в Telegram: {e}")
        traceback.print_exc()
        logger.info("⚠️ Отправляю только текст без фото")
        send_telegram_message(caption, parse_mode)
        return False

def get_random_image_url():
    """Возвращает случайный URL картинки из GitHub"""
    random_image = random.choice(IMAGE_FILES)
    url = GITHUB_IMAGES_URL + random_image
    logger.info(f"🎨 Выбрана картинка: {random_image}")
    return url

def extract_tldr_from_answer(answer):
    """Извлекает только TLDR часть из ответа"""
    try:
        if not answer:
            return ""
        
        # Убираем строку "Researched for Xs"
        answer = '\n'.join([line for line in answer.split('\n') if not line.strip().startswith('Researched for')])
        
        # Ищем TLDR секцию
        if 'TLDR' in answer:
            tldr_start = answer.find('TLDR')
            deep_dive_start = answer.find('Deep Dive')
            
            if deep_dive_start != -1:
                tldr_section = answer[tldr_start:deep_dive_start].strip()
            else:
                tldr_section = answer[tldr_start:].strip()
            
            tldr_section = tldr_section.replace('TLDR', '', 1).strip()
            return tldr_section
        else:
            logger.warning("⚠️ TLDR не найден, возвращаю первые 500 символов")
            return answer[:500] + ("..." if len(answer) > 500 else "")
            
    except Exception as e:
        logger.error(f"⚠️ Ошибка извлечения TLDR: {e}")
        return answer[:500] + ("..." if len(answer) > 500 else "")

def clean_question_specific_text(question, text):
    """Убирает специфичные для вопросов ненужные строки"""
    try:
        if not text:
            return text
        
        cleaners = [
            ("What upcoming events may impact crypto?", 
             "These are the upcoming crypto events that may impact crypto the most:"),
            ("What cryptos are showing bullish momentum?", 
             "Here are the trending cryptos based on CoinMarketCap's evolving momentum algorithm (news, social, price momentum)"),
            ("What are the trending narratives?", 
             "Here are the trending narratives based on CoinMarketCap's evolving narrative algorithm (price, news, social momentum):")
        ]
        
        for question_pattern, text_to_remove in cleaners:
            if question_pattern in question:
                text = text.replace(text_to_remove, "").strip()
        
        return text
    except Exception as e:
        logger.error(f"⚠️ Ошибка очистки текста: {e}")
        return text

def send_question_answer_to_telegram(question, answer):
    """Отправляет вопрос и TLDR в Telegram с картинкой. Возвращает True если успешно."""
    try:
        tldr_text = extract_tldr_from_answer(answer)
        tldr_text = clean_question_specific_text(question, tldr_text)
        
        if not tldr_text:
            logger.error("✗ Пустой TLDR после обработки")
            return False
        
        # Получаем конфигурацию для отображения
        display_config = QUESTION_DISPLAY_CONFIG.get(question, {
            "title": "Crypto Update",
            "hashtags": "#Crypto #Bitcoin"
        })
        
        title = display_config["title"]
        hashtags = display_config["hashtags"]
        
        # Форматируем сообщение БЕЗ вопроса, только заголовок + текст + хэштеги
        short_message = f"""<b>{title}</b>

{tldr_text}

{hashtags}"""
        
        image_url = get_random_image_url()
        
        logger.info(f"\n📤 Отправка в Telegram...")
        logger.info(f"📋 Заголовок: {title}")
        logger.info(f"📏 Длина TLDR: {len(tldr_text)} символов")
        logger.info(f"🏷 Хэштеги: {hashtags}")
        
        result = send_telegram_photo_with_caption(image_url, short_message)
        time.sleep(1)
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Ошибка при отправке: {e}")
        traceback.print_exc()
        return False

async def accept_cookies(page):
    """Принимает cookies если баннер появился"""
    try:
        cookie_buttons = [
            'button:has-text("Accept Cookies and Continue")',
            'button:has-text("Accept All")',
            'button:has-text("Accept")',
            'text="Accept Cookies and Continue"'
        ]

        for selector in cookie_buttons:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    logger.info("✓ Cookie-баннер принят")
                    await asyncio.sleep(2)
                    return True
            except:
                continue

        return False
    except Exception as e:
        logger.warning(f"⚠️ Предупреждение при обработке cookies: {e}")
        return False

async def reset_to_question_list(page):
    """Возвращает страницу к состоянию со списком вопросов"""
    try:
        reset_selectors = [
            'button:has-text("New")',
            'button:has-text("Reset")',
            'button:has-text("Clear")',
            'a:has-text("New")',
            '[aria-label*="new"]',
            '[aria-label*="reset"]',
            '[title*="New"]',
            '[title*="Reset"]'
        ]

        for selector in reset_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    await asyncio.sleep(2)
                    logger.info("  ✓ Сброс чата выполнен")
                    return True
            except:
                continue

        logger.info("  ℹ️  Переход на базовый URL...")
        await page.goto('https://coinmarketcap.com/cmc-ai/ask/', wait_until='domcontentloaded', timeout=15000)
        await accept_cookies(page)
        await asyncio.sleep(3)
        return True

    except Exception as e:
        logger.warning(f"  ⚠️ Ошибка сброса: {e}")
        try:
            await page.goto('https://coinmarketcap.com/cmc-ai/ask/', timeout=15000)
            await asyncio.sleep(2)
            return True
        except:
            return False

async def get_ai_response(page, question_text):
    """Получает ответ AI используя точный селектор"""
    try:
        logger.info("  ⏳ Ожидание генерации ответа AI...")
        await asyncio.sleep(5)

        max_attempts = 25

        for attempt in range(max_attempts):
            try:
                assistant_container = await page.query_selector('div.MemoizedChatMessage_message-assistant-wrapper__eAoOF')

                if assistant_container:
                    full_text = await assistant_container.inner_text()

                    if (full_text and len(full_text) > 200 and 'TLDR' in full_text):
                        if full_text.startswith('BTC$'):
                            parts = full_text.split(question_text)
                            if len(parts) > 1:
                                full_text = question_text + parts[1]

                        logger.info(f"  ✓ Ответ найден на попытке {attempt + 1}")
                        return full_text.strip()

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                assistant_div = soup.find('div', class_=lambda x: x and 'message-assistant' in str(x))

                if assistant_div:
                    paragraphs = assistant_div.find_all('p')
                    if len(paragraphs) > 2:
                        full_answer = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                        if len(full_answer) > 200 and 'TLDR' in full_answer:
                            logger.info(f"  ✓ Ответ найден на попытке {attempt + 1} (BeautifulSoup)")
                            return full_answer

            except Exception as e:
                pass

            if attempt < max_attempts - 1:
                await asyncio.sleep(1)

            if (attempt + 1) % 5 == 0:
                logger.info(f"  ⏳ Попытка {attempt + 1}/{max_attempts}...")

        logger.warning("  ⚠️ Ответ не найден после всех попыток")
        return None

    except Exception as e:
        logger.error(f"  ❌ Ошибка: {e}")
        return None

async def click_and_get_response(page, question_text, attempt_num=1):
    """Кликает по кнопке с вопросом и получает ответ AI"""
    try:
        logger.info(f"\n🔍 Поиск кнопки: '{question_text}' (попытка {attempt_num})")

        button = await page.query_selector(f'text="{question_text}"')

        if not button:
            logger.error(f"✗ Кнопка не найдена")
            return None

        logger.info(f"✓ Кнопка найдена, выполняю клик...")
        await button.click()

        response = await get_ai_response(page, question_text)

        if response:
            logger.info(f"✓ Обработка завершена (длина ответа: {len(response)} символов)")
            return {
                'question': question_text,
                'answer': response,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'attempt': attempt_num,
                'length': len(response)
            }
        else:
            logger.error(f"✗ Ответ не получен")
            return None

    except Exception as e:
        logger.error(f"✗ Ошибка при клике: {e}")
        return None

async def get_all_questions(page):
    """Получает список всех доступных вопросов"""
    try:
        elements = await page.query_selector_all('div.BaseChip_labelWrapper__pQXPT')
        
        questions_list = []
        seen = set()
        
        for elem in elements:
            text = await elem.inner_text()
            text = text.strip()
            if text and text not in seen:
                questions_list.append(text)
                seen.add(text)
        
        logger.info(f"✓ Найдено уникальных вопросов: {len(questions_list)}")
        return questions_list
    except Exception as e:
        logger.error(f"✗ Ошибка получения списка вопросов: {e}")
        return []

async def main_parser():
    """Главная функция парсера с умным расписанием"""
    browser = None
    try:
        logger.info("="*70)
        logger.info("🚀 ЗАПУСК ПАРСЕРА COINMARKETCAP AI v1.0")
        logger.info("="*70)
        
        async with async_playwright() as p:
            logger.info("🌐 Загрузка страницы...")

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--single-process'
                ]
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )

            page = await context.new_page()

            for attempt in range(3):
                try:
                    await page.goto('https://coinmarketcap.com/cmc-ai/ask/', wait_until='domcontentloaded', timeout=20000)
                    logger.info("✓ Страница загружена")
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"⚠️ Попытка {attempt + 1} не удалась, пробую еще раз...")
                        await asyncio.sleep(3)
                    else:
                        raise

            logger.info("🍪 Проверка cookie-баннера...")
            await accept_cookies(page)

            logger.info("⏳ Ожидание загрузки контента (5 секунд)...")
            await asyncio.sleep(5)

            # Получаем список всех вопросов
            logger.info("\n🔍 ПОЛУЧЕНИЕ СПИСКА ВОПРОСОВ")
            questions_list = await get_all_questions(page)
            
            if not questions_list:
                raise Exception("Не найдено ни одного вопроса на странице!")
            
            for i, q in enumerate(questions_list, 1):
                group = get_question_group(q)
                logger.info(f"  {i}. {q} [{group}]")

            # Загружаем историю публикаций
            history = load_publication_history()
            
            # Определяем текущий час UTC
            current_hour = datetime.now(timezone.utc).hour
            scheduled_group = SCHEDULE.get(current_hour)
            
            if not scheduled_group:
                raise Exception(f"Нет расписания для часа {current_hour}")
            
            logger.info(f"\n⏰ Текущий час UTC: {current_hour}")
            logger.info(f"📅 По расписанию должна быть группа: {scheduled_group}")
            
            # Определяем какой вопрос публиковать
            question_to_publish = None
            
            if scheduled_group == "DYNAMIC":
                logger.info("\n🎯 Динамический слот!")
                
                # Находим динамический вопрос
                dynamic_question = None
                for q in questions_list:
                    if get_question_group(q) == "dynamic":
                        dynamic_question = q
                        break
                
                if dynamic_question:
                    last_dynamic = history.get("last_dynamic_question", "")
                    
                    if dynamic_question != last_dynamic:
                        logger.info(f"✨ Динамический вопрос изменился!")
                        logger.info(f"   Старый: {last_dynamic}")
                        logger.info(f"   Новый: {dynamic_question}")
                        question_to_publish = dynamic_question
                        
                        # Обновляем историю динамического вопроса
                        history["last_dynamic_question"] = dynamic_question
                    else:
                        logger.info(f"⚠️ Динамический вопрос не изменился: {dynamic_question}")
                        logger.info(f"   Ищем самый старый вопрос...")
                        oldest_group = get_oldest_question_group(history)
                        question_to_publish = find_question_by_group(questions_list, oldest_group)
                        if question_to_publish:
                            scheduled_group = oldest_group
                        else:
                            logger.warning(f"⚠️ Не найден вопрос для группы {oldest_group}, публикуем динамический")
                            question_to_publish = dynamic_question
                            scheduled_group = "DYNAMIC"
                else:
                    logger.warning("⚠️ Динамический вопрос не найден на странице")
                    logger.info("   Публикуем самый старый вопрос...")
                    oldest_group = get_oldest_question_group(history)
                    question_to_publish = find_question_by_group(questions_list, oldest_group)
                    if question_to_publish:
                        scheduled_group = oldest_group
                    else:
                        raise Exception(f"Критическая ошибка: не найден вопрос для {oldest_group}")
            else:
                # Обычный слот по расписанию
                question_to_publish = find_question_by_group(questions_list, scheduled_group)
            
            if not question_to_publish:
                logger.error("✗ Не удалось найти вопрос для публикации!")
                logger.error("📋 Доступные вопросы:")
                for q in questions_list:
                    logger.error(f"   - {q} [{get_question_group(q)}]")
                
                raise Exception("Не найден вопрос для публикации")
            
            logger.info(f"\n✅ Выбран вопрос для публикации: {question_to_publish}")
            
            # Парсим ответ на выбранный вопрос с повторными попытками
            result = None
            for retry in range(MAX_RETRIES + 1):
                if retry > 0:
                    logger.info(f"\n🔄 Повторная попытка {retry}/{MAX_RETRIES}")
                    await reset_to_question_list(page)
                    await asyncio.sleep(3)
                
                result = await click_and_get_response(page, question_to_publish, attempt_num=retry + 1)
                
                if result:
                    break
            
            if not result:
                raise Exception(f"Не удалось получить ответ после {MAX_RETRIES + 1} попыток")
            
            # Отправляем в Telegram
            logger.info("\n📤 ОТПРАВКА В TELEGRAM")
            send_success = send_question_answer_to_telegram(result['question'], result['answer'])
            
            if not send_success:
                logger.warning("⚠️ Ошибка отправки в Telegram, но продолжаем")
            
            # Обновляем историю публикаций
            if scheduled_group == "DYNAMIC":
                history["dynamic_published_at"] = datetime.now(timezone.utc).isoformat()
                history["last_published"]["dynamic"] = datetime.now(timezone.utc).isoformat()
            else:
                history["last_published"][scheduled_group] = datetime.now(timezone.utc).isoformat()
            
            # Сохраняем дополнительную информацию для отладки
            history["last_publication"] = {
                "question": result['question'],
                "group": scheduled_group,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "hour_utc": current_hour,
                "answer_length": result['length']
            }
            
            save_publication_history(history)
            
            logger.info(f"\n🎯 ИТОГ")
            logger.info(f"  ✓ Вопрос: {result['question']}")
            logger.info(f"  ✓ Группа: {scheduled_group}")
            logger.info(f"  ✓ Длина ответа: {result['length']} символов")
            logger.info(f"  ✓ Опубликовано в Telegram: {send_success}")
            logger.info("="*70)

            await browser.close()
            logger.info("✓ Браузер закрыт\n")
            
            return True

    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(traceback.format_exc())
        
        # Пытаемся закрыть браузер при ошибке
        try:
            if browser:
                await browser.close()
        except:
            pass
        
        # Отправляем уведомление об ошибке в Telegram
        try:
            current_hour = datetime.now(timezone.utc).hour
            scheduled_group = SCHEDULE.get(current_hour, "unknown")
            
            error_message = f"""<b>❌ ОШИБКА ПАРСЕРА</b>

⏰ <b>Время:</b> {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC
🕐 <b>Час UTC:</b> {current_hour}
📋 <b>Запланированная группа:</b> {scheduled_group}

<b>Ошибка:</b>
<code>{str(e)[:1000]}</code>

<i>Парсер будет повторен в следующий час</i>"""
            
            send_telegram_message(error_message)
        except Exception as notification_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notification_error}")
        
        return False


def main():
    """Точка входа в программу"""
    try:
        logger.info("\n" + "="*70)
        logger.info("🤖 COINMARKETCAP AI PARSER - SCHEDULED MODE")
        logger.info("="*70)
        logger.info(f"📅 Дата запуска: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logger.info(f"⚙️  Настройки:")
        logger.info(f"   • MAX_RETRIES: {MAX_RETRIES}")
        logger.info(f"   • Telegram Bot Token: {'✓ Установлен' if TELEGRAM_BOT_TOKEN else '✗ Не установлен'}")
        logger.info(f"   • Telegram Chat ID: {'✓ Установлен' if TELEGRAM_CHAT_ID else '✗ Не установлен'}")
        logger.info("="*70 + "\n")
        
        # Запускаем основной парсер
        success = asyncio.run(main_parser())
        
        if success:
            logger.info("\n✅ ПАРСИНГ ЗАВЕРШЕН УСПЕШНО!")
            sys.exit(0)
        else:
            logger.error("\n❌ ПАРСИНГ ЗАВЕРШЕН С ОШИБКОЙ!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Парсинг прерван пользователем (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА В MAIN: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
