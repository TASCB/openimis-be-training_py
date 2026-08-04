"""Give TMO its full title: TASAF Monitoring Officer.

The seeder only adds missing codes, so an already-seeded database needs the rename
spelled out. The code is untouched — rows and reports join on it.
"""
from django.db import migrations

OLD_NAME = 'TMO'
NEW_NAME = 'TASAF Monitoring Officer'


def _rename(apps, from_name, to_name):
    ParticipantCategory = apps.get_model('training', 'ParticipantCategory')
    (ParticipantCategory.objects.filter(code='TMO', name=from_name)
     .update(name=to_name))


def set_full_title(apps, schema_editor):
    _rename(apps, OLD_NAME, NEW_NAME)


def restore_acronym(apps, schema_editor):
    _rename(apps, NEW_NAME, OLD_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0010_trainer_gender_position'),
    ]

    operations = [
        migrations.RunPython(set_full_title, restore_acronym),
    ]
