from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_engine', '0007_add_relative_paths_for_ai_model_artifacts'),
    ]

    operations = [
        migrations.CreateModel(
            name='Crop',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('english_name', models.CharField(max_length=120, unique=True)),
                ('bengali_name', models.CharField(blank=True, max_length=120)),
            ],
            options={'db_table': 'crops', 'ordering': ['english_name']},
        ),
        migrations.AddField(
            model_name='aimodelartifact',
            name='model_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='aimodelartifact',
            name='version',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
