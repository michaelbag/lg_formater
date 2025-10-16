from django.urls import path
from . import views

app_name = 'data_sources'

urlpatterns = [
    path('download/<int:upload_id>/', views.download_csv_file, name='download_csv'),
]
