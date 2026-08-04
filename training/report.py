"""Reports exposed by the Training module.

``report.apps.ReportConfig`` discovers this module automatically (it looks for a
``report`` submodule with a ``report_definitions`` list in every installed openIMIS
app), so nothing has to be registered by hand. Each entry becomes available at
``/api/report/<name>/<pdf|xlsx>/`` and in the reports list the frontend renders.
"""
from training.apps import DEFAULT_CONFIG, TrainingConfig
from training.reports import training_report

# ReportConfig.ready() imports this module, and may do so BEFORE TrainingConfig.ready()
# has loaded the module configuration — in which case the config attribute is still the
# empty class default. That matters: an empty permission list makes has_perms() return
# True for everyone, so capturing [] here would publish the report to all users. Fall
# back to the shipped default so the report is never left ungated.
def _perms(key):
    return getattr(TrainingConfig, key, None) or DEFAULT_CONFIG[key]


report_definitions = [
    {
        'name': 'training_report',
        'engine': 0,  # ReportBro
        'default_report': training_report.template,
        'description': 'Training Report',
        'module': 'training',
        'python_query': training_report.training_report_query,
        'permission': _perms('gql_training_report_perms'),
    },
]
