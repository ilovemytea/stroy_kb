"""Настройки подключения. Значения можно переопределить переменными окружения."""
import os

SQL_SERVER = os.getenv("STROYMIR_SQL_SERVER", ".")            # «.» = локальный экземпляр по умолчанию
SQL_DATABASE = os.getenv("STROYMIR_SQL_DATABASE", "StroyMir_KB_Review_20261121")
SQL_USER = os.getenv("STROYMIR_SQL_USER")                     # пусто = проверка подлинности Windows
SQL_PASSWORD = os.getenv("STROYMIR_SQL_PASSWORD", "")
SQL_DRIVER = os.getenv("STROYMIR_SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_TRUST_CERT = os.getenv("STROYMIR_SQL_TRUST_CERT", "1") == "1"

ADMIN_PASSWORD = os.getenv("STROYMIR_ADMIN_PASSWORD")  # обязательный пароль редактора
SECRET_KEY = os.getenv("STROYMIR_SECRET_KEY")  # обязательный случайный ключ подписи сессий
PORT = int(os.getenv("STROYMIR_PORT", "5000"))


def connection_string():
    parts = [f"DRIVER={{{SQL_DRIVER}}}", f"SERVER={SQL_SERVER}", f"DATABASE={SQL_DATABASE}"]
    if SQL_USER:
        parts += [f"UID={SQL_USER}", f"PWD={SQL_PASSWORD}"]
    else:
        parts.append("Trusted_Connection=yes")
    if SQL_TRUST_CERT:
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts)
