from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import os
from PIL import Image
import fitz  # PyMuPDF для PDF файлов


def template_upload_path(instance, filename):
    """
    Генерирует путь для сохранения файлов шаблонов
    Формат: templates/YYYY/MM/DD/filename
    """
    from django.utils import timezone
    date = instance.created_at or timezone.now()
    return f'templates/{date.year}/{date.month:02d}/{date.day:02d}/{filename}'


class LabelTemplate(models.Model):
    """
    Модель для хранения шаблонов этикеток
    """
    TEMPLATE_TYPES = [
        ('pdf', 'PDF'),
        ('jpeg', 'JPEG'),
        ('png', 'PNG'),
        ('svg', 'SVG'),
        ('docx', 'Word Document'),
    ]
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название шаблона",
        help_text="Уникальное название шаблона этикетки"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание",
        help_text="Подробное описание назначения шаблона"
    )
    template_type = models.CharField(
        max_length=10,
        choices=TEMPLATE_TYPES,
        verbose_name="Тип шаблона",
        help_text="Формат файла шаблона"
    )
    template_file = models.FileField(
        upload_to=template_upload_path,
        blank=True,
        null=True,
        verbose_name="Файл шаблона",
        help_text="Файл шаблона этикетки (необязательно - можно создать шаблон без файла)"
    )
    preview_image = models.ImageField(
        upload_to=template_upload_path,
        blank=True,
        null=True,
        verbose_name="Превью изображение",
        help_text="Превью шаблона для отображения в интерфейсе"
    )
    # Область печати (основные размеры этикетки)
    print_width_mm = models.PositiveIntegerField(
        default=100,
        verbose_name="Ширина области печати (мм)",
        help_text="Ширина области печати в миллиметрах"
    )
    print_height_mm = models.PositiveIntegerField(
        default=50,
        verbose_name="Высота области печати (мм)",
        help_text="Высота области печати в миллиметрах"
    )
    
    # Область макета (под обрез)
    layout_width_mm = models.PositiveIntegerField(
        default=100,
        verbose_name="Ширина области макета (мм)",
        help_text="Ширина области макета (под обрез) в миллиметрах"
    )
    layout_height_mm = models.PositiveIntegerField(
        default=50,
        verbose_name="Высота области макета (мм)",
        help_text="Высота области макета (под обрез) в миллиметрах"
    )
    
    # Отступы от края макета до области печати
    margin_top_mm = models.PositiveIntegerField(
        default=0,
        verbose_name="Отступ сверху (мм)",
        help_text="Отступ от верхнего края макета до области печати"
    )
    margin_bottom_mm = models.PositiveIntegerField(
        default=0,
        verbose_name="Отступ снизу (мм)",
        help_text="Отступ от нижнего края макета до области печати"
    )
    margin_left_mm = models.PositiveIntegerField(
        default=0,
        verbose_name="Отступ слева (мм)",
        help_text="Отступ от левого края макета до области печати"
    )
    margin_right_mm = models.PositiveIntegerField(
        default=0,
        verbose_name="Отступ справа (мм)",
        help_text="Отступ от правого края макета до области печати"
    )
    dpi = models.PositiveIntegerField(
        default=300,
        verbose_name="DPI",
        help_text="Разрешение печати (точек на дюйм)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активный",
        help_text="Доступен ли шаблон для использования"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Создатель",
        help_text="Пользователь, создавший шаблон"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        help_text="Дата и время создания шаблона"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
        help_text="Дата и время последнего обновления"
    )

    class Meta:
        verbose_name = "Шаблон этикетки"
        verbose_name_plural = "Шаблоны этикеток"
        ordering = ['-created_at']
        unique_together = ['name', 'created_by']

    def __str__(self):
        return f"{self.name} ({self.template_type.upper()})"

    @property
    def file_size(self):
        """Возвращает размер файла в байтах"""
        if self.template_file:
            try:
                return self.template_file.size
            except (OSError, ValueError):
                return 0
        return 0

    @property
    def file_extension(self):
        """Возвращает расширение файла"""
        if self.template_file:
            return os.path.splitext(self.template_file.name)[1].lower()
        return ''

    @property
    def is_blank_template(self):
        """Возвращает True, если это шаблон без файла (с чистого листа)"""
        return not bool(self.template_file)

    @property
    def template_type_display(self):
        """Возвращает отображаемый тип шаблона"""
        if self.is_blank_template:
            return f"Чистый лист ({self.template_type.upper()})"
        return self.get_template_type_display()

    def get_image_dimensions(self, file_path):
        """
        Получает размеры изображения в пикселях
        """
        try:
            with Image.open(file_path) as img:
                return img.size  # (width, height)
        except Exception as e:
            raise ValidationError(f"Ошибка при чтении изображения: {e}")

    def get_pdf_dimensions(self, file_path):
        """
        Получает размеры PDF страницы в пикселях
        """
        try:
            doc = fitz.open(file_path)
            page = doc[0]  # Первая страница
            rect = page.rect
            doc.close()
            return (int(rect.width), int(rect.height))
        except Exception as e:
            raise ValidationError(f"Ошибка при чтении PDF: {e}")

    def pixels_to_mm(self, pixels, dpi):
        """
        Конвертирует пиксели в миллиметры
        """
        # 1 дюйм = 25.4 мм
        return int(pixels * 25.4 / dpi)

    def auto_detect_dimensions(self):
        """
        Автоматически определяет размеры шаблона на основе файла
        Если файла нет, оставляет размеры как есть
        """
        if not self.template_file or not os.path.exists(self.template_file.path):
            # Если файла нет, это шаблон "с чистого листа"
            # Размеры должны быть заданы вручную
            return

        file_path = self.template_file.path
        file_ext = self.file_extension.lower()

        try:
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                width_px, height_px = self.get_image_dimensions(file_path)
            elif file_ext == '.pdf':
                width_px, height_px = self.get_pdf_dimensions(file_path)
            else:
                # Для других форматов используем значения по умолчанию
                return

            # Конвертируем в миллиметры
            width_mm = self.pixels_to_mm(width_px, self.dpi)
            height_mm = self.pixels_to_mm(height_px, self.dpi)

            # Устанавливаем размеры (при загрузке области печати и макета идентичны)
            self.print_width_mm = width_mm
            self.print_height_mm = height_mm
            self.layout_width_mm = width_mm
            self.layout_height_mm = height_mm

            # Сбрасываем отступы (при загрузке они равны 0)
            self.margin_top_mm = 0
            self.margin_bottom_mm = 0
            self.margin_left_mm = 0
            self.margin_right_mm = 0

        except Exception as e:
            raise ValidationError(f"Не удалось определить размеры файла: {e}")
    
    def auto_generate_name(self):
        """
        Автоматически генерирует название шаблона на основе имени файла и размеров
        """
        if not self.template_file:
            return
        
        # Получаем имя файла без расширения
        filename = os.path.splitext(os.path.basename(self.template_file.name))[0]
        
        # Добавляем размеры печатной области в скобках
        if self.print_width_mm and self.print_height_mm:
            dimensions = f"({self.print_width_mm}x{self.print_height_mm})"
            self.name = f"{filename} {dimensions}"
        else:
            self.name = filename

    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем, что область печати не больше области макета
        if (self.print_width_mm and self.layout_width_mm and 
            self.print_width_mm > self.layout_width_mm):
            raise ValidationError(
                "Ширина области печати не может быть больше ширины области макета"
            )
        
        if (self.print_height_mm and self.layout_height_mm and 
            self.print_height_mm > self.layout_height_mm):
            raise ValidationError(
                "Высота области печати не может быть больше высоты области макета"
            )

        # Проверяем отступы
        if (self.margin_left_mm and self.margin_right_mm and 
            self.layout_width_mm and self.print_width_mm):
            total_margins = self.margin_left_mm + self.margin_right_mm
            if total_margins + self.print_width_mm > self.layout_width_mm:
                raise ValidationError(
                    "Сумма отступов слева и справа плюс ширина области печати "
                    "не может превышать ширину области макета"
                )

        if (self.margin_top_mm and self.margin_bottom_mm and 
            self.layout_height_mm and self.print_height_mm):
            total_margins = self.margin_top_mm + self.margin_bottom_mm
            if total_margins + self.print_height_mm > self.layout_height_mm:
                raise ValidationError(
                    "Сумма отступов сверху и снизу плюс высота области печати "
                    "не может превышать высоту области макета"
                )

    def save(self, *args, **kwargs):
        """
        Переопределяем save для автоматического определения размеров и заполнения created_by
        """
        is_new = not self.pk
        
        # Если это новый объект и created_by не заполнен, пытаемся получить текущего пользователя
        if is_new and not self.created_by_id:
            # Проверяем, есть ли текущий пользователь в контексте
            if hasattr(self, '_current_user') and self._current_user:
                self.created_by = self._current_user
            else:
                # Если нет текущего пользователя, берем первого суперпользователя
                from django.contrib.auth import get_user_model
                User = get_user_model()
                superuser = User.objects.filter(is_superuser=True).first()
                if superuser:
                    self.created_by = superuser
        
        # Валидируем модель
        self.clean()
        
        # Сохраняем объект
        super().save(*args, **kwargs)
        
        # После сохранения, если это новый объект и есть файл, определяем размеры автоматически
        if is_new and self.template_file and os.path.exists(self.template_file.path):
            self.auto_detect_dimensions()
            
            # Если название не задано, генерируем название автоматически
            if not self.name:
                self.auto_generate_name()
            
            # Сохраняем еще раз с обновленными размерами и названием
            super().save(*args, **kwargs)


class TemplateField(models.Model):
    """
    Модель для хранения полей данных в шаблоне
    """
    FIELD_TYPES = [
        ('text', 'Текст'),
        ('number', 'Число'),
        ('date', 'Дата'),
        ('barcode', 'Штрих-код'),
        ('qr', 'QR-код'),
        ('datamatrix', 'DataMatrix (DS)'),
        ('image', 'Изображение'),
    ]
    
    template = models.ForeignKey(
        LabelTemplate,
        on_delete=models.CASCADE,
        related_name='fields',
        verbose_name="Шаблон",
        help_text="Шаблон, к которому относится поле"
    )
    field_name = models.CharField(
        max_length=100,
        verbose_name="Название поля",
        help_text="Уникальное название поля в шаблоне"
    )
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPES,
        default='text',
        verbose_name="Тип поля",
        help_text="Тип данных поля"
    )
    x_position = models.PositiveIntegerField(
        verbose_name="Позиция X (мм)",
        help_text="Горизонтальная позиция поля в миллиметрах"
    )
    y_position = models.PositiveIntegerField(
        verbose_name="Позиция Y (мм)",
        help_text="Вертикальная позиция поля в миллиметрах"
    )
    width = models.PositiveIntegerField(
        verbose_name="Ширина (мм)",
        help_text="Ширина поля в миллиметрах"
    )
    height = models.PositiveIntegerField(
        verbose_name="Высота (мм)",
        help_text="Высота поля в миллиметрах"
    )
    font_size = models.PositiveIntegerField(
        default=12,
        verbose_name="Размер шрифта",
        help_text="Размер шрифта для текстовых полей"
    )
    font_family = models.CharField(
        max_length=100,
        default='Arial',
        verbose_name="Шрифт",
        help_text="Название шрифта"
    )
    is_bold = models.BooleanField(
        default=False,
        verbose_name="Жирный",
        help_text="Жирное начертание текста"
    )
    is_italic = models.BooleanField(
        default=False,
        verbose_name="Курсив",
        help_text="Курсивное начертание текста"
    )
    alignment = models.CharField(
        max_length=10,
        choices=[
            ('left', 'По левому краю'),
            ('center', 'По центру'),
            ('right', 'По правому краю'),
        ],
        default='left',
        verbose_name="Выравнивание",
        help_text="Выравнивание текста в поле"
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Значение по умолчанию",
        help_text="Значение поля по умолчанию"
    )
    is_required = models.BooleanField(
        default=False,
        verbose_name="Обязательное",
        help_text="Обязательно ли заполнение поля"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание поля",
        help_text="Описание назначения поля"
    )

    class Meta:
        verbose_name = "Поле шаблона"
        verbose_name_plural = "Поля шаблонов"
        ordering = ['template', 'y_position', 'x_position']
        unique_together = ['template', 'field_name']

    def __str__(self):
        return f"{self.template.name} - {self.field_name} ({self.field_type})"


class TemplateUsage(models.Model):
    """
    Модель для отслеживания использования шаблонов
    """
    template = models.ForeignKey(
        LabelTemplate,
        on_delete=models.CASCADE,
        related_name='usage_logs',
        verbose_name="Шаблон",
        help_text="Использованный шаблон"
    )
    data_source = models.ForeignKey(
        'data_sources.DataUploadLog',
        on_delete=models.CASCADE,
        verbose_name="Источник данных",
        help_text="CSV файл с данными для генерации"
    )
    generated_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество сгенерированных",
        help_text="Количество сгенерированных этикеток"
    )
    generated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Сгенерировал",
        help_text="Пользователь, сгенерировавший этикетки"
    )
    generated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата генерации",
        help_text="Дата и время генерации этикеток"
    )
    output_file = models.FileField(
        upload_to='generated_labels/',
        blank=True,
        null=True,
        verbose_name="Результирующий файл",
        help_text="Сгенерированный файл с этикетками"
    )

    class Meta:
        verbose_name = "Использование шаблона"
        verbose_name_plural = "Использование шаблонов"
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.template.name} - {self.generated_count} этикеток ({self.generated_at.strftime('%d.%m.%Y %H:%M')})"
