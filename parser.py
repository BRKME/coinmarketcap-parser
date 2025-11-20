"""
Парсер для CoinMarketCap AI - УЛУЧШЕННАЯ ВЕРСИЯ
✅ Обработка всех 8 вопросов
✅ Повторные попытки для пропущенных
✅ Отправка каждого вопроса/ответа отдельным сообщением в Telegram
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import time
import json
import csv
import traceback
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import os
import sys
import random

# Глобальные настройки
MAX_QUESTIONS = int(os.getenv('MAX_QUESTIONS', 8))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 2))

# Telegram настройки
TELEGRAM_BOT_TOKEN = "8323539910:AAG6DYij-FuqT7q-ovsBNNgEnWH2V6FXhoM"
TELEGRAM_CHAT_ID = "-1003445906500"

# GitHub настройки для картинок
GITHUB_IMAGES_URL = "https://raw.githubusercontent.com/BRKME/coinmarketcap-parser/main/Images1/"
# Список имен файлов картинок (от 10.jpg до 35.jpg)
IMAGE_FILES = [f"{i}.jpg" for i in range(10, 36)]  # Генерирует: 10.jpg, 11.jpg, ..., 35.jpg

def send_telegram_message(message, parse_mode='HTML'):
    """Отправляет сообщение в Telegram с разбивкой на части при необходимости"""
    try:
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
                print("✓ Сообщение отправлено в Telegram")
                return True
            else:
                print(f"✗ Ошибка отправки в Telegram: {response.status_code}")
                return False
        else:
            # Разбиваем длинное сообщение
            print(f"📨 Сообщение длинное ({len(message)} chars), разбиваю на части...")
            parts = []
            current_part = ""
            
            for line in message.split('\n'):
                if len(current_part) + len(line) + 1 > max_length:
                    if current_part:
                        parts.append(current_part)
                        current_part = line
                    else:
                        # Строка слишком длинная - режем по символам
                        for i in range(0, len(line), max_length - 100):
                            parts.append(line[i:i + max_length - 100])
                else:
                    current_part = current_part + "\n" + line if current_part else line
            
            if current_part:
                parts.append(current_part)
            
            # Отправляем части
            for i, part in enumerate(parts, 1):
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': part,
                    'parse_mode': parse_mode
                }
                response = requests.post(url, data=payload, timeout=10)
                print(f"  ✓ Часть {i}/{len(parts)} отправлена")
                time.sleep(0.5)  # Небольшая пауза между частями
            
            return True
            
    except Exception as e:
        print(f"✗ Ошибка при отправке в Telegram: {e}")
        return False

def send_telegram_photo_with_caption(photo_url, caption, parse_mode='HTML'):
    """Отправляет фото с подписью в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        
        print(f"🔍 Попытка отправить фото: {photo_url}")
        print(f"📏 Длина caption: {len(caption)} символов")
        
        # Telegram всегда требует отправлять длинные тексты отдельно
        # Сначала отправляем фото без подписи
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'photo': photo_url
        }
        response = requests.post(url, data=payload, timeout=30)
        
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ Фото отправлено в Telegram")
            # Ждем немного и отправляем текст отдельным сообщением
            time.sleep(1)
            send_telegram_message(caption, parse_mode)
            return True
        else:
            print(f"✗ Ошибка отправки фото: {response.status_code} - {response.text}")
            # Если фото не отправилось - отправляем хотя бы текст
            print("⚠️ Отправляю только текст без фото")
            send_telegram_message(caption, parse_mode)
            return False
                
    except Exception as e:
        print(f"✗ Ошибка при отправке фото в Telegram: {e}")
        traceback.print_exc()
        # В случае ошибки отправляем хотя бы текст
        print("⚠️ Отправляю только текст без фото")
        send_telegram_message(caption, parse_mode)
        return False

def get_random_image_url():
    """Возвращает случайный URL картинки из GitHub"""
    random_image = random.choice(IMAGE_FILES)
    return GITHUB_IMAGES_URL + random_image

def extract_tldr_from_answer(answer):
    """Извлекает только TLDR часть из ответа"""
    try:
        # Убираем строку "Researched for Xs"
        answer = '\n'.join([line for line in answer.split('\n') if not line.strip().startswith('Researched for')])
        
        # Ищем TLDR секцию
        if 'TLDR' in answer:
            # Находим начало TLDR
            tldr_start = answer.find('TLDR')
            
            # Находим начало Deep Dive (конец TLDR)
            deep_dive_start = answer.find('Deep Dive')
            
            if deep_dive_start != -1:
                # Извлекаем только TLDR часть
                tldr_section = answer[tldr_start:deep_dive_start].strip()
            else:
                # Если нет Deep Dive, берем все после TLDR до конца
                tldr_section = answer[tldr_start:].strip()
            
            return tldr_section
        else:
            # Если нет TLDR, возвращаем первые 500 символов
            return answer[:500] + "..."
            
    except Exception as e:
        print(f"⚠️ Ошибка извлечения TLDR: {e}")
        return answer[:500] + "..."

def send_question_answer_to_telegram(question_num, total_questions, question, answer):
    """Отправляет вопрос и TLDR в Telegram с картинкой"""
    try:
        # Извлекаем только TLDR часть
        tldr_text = extract_tldr_from_answer(answer)
        
        # Форматируем короткое сообщение с вопросом и TLDR
        short_message = f"""<b>{question}</b>

{tldr_text}

{'─' * 40}"""
        
        # Получаем случайную картинку
        image_url = get_random_image_url()
        
        print(f"\n📤 Отправка вопроса {question_num}/{total_questions} в Telegram с картинкой...")
        print(f"📏 Длина TLDR: {len(tldr_text)} символов")
        
        send_telegram_photo_with_caption(image_url, short_message)
        
        # Пауза между сообщениями
        time.sleep(1)
        
    except Exception as e:
        print(f"✗ Ошибка при отправке вопроса {question_num}: {e}")

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
                    print("✓ Cookie-баннер принят")
                    await asyncio.sleep(2)
                    return True
            except:
                continue

        return False
    except Exception as e:
        print(f"⚠️ Предупреждение при обработке cookies: {e}")
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
                    print("  ✓ Сброс чата выполнен")
                    return True
            except:
                continue

        print("  ℹ️  Переход на базовый URL...")
        await page.goto('https://coinmarketcap.com/cmc-ai/ask/', wait_until='domcontentloaded', timeout=15000)
        await accept_cookies(page)
        await asyncio.sleep(3)
        return True

    except Exception as e:
        print(f"  ⚠️ Ошибка сброса: {e}")
        try:
            await page.goto('https://coinmarketcap.com/cmc-ai/ask/', timeout=15000)
            await asyncio.sleep(2)
            return True
        except:
            return False

async def get_ai_response(page, question_text):
    """Получает ответ AI используя точный селектор"""
    try:
        print("  ⏳ Ожидание генерации ответа AI...")
        await asyncio.sleep(5)

        max_attempts = 25

        for attempt in range(max_attempts):
            try:
                assistant_container = await page.query_selector('div.MemoizedChatMessage_message-assistant-wrapper__eAoOF')

                if assistant_container:
                    full_text = await assistant_container.inner_text()

                    if (full_text and
                        len(full_text) > 200 and
                        'TLDR' in full_text):

                        if full_text.startswith('BTC$'):
                            parts = full_text.split(question_text)
                            if len(parts) > 1:
                                full_text = question_text + parts[1]

                        print(f"  ✓ Ответ найден на попытке {attempt + 1}")
                        return full_text.strip()

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')

                assistant_div = soup.find('div', class_=lambda x: x and 'message-assistant' in str(x))

                if assistant_div:
                    paragraphs = assistant_div.find_all('p')

                    if len(paragraphs) > 2:
                        full_answer = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

                        if len(full_answer) > 200 and 'TLDR' in full_answer:
                            print(f"  ✓ Ответ найден на попытке {attempt + 1} (BeautifulSoup)")
                            return full_answer

            except Exception as e:
                pass

            if attempt < max_attempts - 1:
                await asyncio.sleep(1)

            if (attempt + 1) % 5 == 0:
                print(f"  ⏳ Попытка {attempt + 1}/{max_attempts}...")

        print("  ⚠️ Ответ не найден после всех попыток")
        return None

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return None

async def click_and_get_response(page, question_text, attempt_num=1):
    """Кликает по кнопке с вопросом и получает ответ AI"""
    try:
        print(f"\n🔍 Поиск кнопки: '{question_text}' (попытка {attempt_num})")

        button = await page.query_selector(f'text="{question_text}"')

        if not button:
            print(f"✗ Кнопка не найдена")
            return None

        print(f"✓ Кнопка найдена, выполняю клик...")
        await button.click()

        response = await get_ai_response(page, question_text)

        if response:
            print(f"✓ Обработка завершена (длина ответа: {len(response)} символов)")

            return {
                'question': question_text,
                'answer': response,
                'timestamp': datetime.now().isoformat(),
                'attempt': attempt_num,
                'length': len(response)
            }
        else:
            print(f"✗ Ответ не получен")
            return None

    except Exception as e:
        print(f"✗ Ошибка при клике: {e}")
        return None

async def parse_all_questions_with_retries(page, questions_list, max_questions=8, max_retries=2):
    """Парсит все вопросы с повторными попытками для пропущенных"""
    results = []
    failed_questions = []

    print(f"\n📝 СБОР ОТВЕТОВ НА ВОПРОСЫ ({min(max_questions, len(questions_list))} вопросов)")

    # Первый проход - обрабатываем все вопросы
    for i, question in enumerate(questions_list[:max_questions], 1):
        print(f"\n[{i}/{min(max_questions, len(questions_list))}] Обработка вопроса...")

        result = await click_and_get_response(page, question, attempt_num=1)

        if result:
            results.append(result)
            print(f"✓ Успешно обработан")
        else:
            print(f"✗ Не удалось получить ответ, добавляю в список повторов")
            failed_questions.append(question)

        if i < min(max_questions, len(questions_list)):
            await reset_to_question_list(page)
            await asyncio.sleep(2)

    # Повторные попытки для пропущенных вопросов
    if failed_questions and max_retries > 0:
        print(f"\n🔄 ПОВТОРНЫЕ ПОПЫТКИ ({len(failed_questions)} вопросов)")

        for retry_attempt in range(2, max_retries + 2):
            if not failed_questions:
                break

            print(f"\n📍 Попытка #{retry_attempt} для {len(failed_questions)} вопросов")

            still_failed = []

            for question in failed_questions:
                print(f"\n🔄 Повторная обработка: '{question}'")

                result = await click_and_get_response(page, question, attempt_num=retry_attempt)

                if result:
                    results.append(result)
                    print(f"✓ Успешно получен ответ!")
                else:
                    still_failed.append(question)
                    print(f"✗ Все еще не удалось")

                await reset_to_question_list(page)
                await asyncio.sleep(2)

            failed_questions = still_failed

    print(f"\n📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ")
    print(f"  ✅ Успешно обработано: {len(results)}/{min(max_questions, len(questions_list))}")
    print(f"  ❌ Не удалось обработать: {len(failed_questions)}")

    return results, failed_questions

def calculate_statistics(results):
    """Вычисляет статистику по длине ответов"""
    if not results:
        return {}

    lengths = [r['length'] for r in results]

    return {
        'total_answers': len(results),
        'avg_length': sum(lengths) // len(lengths),
        'min_length': min(lengths),
        'max_length': max(lengths),
        'total_chars': sum(lengths)
    }

def save_full_report_to_file(results, filename='full_report.txt'):
    """Сохраняет полный отчет со всеми Deep Dive в текстовый файл"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("COINMARKETCAP AI - ПОЛНЫЙ ОТЧЕТ\n")
            f.write(f"Дата и время: {timestamp}\n")
            f.write(f"Всего вопросов: {len(results)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, result in enumerate(results, 1):
                # Убираем "Researched for Xs"
                answer = '\n'.join([line for line in result['answer'].split('\n') 
                                   if not line.strip().startswith('Researched for')])
                
                f.write(f"\n{'=' * 80}\n")
                f.write(f"ВОПРОС {i}/{len(results)}\n")
                f.write(f"{'=' * 80}\n\n")
                f.write(f"{result['question']}\n\n")
                f.write(f"{answer}\n\n")
                f.write(f"Длина ответа: {result['length']} символов\n")
                f.write(f"Время обработки: {result['timestamp']}\n")
                f.write(f"\n{'─' * 80}\n")
        
        print(f"✓ Полный отчет сохранен: {filename}")
        return filename
        
    except Exception as e:
        print(f"✗ Ошибка сохранения полного отчета: {e}")
        return None

def save_to_json(data, filename='cmc_full_data.json'):
    """Сохраняет данные в JSON файл"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✓ JSON сохранен: {filename}")
        return filename
    except Exception as e:
        print(f"✗ Ошибка сохранения JSON: {e}")
        return None

def save_to_csv(data, filename='cmc_questions_answers.csv'):
    """Сохраняет данные в CSV файл"""
    try:
        if not data:
            print("✗ Нет данных для сохранения в CSV")
            return None

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['question', 'answer', 'length', 'attempt', 'timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        print(f"✓ CSV сохранен: {filename}")
        return filename
    except Exception as e:
        print(f"✗ Ошибка сохранения CSV: {e}")
        return None

def send_all_results_to_telegram(results):
    """Отправляет все результаты в Telegram - каждый вопрос отдельным сообщением"""
    try:
        print("\n📤 Отправка результатов в Telegram...")
        
        # Отправляем каждый вопрос и ответ отдельным сообщением (без стартового сообщения)
        total_questions = len(results)
        for i, result in enumerate(results, 1):
            send_question_answer_to_telegram(
                question_num=i,
                total_questions=total_questions,
                question=result['question'],
                answer=result['answer']
            )
        
        print("✓ Все результаты отправлены в Telegram")
        
    except Exception as e:
        print(f"✗ Ошибка при отправке результатов в Telegram: {e}")

async def main_parser():
    """Главная функция парсера"""
    async with async_playwright() as p:
        try:
            print("🌐 Загрузка страницы...")

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
                    print("✓ Страница загружена")
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"⚠️ Попытка {attempt + 1} не удалась, пробую еще раз...")
                        await asyncio.sleep(3)
                    else:
                        raise

            print("🍪 Проверка cookie-баннера...")
            await accept_cookies(page)

            print("⏳ Ожидание загрузки контента (5 секунд)...")
            await asyncio.sleep(5)

            print("\n🔍 ПОЛУЧЕНИЕ СПИСКА ВОПРОСОВ")

            elements = await page.query_selector_all('div.BaseChip_labelWrapper__pQXPT')

            questions_list = []
            seen = set()

            for elem in elements:
                text = await elem.inner_text()
                text = text.strip()
                if text and text not in seen:
                    questions_list.append(text)
                    seen.add(text)

            print(f"✓ Найдено уникальных вопросов: {len(questions_list)}")
            for i, q in enumerate(questions_list, 1):
                print(f"  {i}. {q}")

            all_results, failed_questions = await parse_all_questions_with_retries(
                page,
                questions_list,
                max_questions=MAX_QUESTIONS,
                max_retries=MAX_RETRIES
            )

            stats = calculate_statistics(all_results)

            print("\n📊 СТАТИСТИКА ПО ДЛИНЕ ОТВЕТОВ")
            print(f"  • Всего ответов: {stats.get('total_answers', 0)}")
            print(f"  • Средняя длина: {stats.get('avg_length', 0)} символов")
            print(f"  • Минимальная: {stats.get('min_length', 0)} символов")
            print(f"  • Максимальная: {stats.get('max_length', 0)} символов")
            print(f"  • Всего символов: {stats.get('total_chars', 0)}")

            # Сохраняем данные локально (для бэкапа)
            export_data = {
                'metadata': {
                    'url': 'https://coinmarketcap.com/cmc-ai/ask/',
                    'parsed_at': datetime.now().isoformat(),
                    'total_questions_found': len(questions_list),
                    'questions_processed': len(all_results),
                    'failed_questions': len(failed_questions),
                    'statistics': stats
                },
                'questions_list': questions_list,
                'all_results': all_results,
                'failed_questions': failed_questions
            }

            json_file = save_to_json(export_data, 'cmc_full_data.json')

            if all_results:
                csv_file = save_to_csv(all_results, 'cmc_questions_answers.csv')

            # Сохраняем полный отчет в текстовый файл
            print("\n📄 СОХРАНЕНИЕ ПОЛНОГО ОТЧЕТА")
            full_report_file = save_full_report_to_file(all_results, 'full_report.txt')

            # Отправляем результаты в Telegram (только TLDR)
            print("\n📤 ОТПРАВКА КРАТКИХ РЕЗУЛЬТАТОВ В TELEGRAM")
            send_all_results_to_telegram(all_results)

            print(f"\n🎯 ИТОГОВАЯ СТАТИСТИКА")
            print(f"  ✓ Найдено вопросов: {len(questions_list)}")
            print(f"  ✓ Успешно обработано: {len(all_results)}")
            print(f"  ✗ Не удалось обработать: {len(failed_questions)}")
            print(f"  📊 Средняя длина ответа: {stats.get('avg_length', 0)} символов")
            print(f"  💾 Сохранено файлов локально: 3 (JSON, CSV, Full Report)")
            print(f"  📱 Отправлено в Telegram: {len(all_results)} кратких сообщений (TLDR)")
            if full_report_file:
                print(f"  📄 Полный отчет: {full_report_file}")

            await browser.close()
            print("✓ Браузер закрыт\n")

        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            traceback.print_exc()
            
            error_message = f"""<b>❌ ОШИБКА ПАРСЕРА</b>
⏰ {datetime.now().strftime("%Y-%m-%d %H:%M")}
<b>Ошибка:</b> <code>{str(e)[:1000]}</code>"""
            send_telegram_message(error_message)

def main():
    """Запуск парсера"""
    print("="*70)
    print("🚀 УЛУЧШЕННЫЙ ПАРСЕР COINMARKETCAP AI")
    print("="*70)
    print("\n📋 ВОЗМОЖНОСТИ:")
    print("  ✅ Обработка всех 8 вопросов")
    print("  ✅ Повторные попытки для пропущенных")
    print("  ✅ Каждый вопрос/ответ отдельным сообщением в Telegram")
    print("  ✅ Без лишних файлов и статистики в чате")
    print(f"\n⚙️  НАСТРОЙКИ:")
    print(f"  • Максимум вопросов: {MAX_QUESTIONS}")
    print(f"  • Повторных попыток: {MAX_RETRIES}")
    print("\n" + "="*70 + "\n")
    
    asyncio.run(main_parser())
    
    print("\n✅ ВСЕ ОПЕРАЦИИ ЗАВЕРШЕНЫ!")
    print("="*70)

if __name__ == "__main__":
    main()
