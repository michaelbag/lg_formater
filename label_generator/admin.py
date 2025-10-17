from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django import forms
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe
from .models import LabelGeneration, FieldMapping, GenerationLog


class FieldMappingInline(admin.TabularInline):
    """
    Встроенная админ-панель для сопоставления полей
    """
    model = FieldMapping
    extra = 0
    fields = [
        'template_field', 'data_column_number', 'data_column_name',
        'is_required', 'default_value', 'format_string', 'order'
    ]
    readonly_fields = ['data_column_name']
    
    def get_queryset(self, request):
        """Оптимизируем запросы"""
        return super().get_queryset(request).select_related('template_field')


class GenerationLogInline(admin.TabularInline):
    """
    Встроенная админ-панель для логов генерации с пагинацией
    """
    model = GenerationLog
    extra = 0
    fields = ['logs_table']
    readonly_fields = ['logs_table']
    template = 'admin/label_generator/generationlog/paginated_inline.html'
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        """Запрещаем добавление логов вручную"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем редактирование логов"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Запрещаем удаление логов"""
        return False
    
    def logs_table(self, obj):
        """Отображение логов в виде таблицы с пагинацией"""
        if not obj or not obj.pk:
            return "Логи будут доступны после сохранения генерации"
        
        # Получаем номер страницы из параметров запроса
        request = self.request
        page_number = request.GET.get('log_page', 1)
        
        try:
            page_number = int(page_number)
        except (ValueError, TypeError):
            page_number = 1
        
        # Получаем логи с пагинацией
        logs = obj.logs.all().order_by('-timestamp')
        paginator = Paginator(logs, 100)  # 100 записей на страницу
        
        try:
            page = paginator.page(page_number)
        except:
            page = paginator.page(1)
        
        # Создаем HTML таблицы
        html = f"""
        <div class="logs-container">
            <div class="logs-header">
                <h4>Логи генерации (всего: {paginator.count})</h4>
            </div>
            <div class="logs-table-container">
                <table class="logs-table">
                    <thead>
                        <tr>
                            <th>Уровень</th>
                            <th>Сообщение</th>
                            <th>Строка</th>
                            <th>Время</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for log in page.object_list:
            level_class = f"log-{log.level}"
            html += f"""
                        <tr class="{level_class}">
                            <td><span class="log-level">{log.get_level_display()}</span></td>
                            <td class="log-message">{log.message}</td>
                            <td class="log-row">{log.row_number or '—'}</td>
                            <td class="log-time">{log.timestamp.strftime('%d.%m.%Y %H:%M:%S')}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        """
        
        # Добавляем пагинацию
        if paginator.num_pages > 1:
            html += '<div class="logs-pagination">'
            
            # Предыдущая страница
            if page.has_previous():
                prev_url = f"?log_page={page.previous_page_number()}"
                html += f'<a href="{prev_url}" class="pagination-link">← Предыдущая</a>'
            
            # Номера страниц
            for num in page.paginator.page_range:
                if num == page.number:
                    html += f'<span class="pagination-current">{num}</span>'
                else:
                    page_url = f"?log_page={num}"
                    html += f'<a href="{page_url}" class="pagination-link">{num}</a>'
            
            # Следующая страница
            if page.has_next():
                next_url = f"?log_page={page.next_page_number()}"
                html += f'<a href="{next_url}" class="pagination-link">Следующая →</a>'
            
            html += '</div>'
        
        # Добавляем CSS стили
        html += """
        <style>
        .logs-container {
            margin: 10px 0;
        }
        .logs-header h4 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .logs-table-container {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .logs-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .logs-table th {
            background-color: #f8f9fa;
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .logs-table td {
            padding: 6px 8px;
            border-bottom: 1px solid #eee;
        }
        .logs-table tr:hover {
            background-color: #f5f5f5;
        }
        .log-level {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .log-debug .log-level { background-color: #e9ecef; color: #6c757d; }
        .log-info .log-level { background-color: #d1ecf1; color: #0c5460; }
        .log-warning .log-level { background-color: #fff3cd; color: #856404; }
        .log-error .log-level { background-color: #f8d7da; color: #721c24; }
        .log-critical .log-level { background-color: #f5c6cb; color: #721c24; }
        .log-message {
            max-width: 300px;
            word-wrap: break-word;
        }
        .log-row {
            text-align: center;
            width: 60px;
        }
        .log-time {
            width: 120px;
            font-size: 11px;
        }
        .logs-pagination {
            margin-top: 10px;
            text-align: center;
        }
        .pagination-link {
            display: inline-block;
            padding: 4px 8px;
            margin: 0 2px;
            background-color: #007cba;
            color: white;
            text-decoration: none;
            border-radius: 3px;
            font-size: 12px;
        }
        .pagination-link:hover {
            background-color: #005a87;
            color: white;
        }
        .pagination-current {
            display: inline-block;
            padding: 4px 8px;
            margin: 0 2px;
            background-color: #333;
            color: white;
            border-radius: 3px;
            font-size: 12px;
        }
        </style>
        """
        
        html += '</div>'
        
        return mark_safe(html)
    
    logs_table.short_description = 'Логи генерации'


@admin.register(LabelGeneration)
class LabelGenerationAdmin(admin.ModelAdmin):
    """
    Админ-панель для генерации этикеток
    """
    list_display = [
        'name',
        'data_source',
        'template',
        'status',
        'progress_display',
        'total_labels',
        'generated_labels',
        'created_by',
        'created_at',
        'output_file_link'
    ]
    list_filter = [
        'status',
        'created_at',
        'created_by',
        'template__template_type'
    ]
    search_fields = [
        'name',
        'description',
        'data_source__filename',
        'template__name',
        'created_by__username'
    ]
    readonly_fields = [
        'created_at',
        'started_at',
        'completed_at',
        'progress_percent',
        'total_labels',
        'generated_labels',
        'output_file_link',
        'log_file_link',
        'logs_display'
    ]
    inlines = [FieldMappingInline]
    
    def get_inline_instances(self, request, obj=None):
        """Передаем request в inline для доступа к параметрам пагинации"""
        inline_instances = []
        for inline_class in self.inlines:
            inline = inline_class(self.model, self.admin_site)
            inline.request = request  # Передаем request в inline
            inline_instances.append(inline)
        return inline_instances
    
    def logs_display(self, obj):
        """Отображение логов в виде таблицы с пагинацией"""
        if not obj or not obj.pk:
            return "Логи будут доступны после сохранения генерации"
        
        # Получаем номер страницы из параметров запроса
        request = self.request
        page_number = request.GET.get('log_page', 1)
        
        try:
            page_number = int(page_number)
        except (ValueError, TypeError):
            page_number = 1
        
        # Получаем логи с пагинацией
        logs = obj.logs.all().order_by('-timestamp')
        paginator = Paginator(logs, 100)  # 100 записей на страницу
        
        try:
            page = paginator.page(page_number)
        except:
            page = paginator.page(1)
        
        # Создаем HTML таблицы
        html = f"""
        <div class="logs-container">
            <div class="logs-header">
                <h4>Логи генерации (всего: {paginator.count})</h4>
            </div>
            <div class="logs-table-container">
                <table class="logs-table">
                    <thead>
                        <tr>
                            <th>Уровень</th>
                            <th>Сообщение</th>
                            <th>Строка</th>
                            <th>Время</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for log in page.object_list:
            level_class = f"log-{log.level}"
            html += f"""
                        <tr class="{level_class}">
                            <td><span class="log-level">{log.get_level_display()}</span></td>
                            <td class="log-message">{log.message}</td>
                            <td class="log-row">{log.row_number or '—'}</td>
                            <td class="log-time">{log.timestamp.strftime('%d.%m.%Y %H:%M:%S')}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        """
        
        # Добавляем пагинацию
        if paginator.num_pages > 1:
            html += '<div class="logs-pagination">'
            
            # Предыдущая страница
            if page.has_previous():
                prev_url = f"?log_page={page.previous_page_number()}"
                html += f'<a href="{prev_url}" class="pagination-link">← Предыдущая</a>'
            
            # Номера страниц
            for num in page.paginator.page_range:
                if num == page.number:
                    html += f'<span class="pagination-current">{num}</span>'
                else:
                    page_url = f"?log_page={num}"
                    html += f'<a href="{page_url}" class="pagination-link">{num}</a>'
            
            # Следующая страница
            if page.has_next():
                next_url = f"?log_page={page.next_page_number()}"
                html += f'<a href="{next_url}" class="pagination-link">Следующая →</a>'
            
            html += '</div>'
        
        # Добавляем CSS стили
        html += """
        <style>
        .logs-container {
            margin: 10px 0;
        }
        .logs-header h4 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .logs-table-container {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .logs-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .logs-table th {
            background-color: #f8f9fa;
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .logs-table td {
            padding: 6px 8px;
            border-bottom: 1px solid #eee;
        }
        .logs-table tr:hover {
            background-color: #f5f5f5;
        }
        .log-level {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .log-debug .log-level { background-color: #e9ecef; color: #6c757d; }
        .log-info .log-level { background-color: #d1ecf1; color: #0c5460; }
        .log-warning .log-level { background-color: #fff3cd; color: #856404; }
        .log-error .log-level { background-color: #f8d7da; color: #721c24; }
        .log-critical .log-level { background-color: #f5c6cb; color: #721c24; }
        .log-message {
            max-width: 300px;
            word-wrap: break-word;
        }
        .log-row {
            text-align: center;
            width: 60px;
        }
        .log-time {
            width: 120px;
            font-size: 11px;
        }
        .logs-pagination {
            margin-top: 10px;
            text-align: center;
        }
        .pagination-link {
            display: inline-block;
            padding: 4px 8px;
            margin: 0 2px;
            background-color: #007cba;
            color: white;
            text-decoration: none;
            border-radius: 3px;
            font-size: 12px;
        }
        .pagination-link:hover {
            background-color: #005a87;
            color: white;
        }
        .pagination-current {
            display: inline-block;
            padding: 4px 8px;
            margin: 0 2px;
            background-color: #333;
            color: white;
            border-radius: 3px;
            font-size: 12px;
        }
        </style>
        """
        
        html += '</div>'
        
        return mark_safe(html)
    
    logs_display.short_description = '📋 Логи генерации'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'created_by')
        }),
        ('Источники данных', {
            'fields': ('data_source', 'template')
        }),
        ('Параметры генерации', {
            'fields': ('start_row', 'end_row', 'labels_per_page')
        }),
        ('Статус и прогресс', {
            'fields': ('status', 'progress_percent', 'total_labels', 'generated_labels'),
            'classes': ('collapse',)
        }),
        ('Результаты', {
            'fields': ('output_file', 'log_file', 'output_file_link', 'log_file_link'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'started_at', 'completed_at', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Логи генерации', {
            'fields': ('logs_display',),
            'classes': ('collapse',)
        }),
    )
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Передаем request для доступа к параметрам пагинации"""
        self.request = request
        return super().change_view(request, object_id, form_url, extra_context)
    
    def get_form(self, request, obj=None, **kwargs):
        """Добавляем кнопки действий в форму"""
        form = super().get_form(request, obj, **kwargs)
        
        if obj and obj.pk:
            # Добавляем кнопки только для существующих объектов
            form.base_fields['_actions'] = forms.CharField(
                widget=forms.HiddenInput(),
                required=False
            )
        
        return form
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливает создателя при сохранении"""
        if not change:  # Если это новый объект
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def response_change(self, request, obj):
        """Обработка кнопок действий"""
        if "_start_generation" in request.POST:
            try:
                # Проверяем готовность к генерации
                errors = obj.get_generation_errors()
                if errors:
                    for error in errors:
                        messages.error(request, error)
                else:
                    # Запускаем генерацию
                    filename = obj.start_generation()
                    messages.success(request, f"Генерация запущена успешно! Файл: {filename}")
            except Exception as e:
                messages.error(request, f"Ошибка запуска генерации: {e}")
            return HttpResponseRedirect(request.path)
        
        if "_cancel_generation" in request.POST:
            if obj.status == 'processing':
                obj.status = 'cancelled'
                obj.save()
                messages.success(request, "Генерация отменена.")
            else:
                messages.warning(request, "Можно отменить только выполняющуюся генерацию.")
            return HttpResponseRedirect(request.path)
        
        return super().response_change(request, obj)
    
    def progress_display(self, obj):
        """Отображает прогресс с цветовой индикацией"""
        if obj.status == 'completed':
            color = 'green'
        elif obj.status == 'failed':
            color = 'red'
        elif obj.status == 'processing':
            color = 'blue'
        else:
            color = 'gray'
        
        return format_html(
            '<span style="color: {};">{}%</span>',
            color,
            obj.progress_percent
        )
    progress_display.short_description = 'Прогресс'
    
    def output_file_link(self, obj):
        """Отображает ссылку на результирующий файл"""
        if obj.output_file:
            return format_html(
                '<a href="{}" target="_blank">📄 Скачать</a>',
                obj.output_file.url
            )
        return "Файл не создан"
    output_file_link.short_description = 'Результирующий файл'
    
    def log_file_link(self, obj):
        """Отображает ссылку на файл лога"""
        if obj.log_file:
            return format_html(
                '<a href="{}" target="_blank">📋 Лог</a>',
                obj.log_file.url
            )
        return "Лог не создан"
    log_file_link.short_description = 'Файл лога'


@admin.register(FieldMapping)
class FieldMappingAdmin(admin.ModelAdmin):
    """
    Админ-панель для сопоставления полей
    """
    list_display = [
        'generation',
        'template_field',
        'data_column_number',
        'data_column_name',
        'is_required',
        'order'
    ]
    list_filter = [
        'is_required',
        'generation__status',
        'template_field__field_type'
    ]
    search_fields = [
        'generation__name',
        'template_field__field_name',
        'data_column_name'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('generation', 'template_field', 'order')
        }),
        ('Сопоставление данных', {
            'fields': ('data_column_number', 'data_column_name')
        }),
        ('Настройки', {
            'fields': ('is_required', 'default_value', 'format_string')
        }),
    )


@admin.register(GenerationLog)
class GenerationLogAdmin(admin.ModelAdmin):
    """
    Админ-панель для логов генерации
    """
    list_display = [
        'generation',
        'level',
        'message_preview',
        'row_number',
        'timestamp'
    ]
    list_filter = [
        'level',
        'timestamp',
        'generation__status'
    ]
    search_fields = [
        'generation__name',
        'message'
    ]
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    
    def message_preview(self, obj):
        """Показывает превью сообщения"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Сообщение (превью)'
    
    def has_add_permission(self, request, obj=None):
        """Запрещаем добавление логов вручную"""
        return False
