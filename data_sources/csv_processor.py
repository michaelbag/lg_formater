import csv
import io
from typing import List, Dict, Any, Optional
from django.core.exceptions import ValidationError
from .models import CSVUploadLog, CSVData, CSVColumn


class CSVProcessor:
    """
    Класс для обработки CSV файлов с различными разделителями
    """
    
    def __init__(self, upload_log: CSVUploadLog):
        self.upload_log = upload_log
        self.delimiter = upload_log.delimiter
        self.has_headers = upload_log.has_headers
        
    def process_csv_file(self) -> Dict[str, Any]:
        """
        Обрабатывает CSV файл и сохраняет данные в базу
        """
        if not self.upload_log.original_file:
            raise ValidationError("Файл не найден")
        
        try:
            # Читаем файл
            with open(self.upload_log.original_file.path, 'r', encoding='utf-8') as file:
                # Пробуем определить кодировку если UTF-8 не работает
                try:
                    content = file.read()
                except UnicodeDecodeError:
                    # Пробуем другие кодировки
                    file.seek(0)
                    try:
                        content = file.read(encoding='cp1251')
                    except UnicodeDecodeError:
                        file.seek(0)
                        content = file.read(encoding='latin-1')
            
            # Создаем StringIO объект для csv.reader
            csv_content = io.StringIO(content)
            
            # Читаем CSV с указанным разделителем
            csv_reader = csv.reader(csv_content, delimiter=self.delimiter)
            
            rows = list(csv_reader)
            
            if not rows:
                raise ValidationError("CSV файл пуст")
            
            # Определяем количество строк и столбцов
            rows_count = len(rows)
            columns_count = len(rows[0]) if rows else 0
            
            # Проверяем, что все строки имеют одинаковое количество столбцов
            for i, row in enumerate(rows):
                if len(row) != columns_count:
                    raise ValidationError(
                        f"Строка {i+1} содержит {len(row)} столбцов, "
                        f"ожидается {columns_count}"
                    )
            
            # Обновляем информацию о файле
            self.upload_log.rows_count = rows_count
            self.upload_log.columns_count = columns_count
            self.upload_log.status = 'processing'
            self.upload_log.save()
            
            # Обрабатываем заголовки если есть
            headers = []
            data_start_row = 1
            
            if self.has_headers and rows:
                headers = rows[0]
                data_start_row = 2  # Данные начинаются со второй строки
                
                # Создаем записи о столбцах
                self._create_column_records(headers)
            
            # Сохраняем данные
            self._save_csv_data(rows, data_start_row)
            
            # Обновляем статус
            self.upload_log.status = 'completed'
            self.upload_log.save()
            
            return {
                'rows_count': rows_count,
                'columns_count': columns_count,
                'has_headers': self.has_headers,
                'headers': headers,
                'delimiter': self.delimiter
            }
            
        except Exception as e:
            # Обновляем статус на ошибку
            self.upload_log.status = 'error'
            self.upload_log.error_message = str(e)
            self.upload_log.save()
            raise ValidationError(f"Ошибка обработки CSV файла: {e}")
    
    def _create_column_records(self, headers: List[str]):
        """
        Создает записи о столбцах CSV файла
        """
        for i, header in enumerate(headers, 1):
            CSVColumn.objects.create(
                upload_log=self.upload_log,
                column_number=i,
                column_name=header.strip(),
                original_name=header.strip(),
                data_type='text',  # По умолчанию все текстовые
                is_required=False,
                description=f"Столбец {i}: {header.strip()}"
            )
    
    def _save_csv_data(self, rows: List[List[str]], start_row: int):
        """
        Сохраняет данные CSV в базу данных
        """
        # Удаляем старые данные если есть
        CSVData.objects.filter(upload_log=self.upload_log).delete()
        
        # Сохраняем новые данные
        for row_index, row in enumerate(rows[start_row-1:], start_row):
            for col_index, cell_value in enumerate(row, 1):
                CSVData.objects.create(
                    upload_log=self.upload_log,
                    row_number=row_index,
                    column_number=col_index,
                    column_name=self._get_column_name(col_index),
                    cell_value=cell_value.strip() if cell_value else ''
                )
    
    def _get_column_name(self, column_number: int) -> str:
        """
        Получает название столбца по номеру
        """
        if self.has_headers:
            try:
                column = CSVColumn.objects.get(
                    upload_log=self.upload_log,
                    column_number=column_number
                )
                return column.column_name
            except CSVColumn.DoesNotExist:
                pass
        
        return f"Столбец {column_number}"
    
    def detect_delimiter(self, sample_size: int = 1024) -> str:
        """
        Автоматически определяет разделитель в CSV файле
        """
        if not self.upload_log.original_file:
            return ','
        
        try:
            with open(self.upload_log.original_file.path, 'r', encoding='utf-8') as file:
                sample = file.read(sample_size)
        except UnicodeDecodeError:
            try:
                with open(self.upload_log.original_file.path, 'r', encoding='cp1251') as file:
                    sample = file.read(sample_size)
            except UnicodeDecodeError:
                with open(self.upload_log.original_file.path, 'r', encoding='latin-1') as file:
                    sample = file.read(sample_size)
        
        # Подсчитываем количество каждого возможного разделителя
        delimiter_counts = {}
        possible_delimiters = [',', ';', '\t', '|', ':', ' ']
        
        for delimiter in possible_delimiters:
            delimiter_counts[delimiter] = sample.count(delimiter)
        
        # Возвращаем разделитель с максимальным количеством
        best_delimiter = max(delimiter_counts, key=delimiter_counts.get)
        
        # Если нет разделителей, возвращаем запятую по умолчанию
        if delimiter_counts[best_delimiter] == 0:
            return ','
        
        return best_delimiter
    
    def auto_detect_and_set_delimiter(self):
        """
        Автоматически определяет и устанавливает разделитель
        """
        detected_delimiter = self.detect_delimiter()
        self.upload_log.delimiter = detected_delimiter
        self.upload_log.save()
        return detected_delimiter
