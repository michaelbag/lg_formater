from django.urls import path
from . import views

app_name = 'label_templates'

urlpatterns = [
    path('', views.template_list, name='template_list'),
    path('<int:template_id>/', views.template_detail, name='template_detail'),
    path('<int:template_id>/download/', views.download_template, name='download_template'),
    path('<int:template_id>/fields/', views.get_template_fields, name='get_template_fields'),
    path('data-source/<int:data_source_id>/columns/', views.get_data_source_columns, name='get_data_source_columns'),
    path('generate/', views.generate_labels, name='generate_labels'),
    path('history/', views.usage_history, name='usage_history'),
]
