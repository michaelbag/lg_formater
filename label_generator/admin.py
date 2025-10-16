from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django import forms
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
    Встроенная админ-панель для логов генерации
    """
    model = GenerationLog
    extra = 0
    fields = ['level', 'message', 'row_number', 'timestamp']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    
    def has_add_permission(self, request, obj=None):
        """Запрещаем добавление логов вручную"""
        return False


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
        'log_file_link'
    ]
    inlines = [FieldMappingInline, GenerationLogInline]
    
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
    )
    
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
