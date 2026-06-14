from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User
from projects.models import Project, ProjectMember

class ProjectAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            first_name="Admin",
            last_name="User",
            is_staff=True
        )
        self.normal_user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            first_name="Normal",
            last_name="User"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="password123",
            first_name="Other",
            last_name="User"
        )
        
        # Create a project
        self.project = Project.objects.create(
            name="Test Project",
            description="Testing description",
            status="active",
            label_set=["car", "truck"],
            created_by=self.admin_user
        )

    def test_create_project_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project-api-list-create")
        data = {
            "name": "New Project",
            "description": "Desc",
            "status": "draft",
            "label_set": ["cat", "dog"],
            "deadline": "2026-12-31"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.filter(name="New Project").count(), 1)
        self.assertEqual(Project.objects.get(name="New Project").created_by, self.admin_user)

    def test_create_project_non_admin_fails(self):
        self.client.force_authenticate(user=self.normal_user)
        url = reverse("project-api-list-create")
        data = {
            "name": "User Project",
            "description": "Desc",
            "status": "draft",
            "label_set": ["cat"],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_member(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("project-api-members", kwargs={"project_id": self.project.id})
        
        # Add normal_user as reviewer
        data = {
            "user": str(self.normal_user.id),
            "role_in_project": "reviewer"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check database
        member = ProjectMember.objects.get(project=self.project, user=self.normal_user)
        self.assertEqual(member.role_in_project, "reviewer")

    def test_update_member_role(self):
        self.client.force_authenticate(user=self.admin_user)
        # Pre-assign as annotator
        ProjectMember.objects.create(
            project=self.project,
            user=self.normal_user,
            role_in_project="annotator"
        )
        
        url = reverse("project-api-members", kwargs={"project_id": self.project.id})
        # Update to reviewer
        data = {
            "user": str(self.normal_user.id),
            "role_in_project": "reviewer"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check database
        member = ProjectMember.objects.get(project=self.project, user=self.normal_user)
        self.assertEqual(member.role_in_project, "reviewer")

    def test_remove_member(self):
        self.client.force_authenticate(user=self.admin_user)
        # Pre-assign
        ProjectMember.objects.create(
            project=self.project,
            user=self.normal_user,
            role_in_project="annotator"
        )
        
        url = reverse("project-api-members", kwargs={"project_id": self.project.id})
        data = {
            "user": str(self.normal_user.id)
        }
        response = self.client.delete(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ProjectMember.objects.filter(project=self.project, user=self.normal_user).exists())

    def test_bulk_assign_view(self):
        # Authenticate admin
        self.client.force_login(self.admin_user)
        
        # Add normal_user as project member with annotator role
        ProjectMember.objects.create(
            project=self.project,
            user=self.normal_user,
            role_in_project="annotator"
        )
        
        # Create dataset and image records to generate unassigned tasks
        from datasets.models import Dataset, Image
        from annotations.models import AnnotationTask
        
        dataset = Dataset.objects.create(
            project=self.project,
            name="Test Dataset",
            original_filename="test.zip",
            uploaded_by=self.admin_user,
            status="ready"
        )
        
        # Create 3 images and their unassigned tasks
        for i in range(3):
            img = Image.objects.create(
                dataset=dataset,
                filename=f"img_{i}.png",
                storage_url=f"/media/img_{i}.png",
                file_size_bytes=100,
                width_px=10,
                height_px=10,
                md5_hash=f"hash_{i}",
                status="pending"
            )
            AnnotationTask.objects.create(
                image=img,
                project=self.project,
                status="unassigned"
            )
            
        # Post to bulk assign URL
        url = reverse("bulk_assign", kwargs={"project_id": self.project.id})
        response = self.client.post(url, {
            "annotator_id": str(self.normal_user.id),
            "num_tasks": "2",
            "dataset_id": ""
        })
        
        # Should redirect back to project_detail
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        
        # Check task statuses: 2 should be assigned to normal_user, 1 unassigned
        assigned_tasks = AnnotationTask.objects.filter(project=self.project, status="assigned", assigned_to=self.normal_user)
        self.assertEqual(assigned_tasks.count(), 2)
        
        unassigned_tasks = AnnotationTask.objects.filter(project=self.project, status="unassigned")
        self.assertEqual(unassigned_tasks.count(), 1)
