from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.utils.encoding import smart_str
from .models import DataUploadLog
import os


@login_required
def download_csv_file(request, upload_id):
    """
    Представление для скачивания исходного CSV файла
    """
    # Получаем запись о загрузке
    upload_log = get_object_or_404(DataUploadLog, id=upload_id)
    
    # Проверяем, что файл существует
    if not upload_log.original_file:
        raise Http404("Файл не найден")
    
    # Проверяем права доступа (только автор или суперпользователь)
    if not (request.user == upload_log.author or request.user.is_superuser):
        raise Http404("У вас нет прав для скачивания этого файла")
    
    # Проверяем, что файл физически существует
    if not os.path.exists(upload_log.original_file.path):
        raise Http404("Файл не найден на диске")
    
    # Открываем файл для чтения
    try:
        with open(upload_log.original_file.path, 'rb') as file:
            response = HttpResponse(
                file.read(),
                content_type='text/csv; charset=utf-8'
            )
            
            # Устанавливаем заголовки для скачивания
            filename = smart_str(upload_log.filename)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = os.path.getsize(upload_log.original_file.path)
            
            return response
            
    except IOError:
        raise Http404("Ошибка при чтении файла")
