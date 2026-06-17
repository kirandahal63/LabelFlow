from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='annotationtask',
            name='batch',
            field=models.CharField(max_length=30, null=True, blank=True),
        ),
    ]
