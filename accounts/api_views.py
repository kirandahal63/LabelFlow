from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import (
    RegisterSerializer,
    LoginSerializer
)


class RegisterAPIView(APIView):

    def post(self, request):

        serializer = RegisterSerializer(
            data=request.data
        )

        if serializer.is_valid():

            user = serializer.save()

            login(request, user)

            return Response(
                {
                    "success": True,
                    "message": "User registered successfully.",
                    "role": user.role,
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class LoginAPIView(APIView):

    def post(self, request):

        serializer = LoginSerializer(
            data=request.data
        )

        if serializer.is_valid():

            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]

            user = authenticate(
                request,
                username=email,   # because USERNAME_FIELD=email
                password=password
            )

            if user:

                login(request, user)

                return Response(
                    {
                        "success": True,
                        "message": "Login successful.",
                        "role": user.role,
                    }
                )

            return Response(
                {
                    "success": False,
                    "message": "Invalid credentials."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class LogoutAPIView(APIView):

    def post(self, request):

        logout(request)

        return Response(
            {
                "success": True,
                "message": "Logged out successfully."
            }
        )