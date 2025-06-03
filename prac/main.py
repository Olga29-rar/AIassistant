import os
import sqlite3
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Конфигурация API ключа ---
if os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
else:
    os.environ["GOOGLE_API_KEY"] = "AIzaSyDdupW6JUDwzQ3zWA-Sh8glSL1qVJKjxwM"
    print("Внимание: GOOGLE_API_KEY не найден в .env. Используется ключ, жестко заданный в коде.")

# --- Инициализация LLM ---
llm = None
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)
    print("LLM инициализирована успешно.")
except Exception as e:
    print(f"Ошибка при инициализации LLM: {e}")
    print("Пожалуйста, убедитесь, что ваш GOOGLE_API_KEY корректен и имеет доступ к Gemini API.")
    print("Возможно, также требуется обновить библиотеки LangChain и Google GenAI.")
    exit()

def extract_text_from_sqlite(db_path):
    """
    Извлекает все текстовые данные из всех таблиц базы данных SQLite.
    """
    if not os.path.exists(db_path):
        print(f"База данных {db_path} не найдена.")
        return ""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        text_data = []
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            # Получаем имена столбцов
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            # Выбираем только текстовые столбцы
            cursor.execute(f"SELECT * FROM {table};")
            for row in cursor.fetchall():
                for idx, value in enumerate(row):
                    if isinstance(value, str):
                        text_data.append(f"{table}.{columns[idx]}: {value}")
        conn.close()
        return "\n".join(text_data)
    except Exception as e:
        print(f"Ошибка при чтении базы данных: {e}")
        return ""

# --- Чтение содержимого базы данных или текстового файла ---
full_document_content = ""
db_path = "tou_data.db"
document_path = "university_info.txt"

# Сначала пробуем базу данных
print(f"Попытка чтения базы данных '{db_path}'...")
full_document_content = extract_text_from_sqlite(db_path)
if full_document_content:
    print(f"Содержимое базы данных '{db_path}' успешно загружено ({len(full_document_content)} символов).")
else:
    print(f"База данных '{db_path}' пуста или не содержит текстовой информации. Пробуем загрузить '{document_path}'...")
    try:
        if not os.path.exists(document_path):
            raise FileNotFoundError(f"Файл '{document_path}' не найден. Убедитесь, что он находится в том же каталоге.")

        try:
            with open(document_path, "r", encoding="utf-8") as f:
                full_document_content = f.read()
        except UnicodeDecodeError:
            print(f"Ошибка кодировки UTF-8. Попытка чтения файла '{document_path}' с кодировкой 'cp1251'.")
            with open(document_path, "r", encoding="cp1251") as f:
                full_document_content = f.read()

        if not full_document_content.strip():
            raise ValueError(f"Файл '{document_path}' пуст или не содержит читаемого текста.")

        print(f"Содержимое файла '{document_path}' успешно загружено ({len(full_document_content)} символов).")
        print("Внимание: Весь документ будет отправляться с каждым запросом. Это может быть неэффективно и ограничено размером промпта LLM.")

    except FileNotFoundError as e:
        print(f"Критическая ошибка: {e}")
        print("Пожалуйста, создайте файл 'university_info.txt' в папке проекта и добавьте в него информацию.")
        exit()
    except ValueError as e:
        print(f"Критическая ошибка обработки файла: {e}")
        print("Убедитесь, что файл не пуст и содержит осмысленный текст.")
        exit()
    except Exception as e:
        print(f"Непредвиденная ошибка при чтении файла '{document_path}': {e}")
        print("Пожалуйста, проверьте разрешения на файл и его целостность.")
        exit()

# --- Промпт для универсального ассистента ---
prompt_template = PromptTemplate.from_template(
    """Ты — современный AI-ассистент университета, обладающий широкими знаниями и доступом к базе данных университета tou_data.db (см. ниже).
Вся необходимая информация по университету, учебе, расписанию, административным вопросам и студенческой жизни содержится в базе данных tou_data.db. 
Перед тем как отвечать, обязательно ищи и анализируй информацию именно из этой базы данных. Если ответ найден — процитируй или перефразируй его. Только если информации нет вообще, используй свои знания.
tou_data.db — это основной и достоверный источник истины для университетских вопросов.

Данные из базы tou_data.db:
{document_content}

Вопрос пользователя: {user_query}
Ответ:"""
)

def handle_user_query():
    """
    Универсальный ассистент: принимает любой вопрос, ищет ответ по всей базе.
    """
    while True:
        user_input = input("\nВведите ваш вопрос (или 'exit' для выхода): ").strip()
        if user_input.lower() == 'exit':
            print("Выход из приложения. До свидания!")
            break
        if not user_input:
            print("Вопрос не может быть пустым. Пожалуйста, введите что-нибудь.")
            continue

        try:
            print("Получение ответа от AI...")
            chain = prompt_template | llm
            response = chain.invoke({
                "document_content": full_document_content,
                "user_query": user_input
            })
            response_content = response.content

            if not response_content.strip():
                print("\n--- AI Ответ (нет информации) ---")
                print("Извините, я не нашёл информации по вашему вопросу в предоставленных данных.")
            else:
                print(f"\n--- AI Ответ ---")
                print(response_content)
            print("-----------------------------\n")

        except Exception as e:
            print(f"Произошла ошибка при получении ответа: {e}")
            print("Проверьте подключение к интернету и ключ API.")
            if "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
                print("Возможно, исчерпан лимит запросов к API Gemini. Попробуйте позже или проверьте свою квоту.")
            elif "authentication" in str(e).lower() or "api key" in str(e).lower():
                print("Ошибка аутентификации. Проверьте правильность вашего GOOGLE_API_KEY.")
            elif "deadline exceeded" in str(e).lower() or "timeout" in str(e).lower():
                print("Запрос к API Gemini превысил время ожидания. Проверьте ваше интернет-соединение.")
            elif "content" in str(e).lower() and "size" in str(e).lower():
                print("Ошибка: Превышен лимит токенов для запроса. Ваш файл слишком большой для этого метода.")

if __name__ == "__main__":
    handle_user_query()