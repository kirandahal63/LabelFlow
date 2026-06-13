from rest_framework import serializers
from .models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):

        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                "Passwords do not match."
            )

        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError(
                "Email already registered."
            )

        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            password=validated_data["password"]
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()