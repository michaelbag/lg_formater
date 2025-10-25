from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.encoding import smart_str
from django.views.decorators.http import require_http_methods
from .models import LabelTemplate, TemplateField, TemplateUsage
from data_sources.models import DataUploadLog, DataRecord
import os


@login_required
def template_list(request):
    """
    Список доступных шаблонов этикеток
    """
    templates = LabelTemplate.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'templates': templates,
        'title': 'Шаблоны этикеток'
    }
    return render(request, 'label_templates/template_list.html', context)


@login_required
def template_detail(request, template_id):
    """
    Детальная информация о шаблоне
    """
    template = get_object_or_404(LabelTemplate, id=template_id, is_active=True)
    fields = template.fields.all().order_by('y_position', 'x_position')
    
    context = {
        'template': template,
        'fields': fields,
        'title': f'Шаблон: {template.name}'
    }
    return render(request, 'label_templates/template_detail.html', context)


@login_required
def download_template(request, template_id):
    """
    Скачивание файла шаблона
    """
    template = get_object_or_404(LabelTemplate, id=template_id)
    
    # Проверяем права доступа
    if not (request.user == template.created_by or request.user.is_superuser):
        raise Http404("У вас нет прав для скачивания этого шаблона")
    
    # Проверяем, что файл существует
    if not template.template_file:
        raise Http404("Этот шаблон не содержит файла (шаблон с чистого листа)")
    
    # Проверяем, что файл физически существует
    if not os.path.exists(template.template_file.path):
        raise Http404("Файл шаблона не найден на диске")
    
    try:
        with open(template.template_file.path, 'rb') as file:
            response = HttpResponse(
                file.read(),
                content_type='application/octet-stream'
            )
            
            # Устанавливаем заголовки для скачивания
            filename = smart_str(f"{template.name}{template.file_extension}")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = os.path.getsize(template.template_file.path)
            
            return response
            
    except IOError:
        raise Http404("Ошибка при чтении файла шаблона")


@login_required
@require_http_methods(["GET"])
def get_template_fields(request, template_id):
    """
    API для получения полей шаблона в JSON формате
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
            'margin_top_mm': template.margin_top_mm,
            'margin_bottom_mm': template.margin_bottom_mm,
            'margin_left_mm': template.margin_left_mm,
            'margin_right_mm': template.margin_right_mm,
            'dpi': template.dpi
        },
        'fields': fields_data
    })


@login_required
@require_http_methods(["GET"])
def get_data_source_columns(request, data_source_id):
    """
    API для получения столбцов из источника данных
    """
    data_source = get_object_or_404(DataUploadLog, id=data_source_id)
    
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
def generate_labels(request):
    """
    Генерация этикеток на основе шаблона и данных
    """
    if request.method == 'GET':
        # Показываем форму выбора шаблона и источника данных
        templates = LabelTemplate.objects.filter(is_active=True)
        data_sources = DataUploadLog.objects.filter(
            status='completed',
            author=request.user
        ).order_by('-upload_date')
        
        context = {
            'templates': templates,
            'data_sources': data_sources,
            'title': 'Генерация этикеток'
        }
        return render(request, 'label_templates/generate_labels.html', context)
    
    elif request.method == 'POST':
        # Здесь будет логика генерации этикеток
        # Пока возвращаем заглушку
        return JsonResponse({
            'status': 'success',
            'message': 'Генерация этикеток будет реализована в следующих версиях'
        })


@login_required
def usage_history(request):
    """
    История использования шаблонов
    """
    usage_logs = TemplateUsage.objects.filter(
        generated_by=request.user
    ).order_by('-generated_at')
    
    context = {
        'usage_logs': usage_logs,
        'title': 'История генерации этикеток'
    }
    return render(request, 'label_templates/usage_history.html', context)
