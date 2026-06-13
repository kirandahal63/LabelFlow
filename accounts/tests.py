from django.test import TestCase
from accounts.models import User
from accounts.serializers import RegisterSerializer

class AccountsTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
            first_name="Test",
            last_name="User"
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpassword123"))
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")
        self.assertTrue(User.objects.filter(email="test@example.com").exists())

    def test_register_serializer(self):
        data = {
            "email": "serializer@example.com",
            "first_name": "Seri",
            "last_name": "Alizer",
            "password": "mypassword123",
            "confirm_password": "mypassword123"
        }
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertEqual(user.email, "serializer@example.com")
        self.assertEqual(user.first_name, "Seri")
        self.assertEqual(user.last_name, "Alizer")
        self.assertTrue(User.objects.filter(email="serializer@example.com").exists())
