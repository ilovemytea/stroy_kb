"""Start the isolated experiment; never target the working database by default."""
import os
from pathlib import Path
import runpy

os.environ.setdefault('STROYMIR_SQL_DATABASE','StroyMir_KB_Review_20261121')
if '_Review_' not in os.environ['STROYMIR_SQL_DATABASE']:
    raise RuntimeError('Для экспериментального запуска выберите отдельную базу _Review_.')
os.environ.setdefault('STROYMIR_PORT','5011')
runpy.run_path(str(Path(__file__).with_name('app.py')),run_name='__main__')
