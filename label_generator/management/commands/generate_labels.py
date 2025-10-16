from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from label_generator.models import LabelGeneration


class Command(BaseCommand):
    help = 'Запускает генерацию этикеток для указанной генерации'

    def add_arguments(self, parser):
        parser.add_argument(
            'generation_id',
            type=int,
            help='ID генерации для запуска'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительный запуск даже если есть ошибки'
        )

    def handle(self, *args, **options):
        generation_id = options['generation_id']
        force = options['force']

        try:
            generation = LabelGeneration.objects.get(id=generation_id)
        except LabelGeneration.DoesNotExist:
            raise CommandError(f'Генерация с ID {generation_id} не найдена')

        self.stdout.write(f'Запуск генерации: {generation.name}')

        # Проверяем готовность к генерации
        if not force:
            errors = generation.get_generation_errors()
            if errors:
                self.stdout.write(
                    self.style.ERROR('Ошибки, препятствующие запуску генерации:')
                )
                for error in errors:
                    self.stdout.write(self.style.ERROR(f'  - {error}'))
                self.stdout.write(
                    self.style.WARNING('Используйте --force для принудительного запуска')
                )
                return

        try:
            # Запускаем генерацию
            filename = generation.start_generation()
            self.stdout.write(
                self.style.SUCCESS(f'Генерация завершена успешно! Файл: {filename}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка генерации: {e}')
            )
            raise CommandError(f'Генерация не удалась: {e}')
