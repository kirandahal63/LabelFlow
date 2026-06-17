from django.urls import path
from .views import (
    assign_task_view,
    auto_assign_view,
    bulk_assign_view,
    label_task_view,
    review_task_view,
    submit_dataset_review_view,
    submit_batch_review_view,
)

urlpatterns = [
    path('assign/<uuid:task_id>/', assign_task_view, name='assign_task'),
    path('auto-assign/<uuid:project_id>/', auto_assign_view, name='auto_assign'),
    path('bulk-assign/<uuid:project_id>/', bulk_assign_view, name='bulk_assign'),
    path('task/<uuid:task_id>/', label_task_view, name='label_task'),
    path('review/<uuid:task_id>/', review_task_view, name='review_task'),
    path('submit-dataset/<uuid:dataset_id>/', submit_dataset_review_view, name='submit_dataset_review'),
    path('submit-batch/<str:batch_code>/', submit_batch_review_view, name='submit_batch_review'),
]
