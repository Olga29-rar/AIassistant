import os
import sqlite3
import asyncio
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
import sys
import threading
from functools import lru_cache
from typing import Optional, Dict, Tuple, Any
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
import logging
import re

# Оптимизированная настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("tougpt.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("tougpt")

# Загружаем переменные окружения
load_dotenv()

# Пути к файлам с знаниями
KNOWLEDGE_TXT = os.path.join(os.path.dirname(__file__), '..', 'knowledge', 'university_info.txt')
KNOWLEDGE_DB = os.path.join(os.path.dirname(__file__), '..', 'knowledge', 'tou_data.db')

# Оптимизированный пул потоков для AI запросов с ограничением
executor = ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 4))

# Функция предварительной обработки запросов для улучшения точности ответов
def preprocess_query(query: str) -> str:
    """Предобработка запроса для улучшения релевантности ответа."""
    # Нормализация пробелов и приведение к нижнему регистру
    query = re.sub(r'\s+', ' ', query.strip().lower())
    
    # Удаление общих фраз вежливости для лучшего выделения смысла вопроса
    query = re.sub(r'^(привет|здравствуйте|доброе утро|добрый день|добрый вечер|пожалуйста|скажи|расскажи|покажи|подскажи|помоги|дай информацию о)[,\s]+', '', query)
    
    # Удаление часто встречающихся незначимых слов
    query = re.sub(r'\b(мне|немного|очень|кратко|подробно|пожалуйста|чуть-чуть|просто)\b', '', query)
    
    # Нормализация запросов о расположении
    if re.search(r'где|как найти|как попасть|расположен|находится', query):
        query = f"местоположение {query}"
    
    # Нормализация запросов о времени работы
    if re.search(r'когда|часы работы|время работы|график работы|режим работы|открыто|закрыто', query):
        query = f"время работы {query}"
        
    return query.strip()

def ensure_knowledge_file():
    """Проверка существования файла с базой знаний, создание пустого файла если он отсутствует."""
    knowledge_dir = os.path.dirname(KNOWLEDGE_TXT)
    if not os.path.isdir(knowledge_dir):
        os.makedirs(knowledge_dir, exist_ok=True)
    if not os.path.exists(KNOWLEDGE_TXT):
        with open(KNOWLEDGE_TXT, "w", encoding="utf-8") as f:
            f.write("# База знаний университета Торайгыров\n\n=== Основная информация ===\nНазвание университета: Торайгыров университет\nРектор: Ерлан Амантайулы\n")
        logger.info(f"Создан пустой файл базы знаний: {KNOWLEDGE_TXT}")

ensure_knowledge_file()

def extract_text_from_sqlite(db_path: str) -> str:
    """Извлекает текстовую информацию из базы данных SQLite с оптимизацией для больших таблиц."""
    if not os.path.exists(db_path):
        return ""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        text_data = []
        
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Ограничиваем количество извлекаемых строк и размер текста
        MAX_ROWS_PER_TABLE = 50
        MAX_TEXT_LENGTH = 300
        
        for table in tables:
            # Получаем информацию о столбцах
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Извлекаем данные с ограничением количества строк
            cursor.execute(f"SELECT * FROM {table} LIMIT {MAX_ROWS_PER_TABLE};")
            rows = cursor.fetchall()
            
            # Добавляем метаданные таблицы
            text_data.append(f"=== Таблица: {table} ===")
            
            # Обрабатываем строки и столбцы
            for row in rows:
                row_data = []
                for idx, value in enumerate(row):
                    if isinstance(value, str) and value.strip():
                        # Ограничиваем длину текста
                        trimmed_value = value[:MAX_TEXT_LENGTH]
                        if len(value) > MAX_TEXT_LENGTH:
                            trimmed_value += "..."
                        row_data.append(f"{columns[idx]}: {trimmed_value}")
                
                if row_data:  # Добавляем только если есть значимые данные
                    text_data.append(" | ".join(row_data))
        
        conn.close()
        
        # Ограничиваем общий объем данных, если он слишком большой
        combined_text = "\n".join(text_data)
        MAX_TOTAL_LENGTH = 15000
        if len(combined_text) > MAX_TOTAL_LENGTH:
            combined_text = combined_text[:MAX_TOTAL_LENGTH] + "\n... (содержимое сокращено для оптимизации)"
            
        return combined_text
    except Exception as e:
        logger.error(f"Ошибка извлечения данных из SQLite: {e}")
        return ""

class OptimizedKnowledgeCache:
    """Оптимизированный кеш для базы знаний с отслеживанием изменений файлов."""
    
    def __init__(self, txt_path: str, db_path: str):
        self.txt_path = txt_path
        self.db_path = db_path
        self._content = ""
        self._content_hash = ""
        self._last_mtime = 0
        self._lock = threading.Lock()
        self._section_index = {}  # Индекс для быстрого доступа к разделам
        self._update_cache()
    
    def _get_latest_mtime(self) -> float:
        """Возвращает последнее время модификации файлов базы знаний."""
        mtimes = []
        if os.path.exists(self.txt_path):
            mtimes.append(os.path.getmtime(self.txt_path))
        if os.path.exists(self.db_path):
            mtimes.append(os.path.getmtime(self.db_path))
        return max(mtimes) if mtimes else 0
    
    def _build_section_index(self, content: str) -> Dict[str, str]:
        """Строит индекс разделов для быстрого поиска по ключевым словам."""
        section_pattern = re.compile(r'===\s+(.*?)\s+===')
        sections = section_pattern.findall(content)
        
        index = {}
        for section in sections:
            keywords = set(re.findall(r'\b\w+\b', section.lower()))
            for keyword in keywords:
                if len(keyword) > 3:  # Игнорируем слишком короткие слова
                    if keyword not in index:
                        index[keyword] = []
                    index[keyword].append(section)
        
        return index
    
    def _update_cache(self) -> None:
        """Обновляет кеш базы знаний если исходные файлы были изменены."""
        with self._lock:
            mtime = self._get_latest_mtime()
            if mtime == self._last_mtime and self._content:
                return

            start_time = time.time()
            
            # Получаем содержимое из БД
            content = extract_text_from_sqlite(self.db_path)
            
            # Если нет данных из БД или БД не существует, читаем из текстового файла
            if not content and os.path.exists(self.txt_path):
                try:
                    with open(self.txt_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(self.txt_path, "r", encoding="cp1251") as f:
                        content = f.read()
            
            # Строим индекс разделов
            self._section_index = self._build_section_index(content)

            # Ограничиваем размер контента для оптимизации
            if len(content) > 20000:
                content = content[:20000] + "\n\n... (содержимое сокращено для оптимизации)"

            self._content = content
            self._content_hash = hashlib.md5(content.encode()).hexdigest()
            self._last_mtime = mtime

            load_time = time.time() - start_time
            logger.info(f"Кеш базы знаний обновлен за {load_time:.2f}с, размер: {len(content)} символов")
    
    def get_relevant_sections(self, query: str) -> str:
        """Извлекает релевантные разделы знаний по запросу."""
        self._update_cache()
        if not self._content:
            return ""
            
        # Извлекаем ключевые слова из запроса
        keywords = set(re.findall(r'\b\w+\b', query.lower()))
        relevant_sections = set()
        
        # Находим релевантные разделы по ключевым словам
        for keyword in keywords:
            if len(keyword) > 3 and keyword in self._section_index:
                relevant_sections.update(self._section_index[keyword])
        
        # Если не нашли релевантных разделов, возвращаем весь контент
        if not relevant_sections:
            return self._content
            
        # Извлекаем контент релевантных разделов
        result = []
        for section in relevant_sections:
            pattern = re.compile(f'===\\s+{re.escape(section)}\\s+===.*?(?====\\s+|$)', re.DOTALL)
            matches = pattern.findall(self._content)
            result.extend(matches)
        
        # Если извлечение по паттерну не дало результатов, возвращаем весь контент
        if not result:
            return self._content
            
        return "\n\n".join(result)
    
    def get(self) -> Tuple[str, str]:
        """Возвращает полное содержимое базы знаний и его хеш."""
        self._update_cache()
        return self._content, self._content_hash


# Инициализируем кеш базы знаний
knowledge_cache = OptimizedKnowledgeCache(KNOWLEDGE_TXT, KNOWLEDGE_DB)

# Оптимизированный промпт с инструкциями для более точных ответов
PROMPT = """
Ты — AI-ассистент университета Торайгырова. Твоя задача - предоставлять точную информацию на основе базы знаний университета.

Рекомендации для ответов:
1. Отвечай точно на основе предоставленных данных.
2. Если информации недостаточно, честно признай это.
3. Будь лаконичным, но информативным.
4. Используй маркированные списки для перечислений.
5. Форматируй ответ для удобства чтения.

База знаний:
{document_content}

Вопрос: {user_query}

Ответ:
"""

class OptimizedLLMManager:
    """Менеджер для работы с LLM-моделями с оптимизацией и кешированием."""
    
    def __init__(self):
        self.default_api_key = os.getenv("GOOGLE_API_KEY")
        self._llm_cache = {}
        self._lock = threading.Lock()

        if self.default_api_key:
            self._create_llm(self.default_api_key)
    
    def _create_llm(self, api_key: str) -> Any:
        """Создание экземпляра LLM с оптимизированными параметрами."""
        # Пробуем сначала использовать более быструю модель
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.1,
                max_tokens=1000,
                google_api_key=api_key,
                request_timeout=30,
                top_p=0.95,        # Параметр top_p для управления разнообразием
                top_k=40,          # Параметр top_k для управления разнообразием
            )
            return llm
        except Exception as e:
            logger.warning(f"Не удалось создать экземпляр gemini-1.5-flash: {e}, пробую резервную модель")
            
            # Если не удалось создать flash модель, используем pro модель
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-pro",
                temperature=0.2,
                max_tokens=1000,
                google_api_key=api_key,
                request_timeout=45,
            )
            return llm

    def get_llm(self, api_key: Optional[str] = None) -> Any:
        """Получение LLM с кэшированием по API-ключу."""
        key = api_key or self.default_api_key
        if not key:
            raise ValueError("API ключ не предоставлен")

        with self._lock:
            if key not in self._llm_cache:
                self._llm_cache[key] = self._create_llm(key)
            return self._llm_cache[key]


# Инициализируем менеджер LLM
llm_manager = OptimizedLLMManager()

# Кэш для ответов с TTL и ограничением размера
response_cache: Dict[str, Tuple[str, float]] = {}
CACHE_TTL = 300  # 5 минут
MAX_CACHE_SIZE = 200  # Максимальное количество элементов в кеше

def get_cache_key(query: str, content_hash: str) -> str:
    """Генерация ключа для кеша."""
    # Нормализуем запрос для лучшего совпадения кеша
    normalized_query = re.sub(r'\s+', ' ', query.lower().strip())
    return hashlib.md5(f"{normalized_query}:{content_hash}".encode()).hexdigest()

def is_cache_valid(timestamp: float) -> bool:
    """Проверка валидности кеша по времени."""
    return time.time() - timestamp < CACHE_TTL

def cleanup_cache() -> None:
    """Очистка устаревших записей кеша."""
    global response_cache
    current_time = time.time()
    # Удаляем устаревшие записи
    expired_keys = [k for k, (_, ts) in response_cache.items() if current_time - ts > CACHE_TTL]
    for k in expired_keys:
        del response_cache[k]
    
    # Если кеш всё ещё слишком большой, удаляем самые старые записи
    if len(response_cache) > MAX_CACHE_SIZE:
        # Сортируем по времени создания (от старых к новым)
        sorted_items = sorted(response_cache.items(), key=lambda x: x[1][1])
        # Определяем количество элементов для удаления
        to_remove = len(response_cache) - MAX_CACHE_SIZE
        # Удаляем самые старые элементы
        for i in range(to_remove):
            del response_cache[sorted_items[i][0]]

def cached_ai_answer(document_content: str, content_hash: str, user_query: str, api_key: Optional[str] = None) -> str:
    """Получение ответа AI с кешированием для повторяющихся запросов."""
    # Предобработка запроса
    processed_query = preprocess_query(user_query)
    cache_key = get_cache_key(processed_query, content_hash)

    # Проверяем кеш
    if cache_key in response_cache:
        cached_response, timestamp = response_cache[cache_key]
        if is_cache_valid(timestamp):
            logger.info(f"Найден кеш для запроса: {user_query[:50]}...")
            return cached_response

    # Генерируем новый ответ
    start_time = time.time()
    
    try:
        llm = llm_manager.get_llm(api_key)
        
        # Формируем промпт с релевантным контентом
        prompt = PROMPT.format(document_content=document_content, user_query=user_query)
        
        # Получаем ответ от модели
        response = llm.invoke(prompt)
        content = response.content.strip() if hasattr(response, "content") else str(response).strip()
        
        # Проверяем на пустые или слишком короткие ответы
        if not content or len(content) < 10:
            content = "Извините, я не смог сформировать ответ на основе имеющейся информации."
            
        # Сохраняем в кеш
        response_cache[cache_key] = (content, time.time())
        
        # Очищаем старые записи из кеша
        cleanup_cache()
        
        response_time = time.time() - start_time
        logger.info(f"Ответ AI сгенерирован за {response_time:.2f}с для запроса: {user_query[:50]}...")
        
        return content
    except Exception as e:
        logger.error(f"Ошибка генерации ответа AI: {str(e)}")
        return f"Произошла ошибка при обработке вашего запроса: {str(e)}"


async def get_ai_answer_async(user_query: str, api_key: Optional[str] = None) -> str:
    """Асинхронная обработка AI запроса с оптимизацией производительности."""
    # Получаем базу знаний и ее хеш
    full_content, content_hash = knowledge_cache.get()
    
    # Получаем только релевантные разделы для запроса
    relevant_content = knowledge_cache.get_relevant_sections(user_query)
    content_to_use = relevant_content or full_content
    
    if not content_to_use or not content_to_use.strip():
        return "База знаний пуста или не загружена. Обратитесь к администратору."

    try:
        # Выполняем AI запрос в отдельном потоке для неблокирующей работы
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            cached_ai_answer,
            content_to_use,
            content_hash,
            user_query,
            api_key
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка AI: {str(e)}")
        return f"Произошла ошибка при обработке вашего запроса. Пожалуйста, повторите попытку позже или обратитесь к администратору системы."


# Инициализация FastAPI с заголовками и метаданными
app = FastAPI(
    title="ToU AI Assistant", 
    version="2.1.0",
    description="AI-ассистент университета Торайгырова на базе Gemini",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Настройка CORS для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Можно ограничить для продакшн
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    """Модель запроса для эндпоинта /api/ask"""
    question: str
    api_key: Optional[str] = None


@app.get("/api/health")
async def health():
    """Эндпоинт проверки работоспособности сервера"""
    return {
        "status": "ok",
        "timestamp": time.time(),
        "cache_size": len(response_cache),
        "version": "2.1.0"
    }


@app.post("/api/ask")
async def ask_ai(req: QueryRequest, x_api_key: Optional[str] = Header(None)):
    """Основной эндпоинт для получения ответов от AI"""
    if not req.question or not req.question.strip():
        return JSONResponse(
            status_code=400,
            content={"answer": "Вопрос не может быть пустым."}
        )

    # Используем API ключ из заголовка или из тела запроса
    api_key = x_api_key or req.api_key

    try:
        start_time = time.time()
        answer = await get_ai_answer_async(req.question, api_key)
        processing_time = time.time() - start_time
        
        # Проверяем, был ли ответ взят из кеша
        cache_key = get_cache_key(preprocess_query(req.question), knowledge_cache.get()[1])
        is_cached = cache_key in response_cache and is_cache_valid(response_cache[cache_key][1])

        return JSONResponse(
            status_code=200,
            content={
                "answer": answer,
                "processing_time": round(processing_time, 2),
                "cached": is_cached
            }
        )
    except ValueError as e:
        logger.error(f"Ошибка валидации: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "answer": f"Ошибка запроса: {str(e)}",
                "error": True
            }
        )
    except Exception as e:
        logger.error(f"Ошибка сервера: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "answer": f"Произошла внутренняя ошибка сервера. Пожалуйста, повторите попытку позже.",
                "error": True
            }
        )


# Эндпоинт для очистки кэша (защищенный паролем для продакшна)
@app.post("/api/clear-cache")
async def clear_cache(api_key: Optional[str] = Header(None)):
    """Очистка кеша ответов (для разработки и администрирования)"""
    global response_cache
    if api_key and api_key == os.getenv("ADMIN_API_KEY", "admin_key_default"):
        old_size = len(response_cache)
        response_cache.clear()
        return {"status": "Кеш очищен", "old_size": old_size, "timestamp": time.time()}
    else:
        return JSONResponse(
            status_code=401,
            content={"status": "Недостаточно прав для этой операции"}
        )


# Монтирование статических файлов фронтенда если они доступны
frontend_dist = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
if os.environ.get("TOU_SERVE_FRONTEND") == "1" or ("--serve-frontend" in sys.argv):
    if os.path.isdir(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
        logger.info(f"Фронтенд смонтирован из: {frontend_dist}")
    else:
        logger.warning(f"Директория фронтенда не найдена: {frontend_dist}")

# Запуск приложения при прямом выполнении
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
