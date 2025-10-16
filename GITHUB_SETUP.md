# Настройка GitHub репозитория

## 📋 Пошаговая инструкция

### 1. Создание репозитория на GitHub

1. **Перейдите на GitHub:** https://github.com/michaelbag
2. **Нажмите зеленую кнопку "New"** или перейдите по ссылке: https://github.com/new
3. **Заполните данные репозитория:**
   - **Repository name:** `lg_for`
   - **Description:** `Django система для генерации этикеток с поддержкой CSV данных и PDF шаблонов`
   - **Visibility:** 
     - ✅ **Public** (если хотите открытый репозиторий)
     - ✅ **Private** (если хотите приватный репозиторий)
   - **НЕ добавляйте:**
     - ❌ README.md (уже есть в проекте)
     - ❌ .gitignore (уже есть в проекте)
     - ❌ License (пока не нужна)
4. **Нажмите "Create repository"**

### 2. Загрузка кода на GitHub

После создания репозитория выполните команды:

```bash
cd /Users/mihailkudravcev/Projects/lg_formater
git push -u origin main
```

### 3. Альтернативные способы

#### Если репозиторий уже существует, но пустой:
```bash
cd /Users/mihailkudravcev/Projects/lg_formater
git push -u origin main
```

#### Если репозиторий не пустой и нужно принудительно загрузить:
```bash
cd /Users/mihailkudravcev/Projects/lg_formater
git push -u origin main --force
```

#### Если нужно изменить URL репозитория:
```bash
cd /Users/mihailkudravcev/Projects/lg_formater
git remote set-url origin https://github.com/michaelbag/lg_for.git
git push -u origin main
```

## 🔗 После успешной загрузки

Проект будет доступен по адресу: **https://github.com/michaelbag/lg_for**

## 📁 Структура проекта на GitHub

```
lg_for/
├── data_sources/              # Управление CSV данными
│   ├── models.py             # Модели данных
│   ├── admin.py              # Админ-панель
│   ├── csv_processor.py      # Обработчик CSV файлов
│   └── migrations/           # Миграции базы данных
├── label_templates/          # Шаблоны этикеток
│   ├── models.py             # Модели шаблонов
│   ├── admin.py              # Админ-панель
│   └── migrations/           # Миграции
├── label_generator/          # Генератор PDF этикеток
│   ├── models.py             # Модели генерации
│   ├── pdf_generator.py      # Генератор PDF
│   ├── admin.py              # Админ-панель
│   └── management/           # Django команды
├── lg_formater/              # Основной проект Django
│   ├── settings.py           # Настройки
│   └── urls.py               # URL маршруты
├── templates/                # HTML шаблоны
├── requirements.txt          # Зависимости Python
├── README.md                 # Основная документация
├── QUICKSTART.md             # Быстрый старт
├── DEPLOYMENT.md             # Инструкции развертывания
├── GITHUB_SETUP.md           # Эта инструкция
└── start_server.sh           # Скрипт запуска сервера
```

## 🚀 Возможности проекта

### ✅ Реализованные функции:
- **Управление CSV данными** с поддержкой различных разделителей
- **Автоматическое определение разделителя** в CSV файлах
- **Обработка различных кодировок** (UTF-8, CP1251, Latin-1)
- **Шаблоны этикеток** (с файлами и с чистого листа)
- **Автоматическое определение размеров** шаблонов
- **Генерация PDF этикеток** с сопоставлением полей
- **Отслеживание прогресса** генерации
- **Детальное логирование** процесса
- **Безопасный доступ** к файлам
- **Сетевой доступ** на всех IP адресах

## 🔧 Технические детали

- **Framework:** Django 5.2.7
- **Python:** 3.11+
- **База данных:** SQLite (для разработки)
- **PDF генерация:** ReportLab
- **Обработка изображений:** Pillow
- **PDF обработка:** PyMuPDF

## 📖 Документация

- **README.md** - полное описание системы
- **QUICKSTART.md** - быстрый старт за 5 минут
- **DEPLOYMENT.md** - инструкции по развертыванию
- **GITHUB_SETUP.md** - эта инструкция

## 🎯 Следующие шаги

1. Создайте репозиторий на GitHub
2. Загрузите код командой `git push -u origin main`
3. Проверьте доступность по адресу https://github.com/michaelbag/lg_for
4. При необходимости настройте GitHub Pages или другие интеграции
