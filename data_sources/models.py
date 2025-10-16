from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os


def csv_upload_path(instance, filename):
    """
    Генерирует путь для сохранения CSV файла
    Формат: csv_files/YYYY/MM/DD/filename
    """
    date = instance.upload_date
    return f'csv_files/{date.year}/{date.month:02d}/{date.day:02d}/{filename}'


class CSVUploadLog(models.Model):
    """
    Модель для журнала загрузки CSV файлов
    """
    filename = models.CharField(
        max_length=255,
        verbose_name="Наименование файла",
        help_text="Название загруженного CSV файла"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Автор загрузки",
        help_text="Пользователь, загрузивший файл"
    )
    upload_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="Дата загрузки",
        help_text="Дата и время загрузки файла"
    )
    file_size = models.PositiveIntegerField(
        default=0,
        verbose_name="Размер файла (байт)",
        help_text="Размер загруженного файла в байтах"
    )
    rows_count = models.PositiveIntegerField(
        verbose_name="Количество строк",
        help_text="Общее количество строк в CSV файле"
    )
    columns_count = models.PositiveIntegerField(
        verbose_name="Количество столбцов",
        help_text="Количество столбцов в CSV файле"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('uploading', 'Загружается'),
            ('processing', 'Обрабатывается'),
            ('completed', 'Завершено'),
            ('error', 'Ошибка'),
        ],
        default='uploading',
        verbose_name="Статус обработки",
        help_text="Текущий статус обработки файла"
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name="Сообщение об ошибке",
        help_text="Описание ошибки, если она возникла"
    )
    has_headers = models.BooleanField(
        default=False,
        verbose_name="Содержит заголовки столбцов",
        help_text="Отметьте, если первая строка содержит названия столбцов"
    )
    
    # Разделители столбцов
    DELIMITER_CHOICES = [
        (',', 'Запятая (,)'),
        (';', 'Точка с запятой (;)'),
        ('\t', 'Табуляция (\\t)'),
        ('|', 'Вертикальная черта (|)'),
        (' ', 'Пробел ( )'),
        (':', 'Двоеточие (:)'),
    ]
    
    delimiter = models.CharField(
        max_length=1,
        choices=DELIMITER_CHOICES,
        default=',',
        verbose_name="Разделитель столбцов",
        help_text="Символ, используемый для разделения столбцов в CSV файле"
    )
    original_file = models.FileField(
        upload_to=csv_upload_path,
        blank=True,
        null=True,
        verbose_name="Исходный файл",
        help_text="Оригинальный CSV файл, загруженный пользователем"
    )

    class Meta:
        verbose_name = "Журнал загрузки CSV"
        verbose_name_plural = "Журнал загрузок CSV"
        ordering = ['-upload_date']

    def __str__(self):
        return f"{self.filename} - {self.author.username} ({self.upload_date.strftime('%d.%m.%Y %H:%M')})"

    def save(self, *args, **kwargs):
        """
        Автоматическое заполнение полей при сохранении
        """
        # Если это новая запись и есть файл
        if not self.pk and self.original_file:
            # Автоматически устанавливаем имя файла из загруженного файла
            if not self.filename:
                self.filename = self.original_file.name
            
            # Автоматически устанавливаем размер файла
            try:
                self.file_size = self.original_file.size
            except (OSError, ValueError):
                self.file_size = 0
        
        # Если автор не заполнен, пытаемся получить текущего пользователя
        if not self.author_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # Пытаемся получить текущего пользователя из контекста
            # Это работает только если save() вызывается из админ-панели или с передачей user
            if hasattr(self, '_current_user') and self._current_user:
                self.author = self._current_user
            else:
                # Если нет текущего пользователя, берем первого суперпользователя
                superuser = User.objects.filter(is_superuser=True).first()
                if superuser:
                    self.author = superuser
        
        super().save(*args, **kwargs)
    
    def auto_detect_delimiter(self):
        """
        Автоматически определяет разделитель в CSV файле
        """
        if not self.original_file:
            return self.delimiter
        
        from .csv_processor import CSVProcessor
        processor = CSVProcessor(self)
        detected_delimiter = processor.auto_detect_and_set_delimiter()
        return detected_delimiter
    
    def process_csv_data(self):
        """
        Обрабатывает CSV файл и сохраняет данные в базу
        """
        from .csv_processor import CSVProcessor
        processor = CSVProcessor(self)
        return processor.process_csv_file()


class CSVData(models.Model):
    """
    Модель для хранения данных из CSV файлов
    """
    upload_log = models.ForeignKey(
        CSVUploadLog,
        on_delete=models.CASCADE,
        related_name='csv_data',
        verbose_name="Журнал загрузки",
        help_text="Ссылка на запись в журнале загрузки"
    )
    row_number = models.PositiveIntegerField(
        verbose_name="Номер строки",
        help_text="Номер строки в CSV файле (начиная с 1)"
    )
    column_number = models.PositiveIntegerField(
        verbose_name="Номер столбца",
        help_text="Номер столбца в CSV файле (начиная с 1)"
    )
    column_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Название столбца",
        help_text="Название столбца (из первой строки CSV)"
    )
    cell_value = models.TextField(
        verbose_name="Значение ячейки",
        help_text="Содержимое ячейки CSV файла"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания записи",
        help_text="Дата и время создания записи в базе данных"
    )

    class Meta:
        verbose_name = "Данные CSV"
        verbose_name_plural = "Данные CSV"
        ordering = ['upload_log', 'row_number', 'column_number']
        indexes = [
            models.Index(fields=['upload_log', 'row_number']),
            models.Index(fields=['upload_log', 'column_number']),
            models.Index(fields=['column_name']),
        ]

    def __str__(self):
        return f"{self.upload_log.filename} - Строка {self.row_number}, Столбец {self.column_number}: {self.cell_value[:50]}"


class CSVColumn(models.Model):
    """
    Модель для хранения информации о столбцах CSV файла
    """
    upload_log = models.ForeignKey(
        CSVUploadLog,
        on_delete=models.CASCADE,
        related_name='csv_columns',
        verbose_name="Журнал загрузки",
        help_text="Ссылка на запись в журнале загрузки"
    )
    column_number = models.PositiveIntegerField(
        verbose_name="Номер столбца",
        help_text="Порядковый номер столбца в CSV файле (начиная с 1)"
    )
    column_name = models.CharField(
        max_length=255,
        verbose_name="Название столбца",
        help_text="Название столбца из заголовка CSV файла"
    )
    original_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Оригинальное название",
        help_text="Оригинальное название столбца (если было изменено)"
    )
    data_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Тип данных",
        help_text="Определенный тип данных столбца (text, number, date, etc.)"
    )
    is_required = models.BooleanField(
        default=False,
        verbose_name="Обязательный столбец",
        help_text="Является ли столбец обязательным для заполнения"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание столбца",
        help_text="Дополнительное описание назначения столбца"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        help_text="Дата и время создания записи о столбце"
    )

    class Meta:
        verbose_name = "Столбец CSV"
        verbose_name_plural = "Столбцы CSV"
        ordering = ['upload_log', 'column_number']
        unique_together = ['upload_log', 'column_number']
        indexes = [
            models.Index(fields=['upload_log', 'column_number']),
            models.Index(fields=['column_name']),
        ]

    def __str__(self):
        return f"{self.upload_log.filename} - Столбец {self.column_number}: {self.column_name}"
