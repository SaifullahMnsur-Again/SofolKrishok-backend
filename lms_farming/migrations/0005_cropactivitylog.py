from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('lms_farming', '0004_croptrackhistory'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CropActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(choices=[('irrigation', 'Irrigation'), ('fertilization', 'Fertilization'), ('pesticide', 'Pesticide'), ('harvest', 'Harvest'), ('other', 'Other')], max_length=20)),
                ('occurred_at', models.DateTimeField()),
                ('quantity', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('unit', models.CharField(blank=True, help_text='e.g. liters, kg, grams, bags', max_length=50)),
                ('notes', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_crop_activities', to=settings.AUTH_USER_MODEL)),
                ('track', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_logs', to='lms_farming.croptrack')),
            ],
            options={
                'db_table': 'crop_activity_logs',
                'ordering': ['-occurred_at', '-created_at'],
            },
        ),
    ]