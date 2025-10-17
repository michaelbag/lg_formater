import os
import io
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, BaseDocTemplate, PageTemplate, Frame
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
        
        # Конвертация в точки (1 мм = 2.834645669 точек)
        self.mm_to_points = 2.834645669
        
        # Размеры страницы в миллиметрах (используем A4)
        from reportlab.lib.pagesizes import A4
        self.page_width_mm = A4[0] / self.mm_to_points  # Конвертируем из точек в мм
        self.page_height_mm = A4[1] / self.mm_to_points
        
        # Размеры области печати в миллиметрах
        self.print_width_mm = self.template.print_width_mm
        self.print_height_mm = self.template.print_height_mm
        
        # Отступы в миллиметрах
        self.margin_left_mm = self.template.margin_left_mm
        self.margin_top_mm = self.template.margin_top_mm
        
        # DPI для конвертации
        self.dpi = self.template.dpi
        
        # Размеры в точках
        self.page_width = self.page_width_mm * self.mm_to_points
        self.page_height = self.page_height_mm * self.mm_to_points
        self.print_width = self.print_width_mm * self.mm_to_points
        self.print_height = self.print_height_mm * self.mm_to_points
        self.layout_width = self.template.layout_width_mm * self.mm_to_points
        self.layout_height = self.template.layout_height_mm * self.mm_to_points
        self.margin_left = self.margin_left_mm * self.mm_to_points
        self.margin_top = self.margin_top_mm * self.mm_to_points
        
        # Стили текста
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        
        # Данные для генерации
        self.csv_data = []
        self.template_background = None
        self.template_background_type = None
        
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
                    # Для PDF сохраняем путь к файлу для векторного рендеринга
                    self.template_background = self.template.template_file.path
                    self.template_background_type = 'pdf'
                else:
                    # Для изображений используем PIL
                    pil_image = PILImage.open(self.template.template_file.path)
                    # Конвертируем в RGB если нужно
                    if pil_image.mode != 'RGB':
                        pil_image = pil_image.convert('RGB')
                    img_data = io.BytesIO()
                    pil_image.save(img_data, format='PNG')
                    img_data.seek(0)
                    # Сохраняем данные изображения для использования в Image()
                    self.template_background = img_data
                    self.template_background_type = 'image'
            except Exception as e:
                self._log_error(f"Ошибка загрузки фонового изображения: {e}")
                self.template_background = None
                self.template_background_type = None
    
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
    
    def _create_custom_doc_template(self, temp_file, page_size):
        """Создание кастомного шаблона документа без отступов"""
        
        class CustomDocTemplate(BaseDocTemplate):
            def __init__(self, filename, pagesize, **kwargs):
                BaseDocTemplate.__init__(self, filename, pagesize=pagesize, **kwargs)
                
                # Создаем фрейм без отступов
                frame = Frame(
                    0, 0, pagesize[0], pagesize[1],
                    leftPadding=0,
                    rightPadding=0,
                    topPadding=0,
                    bottomPadding=0
                )
                
                # Создаем шаблон страницы
                template = PageTemplate('normal', [frame])
                self.addPageTemplates([template])
        
        return CustomDocTemplate(temp_file, page_size)
    
    def _create_page_content(self, row_data: Dict[int, str]) -> List[Flowable]:
        """Создание содержимого одной страницы"""
        content = []
        
        # Добавляем фоновое изображение если есть
        if self.template_background:
            try:
                # Создаем фоновое изображение с пропорциональным масштабированием
                background_img = self._create_scaled_background_image()
                if background_img:
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
    
    def _create_scaled_background_image(self) -> Optional[Flowable]:
        """
        Создание фонового изображения с пропорциональным масштабированием
        Максимально вписывает изображение в размеры страницы из шаблона
        """
        if not self.template_background:
            return None
        
        try:
            # Используем размеры страницы из шаблона
            target_width_pt = self.layout_width
            target_height_pt = self.layout_height
            
            if self.template_background_type == 'pdf':
                # Для PDF создаем векторный элемент
                return self._create_vector_pdf_background(target_width_pt, target_height_pt)
            else:
                # Для изображений используем растровый подход
                return self._create_raster_background(target_width_pt, target_height_pt)
                
        except Exception as e:
            self._log_error(f"Ошибка создания масштабированного фонового изображения: {e}")
            return None
    
    def _create_vector_pdf_background(self, target_width_pt: float, target_height_pt: float) -> Flowable:
        """
        Создание векторного фонового PDF элемента
        """
        class VectorPDFBackground(Flowable):
            def __init__(self, pdf_path, target_width, target_height, generator):
                self.pdf_path = pdf_path
                self.target_width = target_width
                self.target_height = target_height
                self.generator = generator
                
                # Получаем размеры исходного PDF
                doc = fitz.open(pdf_path)
                page = doc[0]
                rect = page.rect
                doc.close()
                
                self.original_width = rect.width
                self.original_height = rect.height
                
                # Вычисляем коэффициенты масштабирования
                scale_x = target_width / self.original_width
                scale_y = target_height / self.original_height
                self.scale = min(scale_x, scale_y)
                
                # Вычисляем новые размеры
                self.new_width = self.original_width * self.scale
                self.new_height = self.original_height * self.scale
                
                # Вычисляем позицию для центрирования
                self.x_offset = (target_width - self.new_width) / 2
                self.y_offset = (target_height - self.new_height) / 2
                
                # Устанавливаем размеры для ReportLab
                self.width = target_width
                self.height = target_height
            
            def draw(self):
                try:
                    # Открываем PDF
                    doc = fitz.open(self.pdf_path)
                    page = doc[0]
                    
                    # Создаем матрицу трансформации
                    matrix = fitz.Matrix(self.scale, self.scale)
                    
                    # Получаем векторные данные страницы
                    page_dict = page.get_drawings()
                    
                    # Рисуем векторные элементы
                    for item in page_dict:
                        if item['type'] == 'path':
                            # Рисуем пути
                            self.canv.saveState()
                            self.canv.translate(self.x_offset, self.y_offset)
                            
                            # Применяем трансформацию
                            if 'transform' in item:
                                transform = item['transform']
                                self.canv.transform(transform[0], transform[1], transform[2], 
                                                  transform[3], transform[4], transform[5])
                            
                            # Рисуем путь
                            if 'items' in item:
                                for path_item in item['items']:
                                    if path_item[0] == 'm':  # moveTo
                                        self.canv.moveTo(path_item[1], path_item[2])
                                    elif path_item[0] == 'l':  # lineTo
                                        self.canv.lineTo(path_item[1], path_item[2])
                                    elif path_item[0] == 'c':  # curveTo
                                        self.canv.curveTo(path_item[1], path_item[2], 
                                                        path_item[3], path_item[4],
                                                        path_item[5], path_item[6])
                                    elif path_item[0] == 'h':  # closePath
                                        self.canv.closePath()
                            
                            # Применяем стили
                            if 'fill' in item and item['fill']:
                                self.canv.setFillColor(item['fill'])
                                self.canv.fill()
                            if 'stroke' in item and item['stroke']:
                                self.canv.setStrokeColor(item['stroke'])
                                self.canv.stroke()
                            
                            self.canv.restoreState()
                    
                    doc.close()
                    
                except Exception as e:
                    # Если векторный рендеринг не удался, используем растровый
                    self.generator._log_warning(f"Векторный рендеринг не удался, используем растровый: {e}")
                    self._draw_raster_fallback()
            
            def _draw_raster_fallback(self):
                """Fallback на растровый рендеринг"""
                try:
                    doc = fitz.open(self.pdf_path)
                    page = doc[0]
                    
                    # Создаем высококачественное растровое изображение
                    matrix = fitz.Matrix(3, 3)  # Высокое разрешение
                    pix = page.get_pixmap(matrix=matrix)
                    img_data = pix.tobytes("png")
                    
                    # Создаем изображение
                    img_buffer = io.BytesIO(img_data)
                    img = Image(img_buffer, width=self.new_width, height=self.new_height)
                    
                    # Рисуем изображение
                    self.canv.saveState()
                    self.canv.translate(self.x_offset, self.y_offset)
                    img.drawOn(self.canv, 0, 0)
                    self.canv.restoreState()
                    
                    doc.close()
                    
                except Exception as e:
                    self.generator._log_error(f"Ошибка растрового fallback: {e}")
        
        return VectorPDFBackground(self.template_background, target_width_pt, target_height_pt, self)
    
    def _create_raster_background(self, target_width_pt: float, target_height_pt: float) -> Image:
        """
        Создание растрового фонового изображения
        """
        # Получаем размеры исходного изображения в пикселях
        with PILImage.open(self.template_background) as img:
            original_width_px, original_height_px = img.size
            
            # Вычисляем коэффициенты масштабирования
            scale_x = target_width_pt / original_width_px
            scale_y = target_height_pt / original_height_px
            
            # Используем минимальный коэффициент для пропорционального масштабирования
            scale = min(scale_x, scale_y)
            
            # Вычисляем новые размеры в пикселях
            new_width_px = int(original_width_px * scale)
            new_height_px = int(original_height_px * scale)
            
            # Вычисляем позицию для центрирования в пикселях
            x_offset_px = int((target_width_pt - new_width_px) / 2)
            y_offset_px = int((target_height_pt - new_height_px) / 2)
            
            # Создаем изображение с новыми размерами
            resized_img = img.resize((new_width_px, new_height_px), PILImage.Resampling.LANCZOS)
            
            # Создаем белый фон с размерами области печати
            background = PILImage.new('RGB', (int(target_width_pt), int(target_height_pt)), 'white')
            
            # Вставляем масштабированное изображение в центр
            background.paste(resized_img, (x_offset_px, y_offset_px))
            
            # Конвертируем в байты
            img_buffer = io.BytesIO()
            background.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Создаем Image для ReportLab с размерами в точках
            return Image(img_buffer, width=target_width_pt, height=target_height_pt)
    
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
            
            # Определяем размер страницы из шаблона
            page_size = (self.layout_width, self.layout_height)
            
            # Создаем кастомный PDF документ без отступов
            doc = self._create_custom_doc_template(temp_file, page_size)
            
            # Собираем содержимое
            story = []
            
            total_labels = len(self.csv_data)
            self.generation.total_labels = total_labels
            self.generation.save()
            
            # Обрабатываем каждую строку данных как отдельную страницу
            for i, row_data in enumerate(self.csv_data):
                try:
                    # Создаем содержимое страницы
                    page_content = self._create_page_content(row_data)
                    
                    # Добавляем содержимое на страницу
                    for item in page_content:
                        story.append(item)
                    
                    # Добавляем разрыв страницы (кроме последней)
                    if i < total_labels - 1:
                        story.append(PageBreak())
                    
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
