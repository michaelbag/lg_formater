from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from .models import LabelGeneration, FieldMapping, GenerationLog
from data_sources.models import CSVUploadLog, CSVColumn
from label_templates.models import LabelTemplate, TemplateField


@login_required
def generation_list(request):
    """
    Список генераций этикеток пользователя
    """
    generations = LabelGeneration.objects.filter(
        created_by=request.user
    ).order_by('-created_at')
    
    context = {
        'generations': generations,
        'title': 'Генерации этикеток'
    }
    return render(request, 'label_generator/generation_list.html', context)


@login_required
def generation_detail(request, generation_id):
    """
    Детальная информация о генерации
    """
    generation = get_object_or_404(
        LabelGeneration, 
        id=generation_id, 
        created_by=request.user
    )
    
    field_mappings = generation.field_mappings.all().order_by('order')
    logs = generation.logs.all().order_by('-timestamp')[:50]  # Последние 50 записей
    
    context = {
        'generation': generation,
        'field_mappings': field_mappings,
        'logs': logs,
        'title': f'Генерация: {generation.name}'
    }
    return render(request, 'label_generator/generation_detail.html', context)


@login_required
@require_http_methods(["GET"])
def get_data_source_columns(request, data_source_id):
    """
    API для получения столбцов из источника данных
    """
    data_source = get_object_or_404(CSVUploadLog, id=data_source_id)
    
    # Проверяем права доступа
    if not (request.user == data_source.author or request.user.is_superuser):
        raise Http404("У вас нет прав для доступа к этому источнику данных")
    
    # Получаем столбцы из CSVColumn или из первой строки CSVData
    columns = []
    
    if data_source.has_headers:
        # Если есть заголовки, используем CSVColumn
        csv_columns = data_source.csv_columns.all().order_by('column_number')
        for col in csv_columns:
            columns.append({
                'number': col.column_number,
                'name': col.column_name,
                'type': col.data_type or 'text',
                'required': col.is_required
            })
    else:
        # Если нет заголовков, получаем из CSVData
        first_row_data = data_source.csv_data.filter(row_number=1).order_by('column_number')
        for i, data in enumerate(first_row_data, 1):
            columns.append({
                'number': i,
                'name': f'Столбец {i}',
                'type': 'text',
                'required': False
            })
    
    return JsonResponse({
        'data_source': {
            'id': data_source.id,
            'filename': data_source.filename,
            'has_headers': data_source.has_headers,
            'rows_count': data_source.rows_count,
            'columns_count': data_source.columns_count
        },
        'columns': columns
    })


@login_required
@require_http_methods(["GET"])
def get_template_fields(request, template_id):
    """
    API для получения полей шаблона
    """
    template = get_object_or_404(LabelTemplate, id=template_id, is_active=True)
    fields = template.fields.all().order_by('y_position', 'x_position')
    
    fields_data = []
    for field in fields:
        fields_data.append({
            'id': field.id,
            'name': field.field_name,
            'type': field.field_type,
            'x': field.x_position,
            'y': field.y_position,
            'width': field.width,
            'height': field.height,
            'font_size': field.font_size,
            'font_family': field.font_family,
            'is_bold': field.is_bold,
            'is_italic': field.is_italic,
            'alignment': field.alignment,
            'default_value': field.default_value,
            'is_required': field.is_required,
            'description': field.description
        })
    
    return JsonResponse({
        'template': {
            'id': template.id,
            'name': template.name,
            'type': template.template_type,
            'print_width_mm': template.print_width_mm,
            'print_height_mm': template.print_height_mm,
            'layout_width_mm': template.layout_width_mm,
            'layout_height_mm': template.layout_height_mm,
            'dpi': template.dpi
        },
        'fields': fields_data
    })


@login_required
@require_http_methods(["GET"])
def get_generation_progress(request, generation_id):
    """
    API для получения прогресса генерации
    """
    generation = get_object_or_404(
        LabelGeneration, 
        id=generation_id, 
        created_by=request.user
    )
    
    return JsonResponse({
        'id': generation.id,
        'status': generation.status,
        'progress_percent': generation.progress_percent,
        'total_labels': generation.total_labels,
        'generated_labels': generation.generated_labels,
        'is_completed': generation.is_completed,
        'is_failed': generation.is_failed,
        'is_processing': generation.is_processing,
        'error_message': generation.error_message
    })


@login_required
def create_generation(request):
    """
    Создание новой генерации этикеток
    """
    if request.method == 'GET':
        # Показываем форму создания генерации
        data_sources = CSVUploadLog.objects.filter(
            status='completed',
            author=request.user
        ).order_by('-upload_date')
        
        templates = LabelTemplate.objects.filter(
            is_active=True
        ).order_by('-created_at')
        
        context = {
            'data_sources': data_sources,
            'templates': templates,
            'title': 'Создание генерации этикеток'
        }
        return render(request, 'label_generator/create_generation.html', context)
    
    elif request.method == 'POST':
        # Здесь будет логика создания генерации
        # Пока возвращаем заглушку
        return JsonResponse({
            'status': 'success',
            'message': 'Создание генерации будет реализовано в следующих версиях'
        })


@login_required
def download_generated_file(request, generation_id):
    """
    Скачивание сгенерированного файла
    """
    from django.http import HttpResponse
    from django.utils.encoding import smart_str
    import os
    
    generation = get_object_or_404(
        LabelGeneration, 
        id=generation_id, 
        created_by=request.user
    )
    
    if not generation.output_file:
        raise Http404("Файл генерации не найден")
    
    if not os.path.exists(generation.output_file.path):
        raise Http404("Файл не найден на диске")
    
    try:
        with open(generation.output_file.path, 'rb') as file:
            response = HttpResponse(
                file.read(),
                content_type='application/pdf'
            )
            filename = smart_str(f"labels_{generation.name}_{generation.id}.pdf")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = os.path.getsize(generation.output_file.path)
            return response
    except IOError:
        raise Http404("Ошибка при чтении файла")


@login_required
def generation_logs(request, generation_id):
    """
    Просмотр логов генерации
    """
    generation = get_object_or_404(
        LabelGeneration, 
        id=generation_id, 
        created_by=request.user
    )
    
    logs = generation.logs.all().order_by('-timestamp')
    
    context = {
        'generation': generation,
        'logs': logs,
        'title': f'Логи генерации: {generation.name}'
    }
    return render(request, 'label_generator/generation_logs.html', context)
