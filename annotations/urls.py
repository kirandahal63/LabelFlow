from django.urls import path
from .views import (
    batch_assign_view,
    label_task_view,
    review_task_view,
    submit_batch_review_view,
    batch_review_list_view,
)

urlpatterns = [
    # Admin assigns a batch of 25 to a specific annotator
    path('batch-assign/<uuid:project_id>/', batch_assign_view, name='batch_assign'),

    # Annotator labels a single image
    path('task/<uuid:task_id>/', label_task_view, name='label_task'),

    # Annotator submits entire batch for review
    path('submit-batch/<str:batch_code>/', submit_batch_review_view, name='submit_batch_review'),

    # Reviewer: overview list for a batch
    path('batch/<str:batch_code>/review/', batch_review_list_view, name='batch_review_list'),

    # Reviewer: review a single task (navigates silently within batch)
    path('review/<uuid:task_id>/', review_task_view, name='review_task'),
]
