from django.urls import path

from datasets import views
from .views import (
    dashboard_view,
    project_create_view,
    project_detail_view,
    admin_dashboard_view,
    update_project_status,
    download_annotations_view
)
from .api_views import (
    ProjectListCreateAPIView,
    ProjectDetailAPIView,
    ProjectMemberAPIView
)

urlpatterns = [
    # HTML views
    path('project/update-status/<uuid:project_id>/', update_project_status, name='update_project_status'),
    
    path(
        "",
        dashboard_view,
        name="dashboard"
    ),
    path(
        "create/",
        project_create_view,
        name="project-create"
    ),
    path(
        "<uuid:project_id>/",
        project_detail_view,
        name="project_detail"
    ),
    path(
        "<uuid:project_id>/download/",
        download_annotations_view,
        name="download_annotations"
    ),
    path(
        "admin-panel/",
        admin_dashboard_view,
        name="admin_dashboard"
    ),

    # REST APIs
    path(
        "api/",
        ProjectListCreateAPIView.as_view(),
        name="project-api-list-create"
    ),
    path(
        "api/<uuid:project_id>/",
        ProjectDetailAPIView.as_view(),
        name="project-api-detail"
    ),
    path(
        "api/<uuid:project_id>/members/",
        ProjectMemberAPIView.as_view(),
        name="project-api-members"
    ),
    
]
