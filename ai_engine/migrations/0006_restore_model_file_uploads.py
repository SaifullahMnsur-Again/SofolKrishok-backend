from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_engine', '0005_model_artifact_paths'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aimodelartifact',
            old_name='model_path',
            new_name='model_file',
        ),
        migrations.RenameField(
            model_name='aimodelartifact',
            old_name='indices_path',
            new_name='indices_file',
        ),
        migrations.AlterField(
            model_name='aimodelartifact',
            name='model_file',
            field=models.FileField(upload_to='ai_models/'),
        ),
        migrations.AlterField(
            model_name='aimodelartifact',
            name='indices_file',
            field=models.FileField(blank=True, null=True, upload_to='ai_models/'),
        ),
    ]