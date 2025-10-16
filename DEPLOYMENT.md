# Развертывание проекта на GitHub

## Создание репозитория на GitHub

1. **Перейдите на GitHub:** https://github.com/michaelbag
2. **Нажмите "New repository"** или перейдите по ссылке: https://github.com/new
3. **Заполните данные:**
   - Repository name: `lg_for`
   - Description: `Django система для генерации этикеток с поддержкой CSV данных и PDF шаблонов`
   - Visibility: Public или Private (на ваш выбор)
   - НЕ добавляйте README, .gitignore или лицензию (они уже есть в проекте)
4. **Нажмите "Create repository"**

## Загрузка кода на GitHub

После создания репозитория выполните команды:

```bash
cd /Users/mihailkudravcev/Projects/lg_formater
git push -u origin main
```

## Альтернативный способ (если репозиторий уже создан)

Если репозиторий уже существует, но пустой:

```bash
cd /Users/mihailkudravcev/Projects/lg_formater
git push -u origin main
```

Если репозиторий не пустой и нужно принудительно загрузить:

```bash
cd /Users/mihailkudravcev/Projects/lg_formater
git push -u origin main --force
```

## Проверка загрузки

После успешной загрузки проект будет доступен по адресу:
https://github.com/michaelbag/lg_for

## Структура проекта

Проект содержит:
- **data_sources/** - управление источниками данных (CSV файлы)
- **label_templates/** - управление шаблонами этикеток
- **label_generator/** - генератор PDF этикеток
- **requirements.txt** - зависимости проекта
- **README.md** - документация проекта
- **start_server.sh** - скрипт запуска сервера

## Настройка на новом сервере

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/michaelbag/lg_for.git
   cd lg_for
   ```

2. **Создайте виртуальную среду:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # или
   venv\Scripts\activate     # Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте базу данных:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Запустите сервер:**
   ```bash
   ./start_server.sh
   # или
   python manage.py runserver 0.0.0.0:8001
   ```
   
   Сервер будет доступен на всех IP адресах по порту 8001
