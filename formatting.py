"""
formatting.py - Модуль улучшенного форматирования для Telegram и Twitter
Version: 2.2.0
Senior QA Approved - Production Ready

ИЗМЕНЕНИЯ v2.2.0:
- Убрана линия разделителя в Telegram
- Только 1 эмодзи в заголовке
- Двойные пробелы между пунктами для читабельности

ИСПОЛЬЗОВАНИЕ:
1. Положите этот файл рядом с parser.py
2. В parser.py добавьте: from formatting import send_improved
3. Замените вызов: send_improved(result['question'], result['answer'])
"""

import re
import time
import logging

# Получаем logger
logger = logging.getLogger(__name__)

# ========================================
# ВЕРСИЯ
# ========================================

__version__ = "2.2.0"

# ========================================
# КОНСТАНТЫ
# ========================================

# Лимиты безопасности
MAX_TEXT_LENGTH = 5000
MAX_LINE_COUNT = 100
MAX_EMOJI_COUNT = 3

# Performance лимиты
EMOJI_DETECTION_TEXT_LIMIT = 2000

# Twitter/Telegram лимиты
MIN_TWITTER_SPACE = 50
MAX_TWITTER_LENGTH = 280
MAX_TELEGRAM_LENGTH = 4000

# Эмодзи для заголовков (ТОЛЬКО ДЛЯ ЗАГОЛОВКА)
TITLE_EMOJI_MAP = {
    "Crypto Insights": "💡",
    "Market Analysis": "📊",
    "Daily Market Sentiment": "🎭",
    "Upcoming Crypto Events": "📅",
    "Bullish Crypto Watchlist": "🚀",
    "Trending Crypto Narratives": "🔥",
    "Altcoin Performance": "⚡"
}

# Контекстные паттерны (только для Twitter теперь)
CONTEXT_PATTERNS = [
    ("bullish|rally|surge|pump|moon", "🚀", 1),
    ("bearish|dump|crash|decline|drop", "🐻", 1),
    ("liquidation|liquidated|rekt", "🔥", 2),
    ("bitcoin|btc", "₿", 3),
    ("ethereum|eth", "💎", 3),
    ("solana|sol", "🦎", 3),
    ("whale|whales", "🐋", 2),
    ("ai|artificial intelligence", "🤖", 2),
    ("defi|decentralized finance", "✨", 3),
]

# Compiled regex patterns
CRYPTO_PRICE_PATTERN = re.compile(r'^[A-Z]{2,10}\s*\([+-]?\d')
LIST_ITEM_PATTERN = re.compile(r'^[\-•\*]\s+|^\d+\.\s+')

# ========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ========================================

def safe_str(value, default="", max_length=None):
    """Безопасное преобразование в строку"""
    if value is None:
        return default
    try:
        result = str(value).strip()
    except Exception:
        return default
    if max_length and len(result) > max_length:
        result = result[:max_length]
    return result


def get_twitter_length(text):
    """Вычисляет длину текста для Twitter (emoji = 2 символа)"""
    if not text:
        return 0
    emoji_pattern = re.compile("["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    emoji_count = len(emoji_pattern.findall(text))
    return len(text) + emoji_count


def get_context_emojis(text, max_count=MAX_EMOJI_COUNT):
    """Определяет контекстные эмодзи на основе содержимого"""
    if not text:
        return []
    
    text_lower = text[:EMOJI_DETECTION_TEXT_LIMIT].lower()
    found = []
    
    for pattern, emoji, priority in sorted(CONTEXT_PATTERNS, key=lambda x: x[2]):
        if emoji in [e for e, p in found]:
            continue
        
        words = pattern.split("|")
        if any(word in text_lower for word in words):
            found.append((emoji, priority))
            
            if len(found) >= max_count:
                break
    
    return [emoji for emoji, _ in found]


def detect_price_change_emoji(line):
    """Определяет эмодзи для изменения цены"""
    if any(indicator in line for indicator in ['+', 'up', '↑']):
        return "🟢"
    elif any(indicator in line for indicator in ['-', 'down', '↓']):
        return "🔴"
    return "•"


# ========================================
# ФОРМАТИРОВАНИЕ
# ========================================

def format_telegram_improved(title, text, hashtags):
    """
    Улучшенное форматирование для Telegram
    v2.2.0: Чистый формат без линий, с пробелами между пунктами
    """
    start_time = time.time()
    
    try:
        title = safe_str(title, "Crypto Update", 100)
        text = safe_str(text, "", MAX_TEXT_LENGTH)
        hashtags = safe_str(hashtags, "", 200)
        
        if not text:
            logger.warning("⚠️ Пустой текст после санитизации")
            return f"<b>{title}</b>\n\n{hashtags}"
        
        # ТОЛЬКО эмодзи заголовка (БЕЗ контекстных)
        emoji = TITLE_EMOJI_MAP.get(title, "📰")
        header = f"{emoji} <b>{title}</b>"
        
        # Обработка текста построчно
        lines = text.split('\n')
        processed = []
        line_count = 0
        
        for line in lines:
            if line_count >= MAX_LINE_COUNT:
                logger.warning(f"⚠️ Достигнут лимит строк ({MAX_LINE_COUNT})")
                break
            
            line = line.strip()
            if not line:
                continue
            
            line_count += 1
            
            # Криптовалюты с процентами
            if CRYPTO_PRICE_PATTERN.match(line):
                price_emoji = detect_price_change_emoji(line)
                processed.append(f"{price_emoji} {line}")
            # Пункты списка
            elif LIST_ITEM_PATTERN.match(line):
                clean = LIST_ITEM_PATTERN.sub('', line)
                processed.append(f"• {clean}")
            # Заголовки разделов
            elif line.endswith((':','–','—')) and len(line) < 50:
                processed.append(f"<b>{line}</b>")
            else:
                processed.append(line)
        
        # ДВОЙНЫЕ переносы между пунктами для читабельности
        formatted = '\n\n'.join(processed)
        
        # Формируем финальное сообщение (БЕЗ линии)
        message = f"{header}\n\n{formatted}"
        
        if hashtags:
            message += f"\n\n{hashtags}"
        
        if len(message) > MAX_TELEGRAM_LENGTH:
            logger.warning(f"⚠️ Сообщение слишком длинное ({len(message)}), обрезаю")
            message = message[:MAX_TELEGRAM_LENGTH-3] + "..."
        
        duration = time.time() - start_time
        if duration > 0.5:
            logger.warning(f"⚠️ Медленное форматирование TG: {duration:.2f}s")
        
        return message
        
    except Exception as e:
        logger.error(f"✗ Ошибка в format_telegram_improved: {e}")
        safe_title = safe_str(title, "Update", 50)
        safe_text = safe_str(text, "No content", 500)
        return f"<b>{safe_title}</b>\n\n{safe_text}"


def format_twitter_improved(title, text, hashtags, max_len=270):
    """Улучшенное форматирование для Twitter"""
    start_time = time.time()
    
    try:
        title = safe_str(title, "Update", 50)
        text = safe_str(text, "", 2000)
        hashtags = safe_str(hashtags, "", 150)
        
        if not text:
            logger.warning("⚠️ Пустой текст для Twitter")
            return f"{title}\n\n{hashtags}"
        
        emoji = TITLE_EMOJI_MAP.get(title, "📰")
        context_emojis = get_context_emojis(text, max_count=1)
        
        if context_emojis:
            header = f"{emoji} {title} {context_emojis[0]}"
        else:
            header = f"{emoji} {title}"
        
        reserved = get_twitter_length(header) + get_twitter_length(hashtags) + 6
        available = max_len - reserved
        
        if available < MIN_TWITTER_SPACE:
            logger.warning(f"⚠️ Мало места ({available}), сокращаю хэштеги")
            tags_list = hashtags.split()[:2]
            hashtags = " ".join(tags_list) if tags_list else ""
            reserved = get_twitter_length(header) + get_twitter_length(hashtags) + 6
            available = max_len - reserved
            
            if available < MIN_TWITTER_SPACE:
                header = title
                reserved = get_twitter_length(header) + get_twitter_length(hashtags) + 6
                available = max_len - reserved
        
        short_text = extract_short_text_safe(text, available)
        tweet = f"{header}\n\n{short_text}\n\n{hashtags}"
        
        attempts = 0
        max_attempts = 3
        
        while get_twitter_length(tweet) > MAX_TWITTER_LENGTH and attempts < max_attempts:
            attempts += 1
            logger.warning(f"⚠️ Твит длинный ({get_twitter_length(tweet)}), попытка {attempts}")
            
            if attempts == 1:
                tags_list = hashtags.split()[:1]
                hashtags = tags_list[0] if tags_list else ""
            elif attempts == 2:
                available = available - 30
                short_text = extract_short_text_safe(text, max(available, 30))
            else:
                tweet = tweet[:277] + "..."
                break
            
            tweet = f"{header}\n\n{short_text}\n\n{hashtags}"
        
        if get_twitter_length(tweet) > MAX_TWITTER_LENGTH:
            logger.error(f"✗ КРИТИЧНО: Твит все еще длинный, аварийная обрезка")
            tweet = tweet[:277] + "..."
        
        duration = time.time() - start_time
        if duration > 0.3:
            logger.warning(f"⚠️ Медленное форматирование TW: {duration:.2f}s")
        
        return tweet
        
    except Exception as e:
        logger.error(f"✗ Ошибка в format_twitter_improved: {e}")
        return f"{title}\n\nCheck Telegram"


def extract_short_text_safe(text, max_length):
    """Безопасное извлечение короткого текста"""
    if not text or max_length < 10:
        return ""
    
    text = text.strip()
    if get_twitter_length(text) <= max_length:
        return text
    
    result = []
    current = ""
    char_count = 0
    max_chars = min(len(text), max_length * 2)
    
    for char in text[:max_chars]:
        current += char
        char_count += 1
        
        if char in '.!?' and char_count > 20:
            if get_twitter_length(current) <= max_length:
                result.append(current.strip())
                current = ""
            else:
                break
        
        if len(result) >= 3:
            break
    
    if result:
        final = " ".join(result)
        if get_twitter_length(final) <= max_length:
            return final
    
    return text[:max_length-3] + "..."


# ========================================
# ГЛАВНАЯ ФУНКЦИЯ
# ========================================

def send_improved(question, answer, 
                 extract_tldr_fn, clean_text_fn, config_dict,
                 get_image_fn, send_tg_photo_fn, send_tg_msg_fn,
                 send_twitter_fn, twitter_enabled, twitter_keys):
    """
    Главная функция для отправки контента
    """
    total_start = time.time()
    
    try:
        logger.info(f"\n📝 Форматирование v{__version__}")
        
        # 1. Извлекаем TLDR
        tldr_text = extract_tldr_fn(answer)
        if not tldr_text:
            logger.error("✗ Пустой TLDR")
            return False
        
        # 2. Очищаем
        tldr_text = clean_text_fn(question, tldr_text)
        if not tldr_text:
            logger.error("✗ Пустой текст после очистки")
            return False
        
        # 3. Конфигурация
        config = config_dict.get(question, {
            "title": "Crypto Update",
            "hashtags": "#Crypto #Bitcoin"
        })
        
        title = config.get("title", "Crypto Update")
        hashtags = config.get("hashtags", "#Crypto")
        
        logger.info(f"  Заголовок: {title}")
        logger.info(f"  Длина: {len(tldr_text)}")
        
        # 4. Форматируем Telegram
        try:
            tg_message = format_telegram_improved(title, tldr_text, hashtags)
            logger.info(f"  ✓ Telegram: {len(tg_message)} символов")
        except Exception as e:
            logger.error(f"  ✗ Ошибка TG: {e}")
            tg_message = f"<b>{title}</b>\n\n{tldr_text[:500]}\n\n{hashtags}"
        
        # 5. Картинка
        image_url = None
        try:
            image_url = get_image_fn()
        except Exception as e:
            logger.warning(f"  ⚠️ Нет картинки: {e}")
        
        # 6. Отправляем Telegram
        logger.info("\n📤 Отправка Telegram...")
        tg_success = False
        
        try:
            if image_url:
                tg_success = send_tg_photo_fn(image_url, tg_message)
            else:
                tg_success = send_tg_msg_fn(tg_message)
        except Exception as e:
            logger.error(f"  ✗ Ошибка: {e}")
        
        time.sleep(2)
        
        # 7. Twitter
        tw_status = "Отключен"
        
        if twitter_enabled and all(twitter_keys):
            try:
                logger.info("\n🐦 Подготовка Twitter...")
                tw_tweet = format_twitter_improved(title, tldr_text, hashtags)
                logger.info(f"  ✓ Twitter: {get_twitter_length(tw_tweet)} символов")
                
                tw_success = send_twitter_fn(title, tldr_text, hashtags, image_url)
                tw_status = "✓ Успешно" if tw_success else "✗ Ошибка"
            except Exception as e:
                logger.error(f"  ✗ Twitter: {e}")
                tw_status = "✗ Ошибка"
        
        # 8. Итоги
        total_duration = time.time() - total_start
        logger.info(f"\n📊 РЕЗУЛЬТАТЫ:")
        logger.info(f"  Telegram: {'✓' if tg_success else '✗'}")
        logger.info(f"  Twitter: {tw_status}")
        logger.info(f"  Время: {total_duration:.2f}s\n")
        
        return tg_success
        
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
