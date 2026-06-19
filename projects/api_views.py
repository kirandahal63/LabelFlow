from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Project, ProjectMember
from .serializers import ProjectSerializer, ProjectMemberSerializer
from accounts.models import User

class IsAdminUserOrReadOnly(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.role == "admin"


class ProjectListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [IsAdminUserOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Project.objects.all().order_by('-created_at')
        return Project.objects.filter(projectmember__user=user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ProjectDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAdminUserOrReadOnly]
    lookup_field = 'id'
    lookup_url_kwarg = 'project_id'



class ProjectMemberAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        # Check permissions: must be admin or member
        if request.user.role != "admin" and not ProjectMember.objects.filter(project=project, user=request.user).exists():
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
            
        members = ProjectMember.objects.filter(project=project)
        serializer = ProjectMemberSerializer(members, many=True)
        return Response(serializer.data)

    def post(self, request, project_id):
        # Only admin can add members
        if request.user.role != "admin":
            return Response({"detail": "Only admins can add project members."}, status=status.HTTP_403_FORBIDDEN)
            
        project = get_object_or_404(Project, id=project_id)
        
        # We accept user_id or email
        email = request.data.get("email")
        user_id = request.data.get("user")
        role = request.data.get("role_in_project", "annotator")

        if email:
            user = get_object_or_404(User, email=email)
        elif user_id:
            user = get_object_or_404(User, id=user_id)
        else:
            return Response({"detail": "User email or ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if already a member
        member, created = ProjectMember.objects.get_or_create(
            project=project,
            user=user,
            defaults={"role_in_project": role}
        )

        if not created:
            # Update role
            member.role_in_project = role
            member.save()

        serializer = ProjectMemberSerializer(member)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, project_id):
        # Only admin can remove members
        if request.user.role != "admin":
            return Response({"detail": "Only admins can remove project members."}, status=status.HTTP_403_FORBIDDEN)
            
        project = get_object_or_404(Project, id=project_id)
        user_id = request.data.get("user")
        
        if not user_id:
            return Response({"detail": "User ID is required to remove member."}, status=status.HTTP_400_BAD_REQUEST)
            
        member = get_object_or_404(ProjectMember, project=project, user_id=user_id)
        member.delete()
        return Response({"success": True, "message": "Member removed successfully."})
    
    
