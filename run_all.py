import subprocess
import sys
import os
import time
import requests

def run_backend():
    return subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=os.path.join(os.path.dirname(__file__), "backend"),
    )

def run_frontend():
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    if not os.path.isdir(frontend_dir):
        print("Ошибка: папка frontend не найдена.")
        return None
    try:
        return subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=frontend_dir,
        )
    except FileNotFoundError:
        print("Ошибка: npm не найден. Установите Node.js и npm.")
        return None

def wait_backend(timeout=30):
    url = "http://127.0.0.1:8000/api/health"
    for _ in range(timeout * 2):
        try:
            if requests.get(url, timeout=1).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

if __name__ == "__main__":
    print("=== Запуск AI-ассистента университета ===")
    backend = run_backend()
    print("Ожидание запуска бэкенда...")
    if not wait_backend():
        print("Бэкенд не запущен. Проверьте логи.")
        backend.terminate()
        sys.exit(1)
    print("Бэкенд готов. Запуск фронтенда...")
    frontend = run_frontend()
    if frontend is None:
        backend.terminate()
        sys.exit(1)
    print("Фронтенд: http://localhost:5173\nБэкенд:   http://127.0.0.1:8000\nДля остановки: Ctrl+C")
    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None:
                print("Бэкенд завершён. Остановка фронтенда...")
                break
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        backend.terminate()
        if frontend:
            frontend.terminate()
        print("Все процессы остановлены.")
