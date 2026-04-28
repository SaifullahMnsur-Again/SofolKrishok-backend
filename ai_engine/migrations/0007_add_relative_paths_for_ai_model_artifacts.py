from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_engine', '0006_restore_model_file_uploads'),
    ]

    operations = [
        migrations.AddField(
            model_name='aimodelartifact',
            name='indices_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='aimodelartifact',
            name='model_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='aimodelartifact',
            name='model_file',
            field=models.FileField(blank=True, null=True, upload_to='ai_models/'),
        ),
    ]
