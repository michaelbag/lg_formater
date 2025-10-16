from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import LabelTemplate, TemplateField, TemplateUsage


class TemplateFieldInline(admin.TabularInline):
    """
    Встроенная админ-панель для полей шаблона
    """
    model = TemplateField
    extra = 0
    fields = [
        'field_name', 'field_type', 'x_position', 'y_position', 
        'width', 'height', 'font_size', 'is_required'
    ]


@admin.register(LabelTemplate)
class LabelTemplateAdmin(admin.ModelAdmin):
    """
    Админ-панель для шаблонов этикеток
    """
    list_display = [
        'name', 
        'template_type_display', 
        'print_width_mm', 
        'print_height_mm', 
        'layout_width_mm',
        'layout_height_mm',
        'dpi',
        'is_active',
        'created_by',
        'created_at',
        'preview_link',
        'file_size_display'
    ]
    list_filter = [
        'template_type',
        'is_active',
        'created_at',
        'created_by',
        'template_file'
    ]
    search_fields = [
        'name',
        'description',
        'created_by__username'
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'file_size_display',
        'file_extension'
    ]
    inlines = [TemplateFieldInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'template_type', 'is_active')
        }),
        ('Файлы', {
            'fields': ('template_file', 'preview_image', 'file_size_display', 'file_extension')
        }),
        ('Область печати', {
            'fields': ('print_width_mm', 'print_height_mm')
        }),
        ('Область макета (под обрез)', {
            'fields': ('layout_width_mm', 'layout_height_mm')
        }),
        ('Отступы', {
            'fields': ('margin_top_mm', 'margin_bottom_mm', 'margin_left_mm', 'margin_right_mm'),
            'classes': ('collapse',)
        }),
        ('Параметры печати', {
            'fields': ('dpi',)
        }),
        ('Системная информация', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливает создателя при сохранении"""
        if not change:  # Если это новый объект
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def response_change(self, request, obj):
        """Обработка кнопки переопределения размеров"""
        if "_redetect_dimensions" in request.POST:
            if obj.is_blank_template:
                messages.warning(request, "Нельзя переопределить размеры для шаблона без файла.")
            else:
                try:
                    obj.auto_detect_dimensions()
                    obj.save()
                    messages.success(request, "Размеры шаблона успешно переопределены.")
                except Exception as e:
                    messages.error(request, f"Ошибка при определении размеров: {e}")
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)
    
    def preview_link(self, obj):
        """Отображает ссылку на превью изображение"""
        if obj.preview_image:
            return format_html(
                '<a href="{}" target="_blank">👁️ Превью</a>',
                obj.preview_image.url
            )
        return "Нет превью"
    preview_link.short_description = 'Превью'
    
    def file_size_display(self, obj):
        """Отображает размер файла в удобном формате"""
        if obj.is_blank_template:
            return "Без файла"
        
        size = obj.file_size
        if size == 0:
            return "0 байт"
        
        for unit in ['байт', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"
    file_size_display.short_description = 'Размер файла'


@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    """
    Админ-панель для полей шаблонов
    """
    list_display = [
        'template',
        'field_name',
        'field_type',
        'x_position',
        'y_position',
        'width',
        'height',
        'is_required'
    ]
    list_filter = [
        'field_type',
        'is_required',
        'template__template_type',
        'template'
    ]
    search_fields = [
        'field_name',
        'template__name',
        'description'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('template', 'field_name', 'field_type', 'description')
        }),
        ('Позиция и размер', {
            'fields': ('x_position', 'y_position', 'width', 'height')
        }),
        ('Настройки текста', {
            'fields': ('font_size', 'font_family', 'is_bold', 'is_italic', 'alignment')
        }),
        ('Дополнительные настройки', {
            'fields': ('default_value', 'is_required')
        }),
    )


@admin.register(TemplateUsage)
class TemplateUsageAdmin(admin.ModelAdmin):
    """
    Админ-панель для отслеживания использования шаблонов
    """
    list_display = [
        'template',
        'data_source',
        'generated_count',
        'generated_by',
        'generated_at',
        'output_file_link'
    ]
    list_filter = [
        'generated_at',
        'template__template_type',
        'generated_by'
    ]
    search_fields = [
        'template__name',
        'data_source__filename',
        'generated_by__username'
    ]
    readonly_fields = ['generated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('template', 'data_source', 'generated_count')
        }),
        ('Результат генерации', {
            'fields': ('output_file', 'generated_by', 'generated_at')
        }),
    )
    
    def output_file_link(self, obj):
        """Отображает ссылку на результирующий файл"""
        if obj.output_file:
            return format_html(
                '<a href="{}" target="_blank">📄 Скачать</a>',
                obj.output_file.url
            )
        return "Файл не создан"
    output_file_link.short_description = 'Результирующий файл'
