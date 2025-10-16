#!/bin/bash

# Скрипт для запуска Django сервера на всех доступных IP адресах

echo "Запуск Django сервера на всех интерфейсах:8001..."
echo "Сервер будет доступен по адресам:"
echo "  - http://localhost:8001"
echo "  - http://127.0.0.1:8001"
echo "  - http://[ваш-ip-адрес]:8001"
echo ""

# Активируем виртуальную среду
source venv/bin/activate

# Запускаем сервер на всех интерфейсах
python manage.py runserver 0.0.0.0:8001
