from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_engine', '0004_aiserviceconfiguration_aimodelartifact'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aimodelartifact',
            old_name='model_file',
            new_name='model_path',
        ),
        migrations.RenameField(
            model_name='aimodelartifact',
            old_name='indices_file',
            new_name='indices_path',
        ),
        migrations.AlterField(
            model_name='aimodelartifact',
            name='model_path',
            field=models.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name='aimodelartifact',
            name='indices_path',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]