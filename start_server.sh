#!/bin/bash

# LG Formater - Development Server Startup Script
# ⚠️ ВНИМАНИЕ: ПРОЕКТ В РАЗРАБОТКЕ - НЕ ДЛЯ ПРОМЫШЛЕННОЙ ЭКСПЛУАТАЦИИ ⚠️

echo "=========================================="
echo "🚧 LG FORMATER - DEVELOPMENT SERVER 🚧"
echo "=========================================="
echo ""
echo "⚠️  ВНИМАНИЕ: ПРОЕКТ В РАЗРАБОТКЕ ⚠️"
echo "❌ СТАТУС: НЕ РАБОЧИЙ"
echo "🚫 НЕ ДЛЯ ПРОМЫШЛЕННОЙ ЭКСПЛУАТАЦИИ"
echo "📋 ВЕРСИЯ: 0.1.0-dev"
echo ""
echo "🔧 Известные проблемы:"
echo "   - Фон шаблона не отображается"
echo "   - Векторный рендеринг нестабилен"
echo "   - Автозаполнение может работать некорректно"
echo ""
echo "📖 Подробности: DEVELOPMENT_STATUS.md"
echo "=========================================="
echo ""

# Активируем виртуальную среду
if [ -d "venv" ]; then
    echo "🔧 Активация виртуальной среды..."
    source venv/bin/activate
else
    echo "❌ Виртуальная среда не найдена!"
    echo "Создайте виртуальную среду: python3 -m venv venv"
    exit 1
fi

# Проверяем зависимости
echo "🔍 Проверка зависимостей..."
if ! python -c "import django" 2>/dev/null; then
    echo "❌ Django не установлен!"
    echo "Установите зависимости: pip install -r requirements.txt"
    exit 1
fi

# Запускаем сервер
echo "🚀 Запуск сервера разработки..."
echo "🌐 Доступ: http://localhost:8001"
echo "👤 Админка: http://localhost:8001/admin"
echo ""
echo "⚠️  НЕ ИСПОЛЬЗУЙТЕ В ПРОИЗВОДСТВЕННОЙ СРЕДЕ! ⚠️"
echo ""

python manage.py runserver 0.0.0.0:8001