from django.contrib import admin

from .models import AnnotationTask, Annotation, Review
admin.site.register(AnnotationTask)
admin.site.register(Annotation)
admin.site.register(Review)
