import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Конфигурация API ключа ---
if os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
else:
    # Замените на ваш фактический ключ API, если не используете .env
    os.environ["GOOGLE_API_KEY"] = "AIzaSyDdupW6JUDwzQ3zWA-Sh8glSL1qVJKjxwM"
    print("Внимание: GOOGLE_API_KEY не найден в .env. Используется ключ, жестко заданный в коде.")

# --- Инициализация LLM (Большой языковой модели) ---
llm = None
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)
    print("LLM инициализирована успешно.")
except Exception as e:
    print(f"Ошибка при инициализации LLM: {e}")
    print("Пожалуйста, убедитесь, что ваш GOOGLE_API_KEY корректен и имеет доступ к Gemini API.")
    print("Возможно, также требуется обновить библиотеки LangChain и Google GenAI.")
    exit()

# --- Чтение всего содержимого файла один раз при запуске ---
# Это самый простой способ "чтения файла", но с серьезными ограничениями по размеру.
full_document_content = ""
document_path = "university_info.txt"

print(f"Попытка чтения всего файла '{document_path}'...")
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


# --- Определение Промпт Шаблона для передачи всего файла ---
# Теперь промпт будет включать весь документ как часть запроса
prompt_template = PromptTemplate.from_template(
    """Ты - полезный AI-помощник. Используй предоставленную ниже информацию для ответа на запрос пользователя.
Если ответ не найден в этой информации, или она не релевантна, сообщи, что у тебя нет нужных данных.
Не придумывай информацию.

Документ:
{document_content}

Категория запроса: {query_type}
Запрос пользователя: {user_query}
Ответ:"""
)

# --- Универсальная функция для обработки различных типов запросов ---
def handle_general_query_simple_file(query_type: str):
    """
    Обрабатывает запросы, передавая все содержимое файла в промпт.
    Args:
        query_type (str): Категория/тип запроса.
    """
    print(f"\n--- Режим: {query_type} ---")
    user_input = input(f"Введите ваш запрос по {query_type.lower()} (или 'выйти в главное меню'): ")
    if user_input.lower() == 'выйти в главное меню':
        return # Возвращаемся в главное меню

    if not user_input.strip():
        print("Запрос не может быть пустым. Пожалуйста, введите что-нибудь.")
        return

    try:
        print("Получение ответа (отправка всего файла в LLM)...")

        # Создаем цепочку: промпт -> LLM
        # Теперь промпт требует {document_content}, {query_type} и {user_query}
        chain = prompt_template | llm

        # Передаем все необходимые переменные в invoke
        response = chain.invoke({
            "document_content": full_document_content,
            "query_type": query_type,
            "user_query": user_input
        })
        response_content = response.content

        if not response_content.strip():
            print("\n--- AI Ответ (нет информации) ---")
            print("Извините, я не нашел достаточной информации по вашему запросу в предоставленных данных.")
        else:
            print(f"\n--- AI Ответ по {query_type.lower()} ---")
            print(response_content)
        print("-----------------------------\n")

    except Exception as e:
        print(f"Произошла ошибка при получении информации по {query_type.lower()}: {e}")
        print("Пожалуйста, проверьте подключение к интернету и ключ API.")
        if "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
            print("Возможно, исчерпан лимит запросов к API Gemini. Попробуйте позже или проверьте свою квоту.")
        elif "authentication" in str(e).lower() or "api key" in str(e).lower():
            print("Ошибка аутентификации. Проверьте правильность вашего GOOGLE_API_KEY.")
        elif "deadline exceeded" in str(e).lower() or "timeout" in str(e).lower():
            print("Запрос к API Gemini превысил время ожидания. Проверьте ваше интернет-соединение.")
        elif "content" in str(e).lower() and "size" in str(e).lower(): # Ошибка, связанная с превышением лимита токенов
             print("Ошибка: Превышен лимит токенов для запроса. Ваш файл слишком большой для этого метода.")


# --- Основной цикл CLI приложения ---
def run_cli_app():
    """
    Запускает интерфейс командной строки с опциями меню.
    """
    while True:
        print("\n--- Главное Меню ---")
        print("1. Расписание консультаций")
        print("2. Навигация по кампусу")
        print("3. Рекомендация элективных курсов")
        print("4. Консультации по учебным программам")
        print("5. Административные вопросы")
        print("Введите 'exit' для выхода")

        choice = input("Выберите опцию (1, 2, 3, 4, 5 или 'exit'): ").strip().lower()

        if choice == 'exit':
            print("Выход из приложения. До свидания!")
            break
        elif choice == '1':
            handle_general_query_simple_file("Расписание консультаций")
        elif choice == '2':
            handle_general_query_simple_file("Навигация по кампусу")
        elif choice == '3':
            handle_general_query_simple_file("Рекомендация элективных курсов")
        elif choice == '4':
            handle_general_query_simple_file("Консультации по учебным программам")
        elif choice == '5':
            handle_general_query_simple_file("Административные вопросы")
        else:
            print("Неверный выбор. Пожалуйста, введите '1', '2', '3', '4', '5' или 'exit'.")

if __name__ == "__main__":
    run_cli_app()