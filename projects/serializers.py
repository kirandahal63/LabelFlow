from rest_framework import serializers
from .models import Project, ProjectMember
from accounts.models import User

class ProjectSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id',
            'name',
            'description',
            'status',
            'label_set',
            'deadline',
            'created_by',
            'created_by_email',
            'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProjectMember
        fields = [
            'id',
            'project',
            'user',
            'role_in_project',
            'user_email',
            'user_name',
            'joined_at'
        ]
        read_only_fields = ['joined_at']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()
