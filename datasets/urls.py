from django.urls import path
from .views import upload_dataset_view

urlpatterns = [
    path('upload/<uuid:project_id>/', upload_dataset_view, name='upload_dataset'),
]

