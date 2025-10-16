from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import CSVUploadLog, CSVData, CSVColumn


@admin.register(CSVUploadLog)
class CSVUploadLogAdmin(admin.ModelAdmin):
    """
    Админ-панель для журнала загрузки CSV файлов
    """
    list_display = [
        'filename', 
        'author', 
        'upload_date', 
        'file_size', 
        'rows_count', 
        'columns_count', 
        'has_headers',
        'delimiter_display',
        'status',
        'download_link'
    ]
    list_filter = [
        'status', 
        'has_headers',
        'delimiter',
        'upload_date', 
        'author'
    ]
    search_fields = [
        'filename', 
        'author__username', 
        'author__first_name', 
        'author__last_name'
    ]
    readonly_fields = [
        'upload_date', 
        'file_size', 
        'rows_count', 
        'columns_count'
    ]
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Настраиваем форму для автоматического заполнения
        """
        form = super().get_form(request, obj, **kwargs)
        
        # Для новых объектов делаем поля необязательными
        if not obj:
            form.base_fields['filename'].required = False
            form.base_fields['filename'].help_text = "Будет заполнено автоматически из имени файла"
            
            form.base_fields['author'].required = False
            form.base_fields['author'].help_text = "Будет заполнено автоматически текущим пользователем"
        
        return form
    ordering = ['-upload_date']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('filename', 'author', 'upload_date')
        }),
        ('Параметры файла', {
            'fields': ('file_size', 'rows_count', 'columns_count')
        }),
        ('Настройки файла', {
            'fields': ('has_headers', 'delimiter', 'original_file')
        }),
        ('Статус обработки', {
            'fields': ('status', 'error_message')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """
        Автоматически устанавливает автора при сохранении
        """
        # Передаем текущего пользователя в модель для автоматического заполнения
        obj._current_user = request.user
        
        # Если автор не заполнен, устанавливаем текущего пользователя
        if not obj.author_id:
            obj.author = request.user
            
        super().save_model(request, obj, form, change)
    
    def response_change(self, request, obj):
        """Обработка кнопок действий"""
        if "_auto_detect_delimiter" in request.POST:
            if not obj.original_file:
                messages.warning(request, "Файл не загружен для определения разделителя.")
            else:
                try:
                    detected_delimiter = obj.auto_detect_delimiter()
                    delimiter_names = {
                        ',': 'Запятая',
                        ';': 'Точка с запятой',
                        '\t': 'Табуляция',
                        '|': 'Вертикальная черта',
                        ' ': 'Пробел',
                        ':': 'Двоеточие',
                    }
                    delimiter_name = delimiter_names.get(detected_delimiter, detected_delimiter)
                    messages.success(request, f"Разделитель определен автоматически: {delimiter_name}")
                except Exception as e:
                    messages.error(request, f"Ошибка определения разделителя: {e}")
            return HttpResponseRedirect(request.path)
        
        if "_process_csv" in request.POST:
            if not obj.original_file:
                messages.warning(request, "Файл не загружен для обработки.")
            else:
                try:
                    result = obj.process_csv_data()
                    messages.success(
                        request, 
                        f"CSV файл обработан успешно! "
                        f"Строк: {result['rows_count']}, "
                        f"Столбцов: {result['columns_count']}"
                    )
                except Exception as e:
                    messages.error(request, f"Ошибка обработки CSV файла: {e}")
            return HttpResponseRedirect(request.path)
        
        return super().response_change(request, obj)
    
    def delimiter_display(self, obj):
        """Отображает разделитель в удобном виде"""
        delimiter_map = {
            ',': 'Запятая',
            ';': 'Точка с запятой',
            '\t': 'Табуляция',
            '|': 'Вертикальная черта',
            ' ': 'Пробел',
            ':': 'Двоеточие',
        }
        return delimiter_map.get(obj.delimiter, obj.delimiter)
    delimiter_display.short_description = 'Разделитель'
    
    def download_link(self, obj):
        """
        Отображает ссылку для скачивания файла
        """
        if obj.original_file:
            download_url = reverse('data_sources:download_csv', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank">📥 Скачать</a>',
                download_url
            )
        return "Файл не загружен"
    download_link.short_description = 'Скачать файл'


@admin.register(CSVData)
class CSVDataAdmin(admin.ModelAdmin):
    """
    Админ-панель для данных CSV файлов
    """
    list_display = [
        'upload_log', 
        'row_number', 
        'column_number', 
        'column_name', 
        'cell_value_preview', 
        'created_at'
    ]
    list_filter = [
        'upload_log__filename', 
        'column_name', 
        'created_at'
    ]
    search_fields = [
        'cell_value', 
        'column_name', 
        'upload_log__filename'
    ]
    readonly_fields = ['created_at']
    ordering = ['upload_log', 'row_number', 'column_number']
    
    def cell_value_preview(self, obj):
        """
        Показывает превью значения ячейки (первые 50 символов)
        """
        return obj.cell_value[:50] + '...' if len(obj.cell_value) > 50 else obj.cell_value
    cell_value_preview.short_description = 'Значение ячейки (превью)'
    
    fieldsets = (
        ('Связь с файлом', {
            'fields': ('upload_log',)
        }),
        ('Позиция в файле', {
            'fields': ('row_number', 'column_number', 'column_name')
        }),
        ('Данные', {
            'fields': ('cell_value', 'created_at')
        }),
    )


@admin.register(CSVColumn)
class CSVColumnAdmin(admin.ModelAdmin):
    """
    Админ-панель для столбцов CSV файлов
    """
    list_display = [
        'upload_log', 
        'column_number', 
        'column_name', 
        'data_type', 
        'is_required',
        'created_at'
    ]
    list_filter = [
        'upload_log__filename', 
        'data_type',
        'is_required',
        'created_at'
    ]
    search_fields = [
        'column_name', 
        'original_name',
        'upload_log__filename',
        'description'
    ]
    readonly_fields = ['created_at']
    ordering = ['upload_log', 'column_number']
    
    fieldsets = (
        ('Связь с файлом', {
            'fields': ('upload_log',)
        }),
        ('Информация о столбце', {
            'fields': ('column_number', 'column_name', 'original_name')
        }),
        ('Характеристики столбца', {
            'fields': ('data_type', 'is_required', 'description')
        }),
        ('Системная информация', {
            'fields': ('created_at',)
        }),
    )
