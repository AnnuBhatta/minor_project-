from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='userlocation',
            old_name='is_safe_zone',
            new_name='is_emergency',
        ),
        migrations.AlterField(
            model_name='userlocation',
            name='latitude',
            field=models.DecimalField(decimal_places=6, max_digits=9),
        ),
        migrations.AlterField(
            model_name='userlocation',
            name='longitude',
            field=models.DecimalField(decimal_places=6, max_digits=9),
        ),
        migrations.AddField(
            model_name='userlocation',
            name='speed',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userlocation',
            name='heading',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userlocation',
            name='emergency_event_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='userlocation',
            index=models.Index(fields=['user', 'timestamp'], name='location_user_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='userlocation',
            index=models.Index(fields=['user', 'is_emergency'], name='location_user_emergency_idx'),
        ),
    ]
