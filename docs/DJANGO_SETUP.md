# Django + Postgres за 5–10 минут — пошаговая шпаргалка

Шаг за шагом, команда за командой. Открыть, пройтись сверху вниз — пустой проект готов.
Пример ниже для сайта `brain.com.ua` → папка проекта `braincomua_project`.
Для другого сайта меняешь только имя домена.

> Проверено на macOS, Python 3.13, Django 5.2, PostgreSQL 16 (Docker).
> Linux — те же команды. Windows — отличия помечены **[Win]**.

---

## 0. Что должно быть установлено

| Что | Проверка | Если нет |
|---|---|---|
| Python 3.11+ | `python3 --version` | python.org |
| Docker | `docker --version` | Docker Desktop |
| Git | `git --version` | git-scm.com |

Postgres ставить не обязательно — поднимаем его в Docker (шаг 3).
Если Postgres уже установлен локально — шаг 3 пропустить, сразу шаг 3b.

---

## 1. Папка проекта + виртуальное окружение

```bash
mkdir brain-parsers && cd brain-parsers
git init
python3 -m venv .venv
source .venv/bin/activate
```

**[Win]** `python -m venv .venv` → `.venv\Scripts\activate`

Проверка: в начале строки терминала появилось `(.venv)`.

---

## 2. Зависимости

```bash
pip install --upgrade pip
pip install "django>=5.1,<5.3" "psycopg[binary]" requests beautifulsoup4 lxml selenium playwright
pip freeze > requirements.txt
```

`psycopg[binary]` — драйвер Postgres (psycopg 3). Отдельно `psycopg2` не нужен.

---

## 3. Postgres в Docker

Создать `docker-compose.yml` в корне:

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: brain-parsers-db
    environment:
      POSTGRES_DB: brain
      POSTGRES_USER: brain
      POSTGRES_PASSWORD: brain
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

```bash
docker compose up -d
docker ps            # контейнер brain-parsers-db в статусе Up
```

База `brain`, юзер `brain`, пароль `brain` создаются автоматически.

**Ошибка `port is already allocated`** — на 5432 уже висит другой Postgres.
Либо останавливаем его, либо меняем `"5433:5432"` и `POSTGRES_PORT=5433` (см. шаг 5).

### 3b. Если Postgres установлен локально (без Docker)

```bash
psql -U postgres
```
```sql
CREATE DATABASE brain;
CREATE USER brain WITH PASSWORD 'brain';
ALTER DATABASE brain OWNER TO brain;
\q
```

---

## 4. Django проект + приложение

Имя проекта = домен без точек + `_project`. Приложение всегда `parser_app`.

```bash
django-admin startproject braincomua_project
cd braincomua_project
python manage.py startapp parser_app
cd ..
```

Структура после шага:

```
brain-parsers/
├── .venv/
├── docker-compose.yml
└── braincomua_project/
    ├── manage.py
    ├── braincomua_project/   ← settings.py
    └── parser_app/           ← models.py
```

---

## 5. settings.py — подключаем приложение и Postgres

Файл `braincomua_project/braincomua_project/settings.py`.

**5.1** Сверху добавить импорт:

```python
import os
from pathlib import Path
```

**5.2** В `INSTALLED_APPS` дописать две строки:

```python
INSTALLED_APPS = [
    ...
    'django.contrib.staticfiles',
    'django.contrib.postgres',   # для ArrayField
    'parser_app',
]
```

**5.3** Блок `DATABASES` заменить целиком:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'brain'),
        'USER': os.environ.get('POSTGRES_USER', 'brain'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'brain'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}
```

**5.4** (опционально) `TIME_ZONE = 'Europe/Kyiv'`

---

## 6. Модель

`parser_app/models.py`. Правила: **все поля `null=True`**, сначала важные поля,
потом списки/JSON, в конце служебные (`link`, `status`).

```python
from django.contrib.postgres.fields import ArrayField
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=255, null=True)
    price = models.IntegerField(null=True)
    photos = ArrayField(models.URLField(max_length=500, null=True), null=True, blank=True)
    specifications = models.JSONField(null=True, blank=True)
    link = models.URLField(max_length=500, null=True)
    status = models.CharField(max_length=50, default='New', null=True)
```

---

## 7. Миграции

```bash
cd braincomua_project
python manage.py makemigrations parser_app
python manage.py migrate
cd ..
```

Увидел `Applying parser_app.0001_initial... OK` — Postgres подключен, таблица создана.

**Типичные ошибки:**

| Ошибка | Причина | Решение |
|---|---|---|
| `connection refused` | Контейнер не запущен | `docker compose up -d` |
| `password authentication failed` | Не совпадают данные в settings и compose | Сверить NAME/USER/PASSWORD |
| `No module named 'psycopg'` | Не активирован venv / не установлен драйвер | `source .venv/bin/activate`, `pip install "psycopg[binary]"` |
| `No changes detected` | Приложение не в `INSTALLED_APPS` | Шаг 5.2 |

---

## 8. Папка `modules` + `load_django.py`

Все скрипты парсера живут в `modules/`, рядом с папкой Django-проекта (не внутри).

```bash
mkdir modules results
```

`modules/load_django.py` — **меняется только имя проекта в двух местах**:

```python
import os
import sys

import django

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'braincomua_project')))
os.environ['DJANGO_SETTINGS_MODULE'] = 'braincomua_project.settings'
django.setup()
```

Путь относительный (`..` от папки `modules`) — работает на любом компьютере без правок.

В начале любого скрипта в `modules/`:

```python
from load_django import *
from parser_app.models import Product
```

---

## 9. Проверка: запись и чтение

`modules/0_check_db_write.py`:

```python
"""
Checks that load_django works: writes a test record into the Product model
"""

from load_django import *
from parser_app.models import Product

product, created = Product.objects.get_or_create(name='Test product', parser='check')
print(f'Created: {created}, id: {product.id}')
```

`modules/0_check_db_read.py`:

```python
"""
Checks that load_django works: reads test records from the Product model and prints them
"""

from load_django import *
from parser_app.models import Product

for product in Product.objects.filter(parser='check').order_by('id'):
    print(product.id, product.name)
```

Запуск **из папки `modules`**:

```bash
cd modules
python 0_check_db_write.py    # Created: True, id: 1
python 0_check_db_write.py    # Created: False, id: 1  ← get_or_create не дублирует
python 0_check_db_read.py     # 1 Test product
```

**`ModuleNotFoundError: No module named 'parser_app'`** — скрипт запущен не из `modules`
или в `load_django.py` неверное имя папки проекта.

---

## 10. Бонус: админка, экспорт, дамп

```bash
# Админка
cd braincomua_project
python manage.py createsuperuser
python manage.py runserver        # http://127.0.0.1:8000/admin/

# Дамп БД в results/
docker exec brain-parsers-db pg_dump -U brain --no-owner brain > results/brain_dump.sql

# Восстановить дамп
docker exec -i brain-parsers-db psql -U brain brain < results/brain_dump.sql
```

---

## Чеклист (засекай время)

- [ ] venv + зависимости
- [ ] `docker compose up -d`
- [ ] `startproject <domain>_project` + `startapp parser_app`
- [ ] settings: `parser_app`, `django.contrib.postgres`, `DATABASES`
- [ ] модель (все поля `null=True`)
- [ ] `makemigrations` + `migrate`
- [ ] `modules/load_django.py`
- [ ] запись + чтение из `modules` работают
