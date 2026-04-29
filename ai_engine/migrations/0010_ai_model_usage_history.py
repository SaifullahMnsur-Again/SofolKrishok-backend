from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_subscriptionplan_ai_assistant_daily_limit_and_more'),
        ('ai_engine', '0009_alter_crop_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIModelUsageHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_name', models.CharField(choices=[('disease_detection', 'Disease Detection'), ('soil_classification', 'Soil Classification'), ('gemini_chat', 'Gemini Chat'), ('voice_command', 'Voice Command'), ('weather_forecast', 'Weather Forecast'), ('other', 'Other')], max_length=50)),
                ('operation', models.CharField(blank=True, max_length=32)),
                ('model_identifier', models.CharField(blank=True, max_length=255)),
                ('model_version', models.CharField(blank=True, max_length=64)),
                ('request_path', models.CharField(blank=True, max_length=255)),
                ('user_role', models.CharField(blank=True, max_length=30)),
                ('subscription_plan_name', models.CharField(blank=True, max_length=100)),
                ('subscription_plan_type', models.CharField(blank=True, max_length=20)),
                ('subscription_status', models.CharField(blank=True, max_length=20)),
                ('request_metadata', models.JSONField(blank=True, default=dict)),
                ('response_metadata', models.JSONField(blank=True, default=dict)),
                ('confidence', models.FloatField(blank=True, null=True)),
                ('success', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True)),
                ('response_time_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('model_artifact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='usage_history', to='ai_engine.aimodelartifact')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='model_usage_history', to='finance.subscription')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='model_usage_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ai_model_usage_history',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['service_name', '-created_at'], name='ai_model_u_service_7b5c4a_idx'),
                    models.Index(fields=['operation', '-created_at'], name='ai_model_u_operat_3c0c6c_idx'),
                    models.Index(fields=['user_role', '-created_at'], name='ai_model_u_user_ro_2e5f1d_idx'),
                ],
            },
        ),
    ]