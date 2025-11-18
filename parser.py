"""
Парсер для CoinMarketCap AI - РАСШИРЕННАЯ ВЕРСИЯ
✅ Обработка всех 8 вопросов
✅ Повторные попытки для пропущенных
✅ Выгрузка в Google Sheets
✅ Статистика по длине ответов
✅ Отправка результатов в Telegram
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

# Глобальные настройки
MAX_QUESTIONS = 8  # Обрабатываем все вопросы
MAX_RETRIES = 2    # Повторные попытки для каждого вопроса

# Telegram настройки
TELEGRAM_BOT_TOKEN = "8323539910:AAG6DYij-FuqT7q-ovsBNNgEnWH2V6FXhoM"
TELEGRAM_CHAT_ID = "@Ready777_bot"  # Если это канал, используйте @channelname

def send_telegram_message(message, parse_mode='HTML'):
    """Отправляет сообщение в Telegram"""
    try:
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
            print(f"✗ Ошибка отправки в Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Ошибка при отправке в Telegram: {e}")
        return False

def send_telegram_document(document_path, caption=""):
    """Отправляет документ в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(document_path, 'rb') as file:
            files = {'document': file}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption
            }
            response = requests.post(url, files=files, data=data, timeout=30)
        if response.status_code == 200:
            print(f"✓ Документ {document_path} отправлен в Telegram")
            return True
        else:
            print(f"✗ Ошибка отправки документа: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Ошибка при отправке документа в Telegram: {e}")
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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

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
    """
    Парсит все вопросы с повторными попытками для пропущенных
    """
    results = []
    failed_questions = []

    print("\n" + "="*70)
    print(f"📝 СБОР ОТВЕТОВ НА ВОПРОСЫ ({min(max_questions, len(questions_list))} вопросов)")
    print("="*70)

    # Первый проход - обрабатываем все вопросы
    for i, question in enumerate(questions_list[:max_questions], 1):
        print(f"\n[{i}/{min(max_questions, len(questions_list))}] Обработка вопроса...")

        result = await click_and_get_response(page, question, attempt_num=1)

        if result:
            results.append(result)
            print(f"✓ Успешно обработан")

            preview = result['answer'][:300] + "..." if len(result['answer']) > 300 else result['answer']
            print(f"\n💬 Превью ответа:\n{preview}\n")
        else:
            print(f"✗ Не удалось получить ответ, добавляю в список повторов")
            failed_questions.append(question)

        if i < min(max_questions, len(questions_list)):
            print("⏱️  Возврат к списку вопросов...")
            await reset_to_question_list(page)
            await asyncio.sleep(2)

    # Повторные попытки для пропущенных вопросов
    if failed_questions and max_retries > 0:
        print("\n" + "="*70)
        print(f"🔄 ПОВТОРНЫЕ ПОПЫТКИ ({len(failed_questions)} вопросов)")
        print("="*70)

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

    # Финальная статистика
    print("\n" + "="*70)
    print("📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ")
    print("="*70)
    print(f"  ✅ Успешно обработано: {len(results)}/{min(max_questions, len(questions_list))}")
    print(f"  ❌ Не удалось обработать: {len(failed_questions)}")

    if failed_questions:
        print(f"\n  Пропущенные вопросы:")
        for q in failed_questions:
            print(f"    • {q}")

    print("="*70 + "\n")

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

def upload_to_google_sheets(data, sheet_name='CoinMarketCap AI Parser'):
    """
    Выгружает данные в Google Sheets
    """
    try:
        print("\n📤 Выгрузка в Google Sheets...")
        
        # Для GitHub Actions нужно использовать Service Account
        # Создайте файл credentials.json с данными сервисного аккаунта
        if os.path.exists('credentials.json'):
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            gc = gspread.authorize(creds)
            
            # Создаем или открываем таблицу
            try:
                spreadsheet = gc.open(sheet_name)
                print(f"✓ Открыта существующая таблица: {sheet_name}")
            except:
                spreadsheet = gc.create(sheet_name)
                print(f"✓ Создана новая таблица: {sheet_name}")

            # Создаем новый лист с timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            worksheet = spreadsheet.add_worksheet(title=f"Parse {timestamp}", rows=100, cols=10)

            # Подготавливаем данные
            headers = ['#', 'Вопрос', 'Ответ', 'Длина ответа', 'Попытка', 'Время']
            rows = [headers]

            for i, item in enumerate(data, 1):
                rows.append([
                    i,
                    item['question'],
                    item['answer'],
                    item['length'],
                    item.get('attempt', 1),
                    item['timestamp']
                ])

            # Добавляем пустую строку и статистику
            stats = calculate_statistics(data)
            rows.append([])
            rows.append(['СТАТИСТИКА', '', '', '', '', ''])
            rows.append(['Всего ответов', stats.get('total_answers', 0), '', '', '', ''])
            rows.append(['Средняя длина', stats.get('avg_length', 0), '', '', '', ''])
            rows.append(['Мин. длина', stats.get('min_length', 0), '', '', '', ''])
            rows.append(['Макс. длина', stats.get('max_length', 0), '', '', '', ''])
            rows.append(['Всего символов', stats.get('total_chars', 0), '', '', '', ''])

            # Записываем данные
            worksheet.update('A1', rows)

            # Форматирование
            worksheet.format('A1:F1', {
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.86},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })

            # Авторазмер колонок
            worksheet.columns_auto_resize(0, 5)

            # Получаем ссылку
            sheet_url = spreadsheet.url

            print(f"✓ Данные успешно выгружены в Google Sheets!")
            print(f"📊 Ссылка на таблицу: {sheet_url}")
            print(f"📄 Лист: {worksheet.title}")

            return sheet_url
        else:
            print("⚠️ Файл credentials.json не найден, пропускаем выгрузку в Google Sheets")
            return None

    except Exception as e:
        print(f"✗ Ошибка при выгрузке в Google Sheets: {e}")
        traceback.print_exc()
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

def send_results_to_telegram(results, failed_questions, stats, sheet_url=None):
    """Отправляет итоговые результаты в Telegram"""
    try:
        print("\n📤 Отправка результатов в Telegram...")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Основное сообщение со статистикой
        message = f"""
<b>🚀 ПАРСИНГ COINMARKETCAP AI ЗАВЕРШЕН</b>
<b>⏰ Время:</b> {timestamp}
        
<b>📊 СТАТИСТИКА:</b>
✅ Успешно обработано: <b>{stats.get('total_answers', 0)}</b>
❌ Не удалось: <b>{len(failed_questions)}</b>
📏 Средняя длина ответа: <b>{stats.get('avg_length', 0)}</b> символов
📈 Максимальная длина: <b>{stats.get('max_length', 0)}</b> символов
📉 Минимальная длина: <b>{stats.get('min_length', 0)}</b> символов
🔤 Всего символов: <b>{stats.get('total_chars', 0)}</b>
        
<b>📋 ОБРАБОТАННЫЕ ВОПРОСЫ:</b>
"""
        
        # Добавляем список обработанных вопросов
        for i, result in enumerate(results[:5], 1):  # Первые 5 вопросов
            message += f"{i}. {result['question']} ({result['length']} символов)\n"
        
        if len(results) > 5:
            message += f"... и еще {len(results) - 5} вопросов\n"
        
        # Добавляем информацию о Google Sheets
        if sheet_url:
            message += f"\n<b>📊 GOOGLE SHEETS:</b>\n{sheet_url}"
        
        # Отправляем основное сообщение
        send_telegram_message(message)
        
        # Отправляем пример ответа (первый успешный)
        if results:
            first_result = results[0]
            example_message = f"""
<b>📝 ПРИМЕР ОТВЕТА:</b>
<b>Вопрос:</b> {first_result['question']}
<b>Длина:</b> {first_result['length']} символов
<b>Попытка:</b> {first_result.get('attempt', 1)}

<code>{first_result['answer'][:1000]}...</code>
"""
            send_telegram_message(example_message)
        
        print("✓ Результаты отправлены в Telegram")
        
    except Exception as e:
        print(f"✗ Ошибка при отправке результатов в Telegram: {e}")

async def main_parser():
    """Главная функция парсера"""
    async with async_playwright() as p:
        try:
            print("🌐 Загрузка страницы...")

            # Установка браузера для GitHub Actions
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

            # Отправляем стартовое сообщение в Telegram
            start_message = f"""
<b>🚀 ЗАПУСК ПАРСЕРА COINMARKETCAP AI</b>
<b>⏰ Время начала:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
<b>⚙️ Настройки:</b>
• Максимум вопросов: {MAX_QUESTIONS}
• Повторных попыток: {MAX_RETRIES}

Ожидайте результаты...
"""
            send_telegram_message(start_message)

            # Переходим на страницу с retry
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

            # Получаем список вопросов
            print("\n" + "="*70)
            print("🔍 ПОЛУЧЕНИЕ СПИСКА ВОПРОСОВ")
            print("="*70 + "\n")

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

            # Парсим все вопросы с повторными попытками
            all_results, failed_questions = await parse_all_questions_with_retries(
                page,
                questions_list,
                max_questions=MAX_QUESTIONS,
                max_retries=MAX_RETRIES
            )

            # Вычисляем статистику
            stats = calculate_statistics(all_results)

            print("\n" + "="*70)
            print("📊 СТАТИСТИКА ПО ДЛИНЕ ОТВЕТОВ")
            print("="*70)
            print(f"  • Всего ответов: {stats.get('total_answers', 0)}")
            print(f"  • Средняя длина: {stats.get('avg_length', 0)} символов")
            print(f"  • Минимальная: {stats.get('min_length', 0)} символов")
            print(f"  • Максимальная: {stats.get('max_length', 0)} символов")
            print(f"  • Всего символов: {stats.get('total_chars', 0)}")
            print("="*70 + "\n")

            # === СОХРАНЕНИЕ ДАННЫХ ===
            print("\n" + "="*70)
            print("💾 СОХРАНЕНИЕ ДАННЫХ")
            print("="*70 + "\n")

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

            # Сохраняем JSON
            json_file = save_to_json(export_data, 'cmc_full_data.json')

            # Сохраняем CSV
            csv_file = None
            if all_results:
                csv_file = save_to_csv(all_results, 'cmc_questions_answers.csv')

            # Выгружаем в Google Sheets
            sheet_url = None
            if all_results:
                sheet_url = upload_to_google_sheets(all_results, 'CoinMarketCap AI Parser')

            # Скриншот
            print("\n📸 Сохранение финального скриншота...")
            screenshot_file = 'screenshot_final.png'
            await page.screenshot(path=screenshot_file, full_page=True)
            print("✓ Скриншот сохранен: screenshot_final.png")

            # === ОТПРАВКА В TELEGRAM ===
            print("\n" + "="*70)
            print("📤 ОТПРАВКА РЕЗУЛЬТАТОВ В TELEGRAM")
            print("="*70 + "\n")

            # Отправляем итоговые результаты
            send_results_to_telegram(all_results, failed_questions, stats, sheet_url)

            # Отправляем файлы
            if json_file:
                send_telegram_document(json_file, "📄 Полные данные в JSON")
            
            if csv_file:
                send_telegram_document(csv_file, "📊 Вопросы и ответы в CSV")
            
            send_telegram_document(screenshot_file, "🖼️ Финальный скриншот")

            # Итоговая статистика
            print("\n" + "="*70)
            print("🎯 ИТОГОВАЯ СТАТИСТИКА")
            print("="*70)
            print(f"  ✓ Найдено вопросов: {len(questions_list)}")
            print(f"  ✓ Успешно обработано: {len(all_results)}")
            print(f"  ✗ Не удалось обработать: {len(failed_questions)}")
            print(f"  📊 Средняя длина ответа: {stats.get('avg_length', 0)} символов")
            print(f"  💾 Сохранено файлов: 3 (JSON, CSV, Screenshot)")
            if sheet_url:
                print(f"  📊 Google Sheets: Обновлено")
            print(f"  📱 Отправлено в Telegram: 3 файла + статистика")
            print("="*70 + "\n")

            await browser.close()
            print("✓ Браузер закрыт\n")

        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            traceback.print_exc()
            
            # Отправляем сообщение об ошибке в Telegram
            error_message = f"""
<b>❌ ОШИБКА ПАРСЕРА</b>
<b>⏰ Время:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
<b>Ошибка:</b> <code>{str(e)[:1000]}</code>
"""
            send_telegram_message(error_message)

def main():
    """Запуск парсера"""
    print("="*70)
    print("🚀 РАСШИРЕННЫЙ ПАРСЕР COINMARKETCAP AI")
    print("="*70)
    print("\n📋 ВОЗМОЖНОСТИ:")
    print("  ✅ Обработка всех 8 вопросов")
    print("  ✅ Повторные попытки для пропущенных")
    print("  ✅ Выгрузка в Google Sheets")
    print("  ✅ Статистика по длине ответов")
    print("  ✅ Отправка результатов в Telegram")
    print(f"\n⚙️  НАСТРОЙКИ:")
    print(f"  • Максимум вопросов: {MAX_QUESTIONS}")
    print(f"  • Повторных попыток: {MAX_RETRIES}")
    print(f"  • Telegram бот: @Ready777_bot")
    print("\n" + "="*70 + "\n")
    
    # Запуск асинхронной функции
    asyncio.run(main_parser())
    
    print("\n✅ ВСЕ ОПЕРАЦИИ ЗАВЕРШЕНЫ!")
    print("="*70)

if __name__ == "__main__":
    main()
