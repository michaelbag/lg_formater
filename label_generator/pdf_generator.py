import os
import io
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.platypus.flowables import Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage
import fitz  # PyMuPDF
from pystrich.datamatrix import DataMatrixEncoder

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import LabelGeneration, FieldMapping, GenerationLog
from data_sources.models import CSVData
from label_templates.models import LabelTemplate, TemplateField


class LabelPDFGenerator:
    """
    Класс для генерации PDF файлов с этикетками
    """
    
    def __init__(self, generation: LabelGeneration):
        self.generation = generation
        self.template = generation.template
        self.data_source = generation.data_source
        self.field_mappings = generation.field_mappings.all().order_by('order')
        
        # Размеры страницы в миллиметрах
        self.page_width_mm = self.template.layout_width_mm
        self.page_height_mm = self.template.layout_height_mm
        
        # Размеры области печати в миллиметрах
        self.print_width_mm = self.template.print_width_mm
        self.print_height_mm = self.template.print_height_mm
        
        # Отступы в миллиметрах
        self.margin_left_mm = self.template.margin_left_mm
        self.margin_top_mm = self.template.margin_top_mm
        
        # DPI для конвертации
        self.dpi = self.template.dpi
        
        # Конвертация в точки (1 мм = 2.834645669 точек)
        self.mm_to_points = 2.834645669
        
        # Размеры в точках
        self.page_width = self.page_width_mm * self.mm_to_points
        self.page_height = self.page_height_mm * self.mm_to_points
        self.print_width = self.print_width_mm * self.mm_to_points
        self.print_height = self.print_height_mm * self.mm_to_points
        self.margin_left = self.margin_left_mm * self.mm_to_points
        self.margin_top = self.margin_top_mm * self.mm_to_points
        
        # Стили текста
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        
        # Данные для генерации
        self.csv_data = []
        self.template_background = None
        
    def _setup_styles(self):
        """Настройка стилей текста"""
        # Базовый стиль для текста
        self.text_style = ParagraphStyle(
            'CustomText',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Helvetica'
        )
        
        # Стиль для заголовков
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=14,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        )
    
    def _load_template_background(self):
        """Загрузка фонового изображения шаблона"""
        if self.template.template_file and os.path.exists(self.template.template_file.path):
            try:
                if self.template.template_type == 'pdf':
                    # Для PDF используем PyMuPDF
                    doc = fitz.open(self.template.template_file.path)
                    page = doc[0]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Увеличиваем разрешение
                    img_data = pix.tobytes("png")
                    self.template_background = ImageReader(io.BytesIO(img_data))
                else:
                    # Для изображений используем PIL
                    pil_image = PILImage.open(self.template.template_file.path)
                    # Конвертируем в RGB если нужно
                    if pil_image.mode != 'RGB':
                        pil_image = pil_image.convert('RGB')
                    img_data = io.BytesIO()
                    pil_image.save(img_data, format='PNG')
                    img_data.seek(0)
                    self.template_background = ImageReader(img_data)
            except Exception as e:
                self._log_error(f"Ошибка загрузки фонового изображения: {e}")
                self.template_background = None
    
    def _load_csv_data(self):
        """Загрузка данных из CSV"""
        try:
            # Получаем диапазон строк для обработки
            start_row = self.generation.start_row
            end_row = self.generation.end_row or self.data_source.rows_count
            
            # Загружаем данные
            csv_data_objects = CSVData.objects.filter(
                upload_log=self.data_source,
                row_number__gte=start_row,
                row_number__lte=end_row
            ).order_by('row_number', 'column_number')
            
            # Группируем по строкам
            current_row = None
            current_row_data = {}
            
            for data_obj in csv_data_objects:
                if current_row != data_obj.row_number:
                    if current_row is not None:
                        self.csv_data.append(current_row_data)
                    current_row = data_obj.row_number
                    current_row_data = {}
                
                current_row_data[data_obj.column_number] = data_obj.cell_value
            
            # Добавляем последнюю строку
            if current_row is not None:
                self.csv_data.append(current_row_data)
                
            self._log_info(f"Загружено {len(self.csv_data)} строк данных")
            
        except Exception as e:
            self._log_error(f"Ошибка загрузки данных CSV: {e}")
            raise
    
    def _get_field_value(self, field_mapping: FieldMapping, row_data: Dict[int, str]) -> str:
        """Получение значения поля из данных строки"""
        column_number = field_mapping.data_column_number
        
        # Получаем значение из данных
        value = row_data.get(column_number, '')
        
        # Если значение пустое, используем значение по умолчанию
        if not value and field_mapping.default_value:
            value = field_mapping.default_value
        
        # Применяем форматирование если задано
        if field_mapping.format_string and value:
            try:
                if field_mapping.format_string.startswith('date:'):
                    # Форматирование даты
                    date_format = field_mapping.format_string[5:]
                    from dateutil import parser
                    parsed_date = parser.parse(value)
                    value = parsed_date.strftime(date_format)
                elif field_mapping.format_string.startswith('number:'):
                    # Форматирование числа
                    number_format = field_mapping.format_string[7:]
                    value = f"{float(value):{number_format}}"
                elif field_mapping.format_string.startswith('text:'):
                    # Форматирование текста
                    text_format = field_mapping.format_string[5:]
                    value = text_format.format(value=value)
            except Exception as e:
                self._log_warning(f"Ошибка форматирования поля {field_mapping.template_field.field_name}: {e}")
        
        return str(value) if value else ''
    
    def _create_label_content(self, row_data: Dict[int, str]) -> List[Flowable]:
        """Создание содержимого одной этикетки"""
        content = []
        
        # Добавляем фоновое изображение если есть
        if self.template_background:
            try:
                # Создаем изображение с размерами области печати
                background_img = Image(
                    self.template_background,
                    width=self.print_width,
                    height=self.print_height
                )
                content.append(background_img)
            except Exception as e:
                self._log_warning(f"Ошибка добавления фонового изображения: {e}")
        
        # Добавляем поля данных
        for field_mapping in self.field_mappings:
            field = field_mapping.template_field
            value = self._get_field_value(field_mapping, row_data)
            
            if not value and field_mapping.is_required:
                self._log_warning(f"Обязательное поле {field.field_name} не заполнено")
                continue
            
            if value:
                # Позиционируем поле
                # Конвертируем позицию из миллиметров в точки
                x = (field.x_position or 0) * self.mm_to_points
                y = (field.y_position or 0) * self.mm_to_points
                
                # Обрабатываем разные типы полей
                if field.field_type == 'datamatrix':
                    # Создаем DataMatrix код
                    width = int(field.width * self.mm_to_points) if field.width else 100
                    height = int(field.height * self.mm_to_points) if field.height else 100
                    
                    datamatrix_image = self._create_datamatrix_image(value, width, height)
                    if datamatrix_image:
                        positioned_image = self._create_positioned_flowable(
                            datamatrix_image, x, y, width, height
                        )
                        content.append(positioned_image)
                else:
                    # Создаем стиль для текстового поля
                    field_style = ParagraphStyle(
                        f'Field_{field.id}',
                        parent=self.text_style,
                        fontSize=field.font_size or 10,
                        leading=(field.font_size or 10) * 1.2,
                        alignment={'left': TA_LEFT, 'center': TA_CENTER, 'right': TA_RIGHT, 'justify': TA_JUSTIFY}.get(field.alignment, TA_LEFT) if field.alignment else TA_LEFT,
                        textColor=colors.black,
                        fontName='Helvetica-Bold' if field.is_bold else 'Helvetica'
                    )
                    
                    # Создаем параграф с текстом
                    paragraph = Paragraph(value, field_style)
                    
                    # Создаем контейнер с позиционированием
                    positioned_paragraph = self._create_positioned_flowable(
                        paragraph, x, y, 
                        field.width * self.mm_to_points if field.width else None,
                        field.height * self.mm_to_points if field.height else None
                    )
                    
                    content.append(positioned_paragraph)
        
        return content
    
    def _create_datamatrix_image(self, data: str, width: int, height: int) -> Optional[Image]:
        """
        Создание DataMatrix кода в виде изображения
        """
        try:
            # Создаем DataMatrix код
            encoder = DataMatrixEncoder(data)
            encoder.width = width
            encoder.height = height
            
            # Получаем данные изображения DataMatrix
            img_data = encoder.get_imagedata()
            
            # Создаем BytesIO для обработки данных
            img_buffer = io.BytesIO(img_data)
            
            # Создаем Image для ReportLab
            return Image(img_buffer, width=width, height=height)
            
        except Exception as e:
            self._log_error(f"Ошибка создания DataMatrix: {e}")
            return None
    
    def _create_positioned_flowable(self, flowable: Flowable, x: float, y: float, 
                                  width: Optional[float] = None, height: Optional[float] = None) -> Flowable:
        """Создание позиционированного элемента"""
        class PositionedFlowable(Flowable):
            def __init__(self, flowable, x, y, width=None, height=None):
                self.flowable = flowable
                self.x = x
                self.y = y
                self.width = width
                self.height = height
            
            def draw(self):
                self.canv.saveState()
                self.canv.translate(self.x, self.y)
                if self.width and self.height:
                    self.canv.rect(0, 0, self.width, self.height, fill=0, stroke=0)
                
                # Для ReportLab 4.x используем правильный метод
                try:
                    # Пытаемся использовать drawOn для совместимости
                    self.flowable.drawOn(self.canv, 0, 0)
                except AttributeError:
                    # Если drawOn не работает, используем альтернативный подход
                    if hasattr(self.flowable, 'wrap'):
                        w, h = self.flowable.wrap(self.width or 100, self.height or 100)
                        self.flowable.drawOn(self.canv, 0, 0, w, h)
                    else:
                        # Для простых элементов используем прямой вызов draw
                        self.flowable.draw()
                
                self.canv.restoreState()
            
            def wrap(self, availWidth, availHeight):
                if hasattr(self.flowable, 'wrap'):
                    return self.flowable.wrap(availWidth, availHeight)
                return self.width or availWidth, self.height or availHeight
        
        return PositionedFlowable(flowable, x, y, width, height)
    
    def _log_info(self, message: str, row_number: Optional[int] = None):
        """Логирование информационного сообщения"""
        GenerationLog.objects.create(
            generation=self.generation,
            level='info',
            message=message,
            row_number=row_number
        )
    
    def _log_warning(self, message: str, row_number: Optional[int] = None):
        """Логирование предупреждения"""
        GenerationLog.objects.create(
            generation=self.generation,
            level='warning',
            message=message,
            row_number=row_number
        )
    
    def _log_error(self, message: str, row_number: Optional[int] = None):
        """Логирование ошибки"""
        GenerationLog.objects.create(
            generation=self.generation,
            level='error',
            message=message,
            row_number=row_number
        )
    
    def generate_pdf(self) -> str:
        """Генерация PDF файла с этикетками"""
        try:
            # Обновляем статус
            self.generation.status = 'processing'
            self.generation.started_at = timezone.now()
            self.generation.save()
            
            self._log_info("Начало генерации PDF")
            
            # Загружаем данные и шаблон
            self._load_csv_data()
            self._load_template_background()
            
            # Создаем временный файл
            temp_file = io.BytesIO()
            
            # Создаем PDF документ
            doc = SimpleDocTemplate(
                temp_file,
                pagesize=(self.page_width, self.page_height),
                leftMargin=0,
                rightMargin=0,
                topMargin=0,
                bottomMargin=0
            )
            
            # Собираем содержимое
            story = []
            labels_per_page = self.generation.labels_per_page
            labels_on_current_page = 0
            
            total_labels = len(self.csv_data)
            self.generation.total_labels = total_labels
            self.generation.save()
            
            for i, row_data in enumerate(self.csv_data):
                try:
                    # Создаем содержимое этикетки
                    label_content = self._create_label_content(row_data)
                    
                    # Добавляем содержимое на страницу
                    for item in label_content:
                        story.append(item)
                    
                    labels_on_current_page += 1
                    
                    # Если достигли лимита этикеток на страницу, добавляем разрыв страницы
                    if labels_on_current_page >= labels_per_page and i < total_labels - 1:
                        story.append(PageBreak())
                        labels_on_current_page = 0
                    
                    # Обновляем прогресс
                    if (i + 1) % 10 == 0 or i == total_labels - 1:
                        self.generation.update_progress(i + 1, total_labels)
                        self._log_info(f"Обработано {i + 1} из {total_labels} этикеток")
                
                except Exception as e:
                    self._log_error(f"Ошибка обработки строки {i + 1}: {e}")
                    continue
            
            # Строим PDF
            self._log_info("Создание PDF документа")
            doc.build(story)
            
            # Сохраняем файл
            temp_file.seek(0)
            filename = f"labels_{self.generation.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Создаем ContentFile
            pdf_content = ContentFile(temp_file.getvalue(), name=filename)
            
            # Сохраняем в модель
            self.generation.output_file = pdf_content
            self.generation.status = 'completed'
            self.generation.completed_at = timezone.now()
            self.generation.progress_percent = 100
            self.generation.save()
            
            self._log_info(f"Генерация завершена. Создан файл: {filename}")
            
            return filename
            
        except Exception as e:
            self.generation.status = 'failed'
            self.generation.error_message = str(e)
            self.generation.completed_at = timezone.now()
            self.generation.save()
            
            self._log_error(f"Критическая ошибка генерации: {e}")
            raise
