from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import DataUploadLog, DataRecord, DataColumn


@admin.register(DataUploadLog)
class DataUploadLogAdmin(admin.ModelAdmin):
    """
    Админ-панель для журнала загрузки файлов данных
    """
    change_form_template = 'admin/data_sources/csvuploadlog/change_form.html'
    
    list_display = [
        'filename', 
        'author', 
        'upload_date', 
        'file_type_display',
        'file_size', 
        'rows_count_display', 
        'columns_count_display', 
        'has_headers',
        'delimiter_display',
        'status',
        'download_link'
    ]
    list_filter = [
        'status', 
        'file_type',
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
        'columns_count',
        'sheet_name'
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
            'fields': ('filename', 'author', 'upload_date', 'file_type')
        }),
        ('Параметры файла', {
            'fields': ('file_size', 'rows_count', 'columns_count', 'sheet_name')
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
    
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        """
        Добавляем дополнительные кнопки в контекст
        """
        if obj and obj.pk and obj.original_file:
            context['show_csv_buttons'] = True
        else:
            context['show_csv_buttons'] = False
        
        return super().render_change_form(request, context, add, change, form_url, obj)
    
    
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
        
        if "_process_data" in request.POST:
            if not obj.original_file:
                messages.warning(request, "Файл не загружен для обработки.")
            else:
                try:
                    result = obj.process_data()
                    if result.get('success'):
                        messages.success(
                            request, 
                            f"Файл обработан успешно! "
                            f"Строк: {result.get('rows_processed', 'N/A')}, "
                            f"Столбцов: {result.get('columns_processed', 'N/A')}"
                        )
                    else:
                        messages.error(request, f"Ошибка обработки файла: {result.get('error', 'Неизвестная ошибка')}")
                except Exception as e:
                    messages.error(request, f"Ошибка обработки файла: {e}")
            return HttpResponseRedirect(request.path)
        
        return super().response_change(request, obj)
    
    def file_type_display(self, obj):
        """Отображает тип файла"""
        type_map = {
            'csv': 'CSV',
            'xlsx': 'Excel (XLSX)',
        }
        return type_map.get(obj.file_type, obj.file_type.upper())
    file_type_display.short_description = 'Тип файла'
    
    def rows_count_display(self, obj):
        """Отображает количество строк или статус"""
        if obj.rows_count is not None:
            return obj.rows_count
        elif obj.status == 'uploading':
            return "Не обработано"
        else:
            return "—"
    rows_count_display.short_description = 'Строк'
    
    def columns_count_display(self, obj):
        """Отображает количество столбцов или статус"""
        if obj.columns_count is not None:
            return obj.columns_count
        elif obj.status == 'uploading':
            return "Не обработано"
        else:
            return "—"
    columns_count_display.short_description = 'Столбцов'
    
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


@admin.register(DataRecord)
class DataRecordAdmin(admin.ModelAdmin):
    """
    Админ-панель для записей данных
    """
    list_display = [
        'upload_log', 
        'row_number', 
        'column_number', 
        'data_column', 
        'cell_value_preview', 
        'created_at'
    ]
    list_filter = [
        'upload_log__filename', 
        'data_column__column_name', 
        'created_at'
    ]
    search_fields = [
        'cell_value', 
        'data_column__column_name', 
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
            'fields': ('row_number', 'column_number', 'data_column')
        }),
        ('Данные', {
            'fields': ('cell_value', 'created_at')
        }),
    )


@admin.register(DataColumn)
class DataColumnAdmin(admin.ModelAdmin):
    """
    Админ-панель для столбцов данных
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
