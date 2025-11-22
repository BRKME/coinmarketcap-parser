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
                print(f"Ответ: {response.text}")
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
        traceback.print_exc()
        return False

def extract_tldr_from_answer(answer):
    """Извлекает только TLDR часть из ответа и очищает от лишнего текста"""
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
            
            # Убираем саму строку "TLDR" из начала
            tldr_section = tldr_section.replace('TLDR', '', 1).strip()
            
            return tldr_section
        else:
            # Если нет TLDR, возвращаем первые 500 символов
            return answer[:500] + "..."
            
    except Exception as e:
        print(f"⚠️ Ошибка извлечения TLDR: {e}")
        return answer[:500] + "..."

def clean_question_specific_text(question, text):
    """Убирает специфичные для вопросов ненужные строки"""
    try:
        # Для вопроса про upcoming events
        if "What upcoming events may impact crypto?" in question:
            text = text.replace("These are the upcoming crypto events that may impact crypto the most:", "").strip()
        
        # Для вопроса про bullish momentum
        if "What cryptos are showing bullish momentum?" in question:
            text = text.replace("Here are the trending cryptos based on CoinMarketCap's evolving momentum algorithm (news, social, price momentum)", "").strip()
        
        # Для вопроса про trending narratives
        if "What are the trending narratives?" in question:
            text = text.replace("Here are the trending narratives based on CoinMarketCap's evolving narrative algorithm (price, news, social momentum):", "").strip()
        
        return text
    except Exception as e:
        print(f"⚠️ Ошибка очистки текста: {e}")
        return text

def send_question_answer_to_telegram(question_num, total_questions, question, answer):
    """Отправляет вопрос и TLDR в Telegram"""
    try:
        # Извлекаем только TLDR часть
        tldr_text = extract_tldr_from_answer(answer)
        
        # Очищаем от специфичных для вопросов строк
        tldr_text = clean_question_specific_text(question, tldr_text)
        
        # Форматируем короткое сообщение без разделительной линии
        short_message = f"""<b>{question}</b>

{tldr_text}"""
        
        print(f"\n📤 Отправка вопроса {question_num}/{total_questions} в Telegram...")
        print(f"📏 Длина текста: {len(tldr_text)} символов")
        
        # Отправляем просто текст
        send_telegram_message(short_message)
        
        # Пауза между сообщениями
        time.sleep(2)
        
    except Exception as e:
        print(f"✗ Ошибка при отправке вопроса {question_num}: {e}")
        traceback.print_exc()

def send_all_results_to_telegram(results):
    """Отправляет все результаты в Telegram - каждый вопрос отдельным сообщением"""
    try:
        print("\n📤 Отправка результатов в Telegram...")
        
        # Отправляем каждый вопрос и ответ отдельным сообщением
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
        traceback.print_exc()
