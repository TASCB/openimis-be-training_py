from django.db import migrations
import uuid


def seed_trainer_sequence(apps, schema_editor):
    """Seed the auto-increment sequence for trainer codes, continuing past any existing numeric codes."""
    TrainerProfile = apps.get_model('training', 'TrainerProfile')
    ActivityCodeSequence = apps.get_model('training', 'ActivityCodeSequence')
    key = 'TRAINER'
    last_number = 0
    for code in TrainerProfile.objects.values_list('code', flat=True):
        if code and code.isdigit():
            last_number = max(last_number, int(code))
    ActivityCodeSequence.objects.get_or_create(
        prefix=key,
        defaults={'id': uuid.uuid4(), 'last_number': last_number},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0004_activity_code_sequence'),
    ]

    operations = [
        migrations.RunPython(seed_trainer_sequence, migrations.RunPython.noop),
    ]
