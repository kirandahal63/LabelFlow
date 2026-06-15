from django.urls import path
from .views import (
    dashboard_view,
    project_create_view,
    project_detail_view,
    admin_dashboard_view,
)
from .api_views import (
    ProjectListCreateAPIView,
    ProjectDetailAPIView,
    ProjectMemberAPIView
)

urlpatterns = [
    # HTML views
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
