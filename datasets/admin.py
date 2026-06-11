from django.contrib import admin
from .models import Image, Dataset

admin.site.register(Dataset)
admin.site.register(Image)
