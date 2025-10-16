from django.urls import path
from . import views

app_name = 'label_generator'

urlpatterns = [
    path('', views.generation_list, name='generation_list'),
    path('create/', views.create_generation, name='create_generation'),
    path('<int:generation_id>/', views.generation_detail, name='generation_detail'),
    path('<int:generation_id>/logs/', views.generation_logs, name='generation_logs'),
    path('<int:generation_id>/download/', views.download_generated_file, name='download_generated_file'),
    path('<int:generation_id>/progress/', views.get_generation_progress, name='get_generation_progress'),
    path('api/data-source/<int:data_source_id>/columns/', views.get_data_source_columns, name='get_data_source_columns'),
    path('api/template/<int:template_id>/fields/', views.get_template_fields, name='get_template_fields'),
]
