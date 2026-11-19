"""Private, persistent settings for the loopback-only ``python app.py`` entrypoint.

WSGI imports never invoke this helper and still require explicit credentials.
"""
import json
import os
from pathlib import Path
import secrets

KEYS = ('STROYMIR_ADMIN_PASSWORD', 'STROYMIR_SECRET_KEY')


def configure_local(path=None, environ=None):
    environ = os.environ if environ is None else environ
    if all(environ.get(key) for key in KEYS):
        return None
    path = Path(path) if path is not None else Path(__file__).with_name('.env.local.json')
    if not path.exists():
        settings = {
            'STROYMIR_ADMIN_PASSWORD': secrets.token_urlsafe(24),
            'STROYMIR_SECRET_KEY': secrets.token_hex(32),
        }
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(settings, output, ensure_ascii=False, indent=2)
                output.write('\n')
    try:
        settings = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(settings, dict) or any(
            not isinstance(settings.get(key), str) or not settings[key].strip()
            for key in KEYS
        ):
            raise ValueError('Missing local settings')
    except (OSError, ValueError) as error:
        raise RuntimeError(f'Проверьте локальные настройки в {path.name}: нужен корректный JSON с паролем и ключом.') from error
    for key in KEYS:
        if not environ.get(key):
            environ[key] = settings[key]
    return path
