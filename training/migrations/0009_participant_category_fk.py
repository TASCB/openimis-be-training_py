"""Replace TrainingParticipant.participant_type with a ParticipantCategory FK.

Only two of the nine enum values map cleanly; the rest are left NULL rather than swept
into OTHER. Rationale and the full mapping table: docs/REFERENCE_DATA.md §3.
"""
from django.db import migrations, models
import django.db.models.deletion

# Old enum value -> ParticipantCategory.code; None leaves the row uncategorised.
# Codes are literals, not imports: a migration must keep meaning when the model moves on.
PARTICIPANT_TYPE_TO_CATEGORY = {
    'TASAF_STAFF': 'TMU_HQ_STAFF',
    'CMC_MEMBER': 'CMC',
    'PAA_REP': None,
    'LGA_OFFICER': None,
    'ENUMERATOR': None,
    'SUPERVISOR': None,
    'COMMUNITY_FACILITATOR': None,
    'TRAINER': None,
    'OTHER': None,
}


def rename_tmu_staff(apps, schema_editor):
    """TMU_STAFF -> TMU_HQ_STAFF, ahead of the mapping below.

    The seeder only ever adds missing codes, so an already-seeded database needs the
    rename spelled out. See docs/REFERENCE_DATA.md §2.
    """
    ParticipantCategory = apps.get_model('training', 'ParticipantCategory')
    stale = ParticipantCategory.objects.filter(code='TMU_STAFF')
    if ParticipantCategory.objects.filter(code='TMU_HQ_STAFF').exists():
        # Seeded after the rename landed: both rows exist and nothing points at either yet.
        stale.delete()
    else:
        stale.update(code='TMU_HQ_STAFF', name='TMU Headquarters Staff')


def restore_tmu_staff(apps, schema_editor):
    ParticipantCategory = apps.get_model('training', 'ParticipantCategory')
    (ParticipantCategory.objects.filter(code='TMU_HQ_STAFF')
     .update(code='TMU_STAFF', name='TMU Staff'))


def enum_to_category(apps, schema_editor):
    TrainingParticipant = apps.get_model('training', 'TrainingParticipant')
    ParticipantCategory = apps.get_model('training', 'ParticipantCategory')

    ids_by_code = dict(ParticipantCategory.objects.values_list('code', 'id'))
    updated = []
    for participant in TrainingParticipant.objects.exclude(participant_type=None):
        legacy = participant.participant_type
        if not legacy:
            continue
        json_ext = participant.json_ext if isinstance(participant.json_ext, dict) else {}
        participant.json_ext = {**json_ext, 'legacy_participant_type': legacy}
        code = PARTICIPANT_TYPE_TO_CATEGORY.get(legacy)
        participant.category_id = ids_by_code.get(code) if code else None
        updated.append(participant)
    if updated:
        TrainingParticipant.objects.bulk_update(updated, ['category_id', 'json_ext'], batch_size=500)


def category_to_enum(apps, schema_editor):
    """Restore participant_type from the stashed value — which is why it is stashed."""
    TrainingParticipant = apps.get_model('training', 'TrainingParticipant')
    updated = []
    for participant in TrainingParticipant.objects.all():
        json_ext = participant.json_ext if isinstance(participant.json_ext, dict) else {}
        legacy = json_ext.pop('legacy_participant_type', None)
        if legacy is None:
            continue
        participant.participant_type = legacy
        participant.json_ext = json_ext
        updated.append(participant)
    if updated:
        TrainingParticipant.objects.bulk_update(
            updated, ['participant_type', 'json_ext'], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0008_participantcategory_participantcategorymutation_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_tmu_staff, restore_tmu_staff),
        migrations.AddField(
            model_name='historicaltrainingparticipant',
            name='category',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='training.participantcategory'),
        ),
        migrations.AddField(
            model_name='trainingparticipant',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='participants', to='training.participantcategory'),
        ),
        migrations.RunPython(enum_to_category, category_to_enum),
        migrations.RemoveIndex(
            model_name='trainingparticipant',
            name='training_tr_partici_d67f9e_idx',
        ),
        migrations.RemoveField(
            model_name='historicaltrainingparticipant',
            name='participant_type',
        ),
        migrations.RemoveField(
            model_name='trainingparticipant',
            name='participant_type',
        ),
        migrations.AddIndex(
            model_name='trainingparticipant',
            index=models.Index(fields=['category'], name='training_tr_categor_037759_idx'),
        ),
    ]
