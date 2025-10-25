from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


def generated_labels_upload_path(instance, filename):
    """
    Генерирует путь для сохранения сгенерированных этикеток
    Формат: generated_labels/YYYY/MM/DD/filename
    """
    date = instance.created_at
    return f'generated_labels/{date.year}/{date.month:02d}/{date.day:02d}/{filename}'


class LabelGeneration(models.Model):
    """
    Модель для журнала генерации этикеток
    """
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('processing', 'Обрабатывается'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
        ('cancelled', 'Отменено'),
    ]
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название генерации",
        help_text="Уникальное название для этой генерации этикеток"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание",
        help_text="Подробное описание генерации"
    )
    
    # Связи с источниками данных и шаблонами
    data_source = models.ForeignKey(
        'data_sources.DataUploadLog',
        on_delete=models.CASCADE,
        verbose_name="Источник данных",
        help_text="CSV файл с данными для генерации"
    )
    template = models.ForeignKey(
        'label_templates.LabelTemplate',
        on_delete=models.CASCADE,
        verbose_name="Шаблон",
        help_text="Шаблон этикетки для генерации"
    )
    
    # Параметры генерации
    start_row = models.PositiveIntegerField(
        default=1,
        verbose_name="Начальная строка",
        help_text="Номер строки, с которой начинать генерацию (1 - первая строка данных)"
    )
    end_row = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Конечная строка",
        help_text="Номер строки, на которой закончить генерацию (пусто - до конца)"
    )
    labels_per_page = models.PositiveIntegerField(
        default=1,
        verbose_name="Этикеток на страницу",
        help_text="Количество этикеток на одной странице"
    )
    
    # Статус и результаты
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус",
        help_text="Текущий статус генерации"
    )
    progress_percent = models.PositiveIntegerField(
        default=0,
        verbose_name="Прогресс (%)",
        help_text="Процент выполнения генерации"
    )
    total_labels = models.PositiveIntegerField(
        default=0,
        verbose_name="Всего этикеток",
        help_text="Общее количество этикеток для генерации"
    )
    generated_labels = models.PositiveIntegerField(
        default=0,
        verbose_name="Сгенерировано",
        help_text="Количество уже сгенерированных этикеток"
    )
    
    # Файлы результатов
    output_file = models.FileField(
        upload_to=generated_labels_upload_path,
        blank=True,
        null=True,
        verbose_name="Результирующий файл",
        help_text="Сгенерированный файл с этикетками"
    )
    log_file = models.FileField(
        upload_to=generated_labels_upload_path,
        blank=True,
        null=True,
        verbose_name="Файл лога",
        help_text="Файл с подробным логом генерации"
    )
    
    # Системная информация
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Создатель",
        help_text="Пользователь, создавший генерацию"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        help_text="Дата и время создания генерации"
    )
    started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата начала",
        help_text="Дата и время начала генерации"
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата завершения",
        help_text="Дата и время завершения генерации"
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name="Сообщение об ошибке",
        help_text="Описание ошибки, если генерация не удалась"
    )

    class Meta:
        verbose_name = "Генерация этикеток"
        verbose_name_plural = "Генерации этикеток"
        ordering = ['-created_at']
        unique_together = ['name', 'created_by']

    def __str__(self):
        return f"{self.name} - {self.get_status_display()} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"

    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем, что начальная строка не больше конечной
        if self.start_row and self.end_row and self.start_row > self.end_row:
            raise ValidationError("Начальная строка не может быть больше конечной")
        
        # Проверяем, что начальная строка не меньше 1
        if self.start_row and self.start_row < 1:
            raise ValidationError("Начальная строка должна быть больше 0")
        
        # Проверяем, что количество этикеток на страницу больше 0
        if self.labels_per_page and self.labels_per_page < 1:
            raise ValidationError("Количество этикеток на страницу должно быть больше 0")

    @property
    def is_completed(self):
        """Возвращает True, если генерация завершена"""
        return self.status == 'completed'

    @property
    def is_failed(self):
        """Возвращает True, если генерация завершилась с ошибкой"""
        return self.status == 'failed'

    @property
    def is_processing(self):
        """Возвращает True, если генерация выполняется"""
        return self.status == 'processing'

    def update_progress(self, generated_count, total_count):
        """
        Обновляет прогресс генерации
        """
        self.generated_labels = generated_count
        self.total_labels = total_count
        if total_count > 0:
            self.progress_percent = int((generated_count / total_count) * 100)
        else:
            self.progress_percent = 0
        self.save(update_fields=['generated_labels', 'total_labels', 'progress_percent'])

    def start_generation(self):
        """
        Запускает процесс генерации PDF
        """
        if self.status != 'pending':
            raise ValueError("Генерация может быть запущена только в статусе 'Ожидает'")
        
        # Проверяем наличие сопоставлений полей
        if not self.field_mappings.exists():
            raise ValueError("Не настроено сопоставление полей")
        
        # Проверяем источник данных
        if self.data_source.status != 'completed':
            raise ValueError("Источник данных не готов к использованию")
        
        # Проверяем шаблон
        if not self.template.is_active:
            raise ValueError("Шаблон неактивен")
        
        try:
            from .pdf_generator import LabelPDFGenerator
            generator = LabelPDFGenerator(self)
            filename = generator.generate_pdf()
            return filename
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.completed_at = timezone.now()
            self.save()
            raise

    def can_start_generation(self):
        """
        Проверяет, можно ли запустить генерацию
        """
        return (
            self.status == 'pending' and
            self.field_mappings.exists() and
            self.data_source.status == 'completed' and
            self.template.is_active
        )

    def get_generation_errors(self):
        """
        Возвращает список ошибок, препятствующих запуску генерации
        """
        errors = []
        
        if self.status != 'pending':
            errors.append(f"Статус должен быть 'Ожидает', текущий: {self.get_status_display()}")
        
        if not self.field_mappings.exists():
            errors.append("Не настроено сопоставление полей")
        
        if self.data_source.status != 'completed':
            errors.append(f"Источник данных не готов (статус: {self.data_source.get_status_display()})")
        
        if not self.template.is_active:
            errors.append("Шаблон неактивен")
        
        return errors


class FieldMapping(models.Model):
    """
    Модель для сопоставления полей источника данных с полями шаблона
    """
    generation = models.ForeignKey(
        LabelGeneration,
        on_delete=models.CASCADE,
        related_name='field_mappings',
        verbose_name="Генерация",
        help_text="Генерация, к которой относится сопоставление"
    )
    
    # Поле шаблона
    template_field = models.ForeignKey(
        'label_templates.TemplateField',
        on_delete=models.CASCADE,
        verbose_name="Поле шаблона",
        help_text="Поле в шаблоне этикетки"
    )
    
    # Источник данных
    data_column_number = models.PositiveIntegerField(
        verbose_name="Номер столбца данных",
        help_text="Номер столбца в CSV файле (начиная с 1)"
    )
    data_column_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Название столбца",
        help_text="Название столбца в CSV файле"
    )
    
    # Дополнительные настройки
    is_required = models.BooleanField(
        default=False,
        verbose_name="Обязательное поле",
        help_text="Обязательно ли заполнение этого поля"
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Значение по умолчанию",
        help_text="Значение по умолчанию, если данные отсутствуют"
    )
    format_string = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Формат данных",
        help_text="Формат для преобразования данных (например, для дат)"
    )
    
    # Порядок отображения
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок",
        help_text="Порядок отображения в интерфейсе"
    )

    class Meta:
        verbose_name = "Сопоставление полей"
        verbose_name_plural = "Сопоставления полей"
        ordering = ['generation', 'order', 'template_field']
        unique_together = ['generation', 'template_field']

    def __str__(self):
        return f"{self.generation.name} - {self.template_field.field_name} → Столбец {self.data_column_number}"

    def clean(self):
        """
        Валидация модели
        """
        super().clean()
        
        # Проверяем, что номер столбца больше 0
        if self.data_column_number and self.data_column_number < 1:
            raise ValidationError("Номер столбца должен быть больше 0")
        
        # Проверяем, что номер столбца не превышает количество столбцов в источнике данных
        if (self.generation and self.generation.data_source and 
            self.data_column_number and self.generation.data_source.columns_count and
            self.data_column_number > self.generation.data_source.columns_count):
            raise ValidationError(
                f"Номер столбца ({self.data_column_number}) не может быть больше "
                f"количества столбцов в источнике данных ({self.generation.data_source.columns_count})"
            )


class GenerationLog(models.Model):
    """
    Модель для детального лога генерации
    """
    LOG_LEVELS = [
        ('debug', 'Отладка'),
        ('info', 'Информация'),
        ('warning', 'Предупреждение'),
        ('error', 'Ошибка'),
        ('critical', 'Критическая ошибка'),
    ]
    
    generation = models.ForeignKey(
        LabelGeneration,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name="Генерация",
        help_text="Генерация, к которой относится лог"
    )
    
    level = models.CharField(
        max_length=20,
        choices=LOG_LEVELS,
        verbose_name="Уровень",
        help_text="Уровень важности сообщения"
    )
    message = models.TextField(
        verbose_name="Сообщение",
        help_text="Текст сообщения лога"
    )
    row_number = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Номер строки",
        help_text="Номер строки данных, к которой относится сообщение"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время",
        help_text="Время создания записи лога"
    )

    class Meta:
        verbose_name = "Запись лога"
        verbose_name_plural = "Записи логов"
        ordering = ['generation', '-timestamp']

    def __str__(self):
        return f"{self.generation.name} - {self.get_level_display()}: {self.message[:50]}"
