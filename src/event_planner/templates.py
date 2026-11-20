"""Built-in templates, including the Wedding template blueprint."""
from event_planner.models import Template, TemplateTask


def get_wedding_template() -> Template:
    """Returns the standardized Wedding template blueprint."""
    return Template(
        id="wedding_standard_v1",
        name="Standard Wedding Template",
        default_tasks=[
            TemplateTask(
                template_task_id="w-budget",
                title="Determine wedding budget and guest count",
                relative_days=-365,
                depends_on=[],
                vendor_category="planning",
            ),
            TemplateTask(
                template_task_id="w-venue",
                title="Book ceremony and reception venue",
                relative_days=-300,
                depends_on=["w-budget"],
                vendor_category="venue",
            ),
            TemplateTask(
                template_task_id="w-photo",
                title="Hire photographer and videographer",
                relative_days=-240,
                depends_on=["w-venue"],
                vendor_category="photography",
            ),
            TemplateTask(
                template_task_id="w-catering",
                title="Finalize catering and tasting menu",
                relative_days=-180,
                depends_on=["w-venue"],
                vendor_category="catering",
            ),
            TemplateTask(
                template_task_id="w-invitations",
                title="Send invitations and track RSVPs",
                relative_days=-90,
                depends_on=["w-venue"],
                vendor_category="stationery",
            ),
            TemplateTask(
                template_task_id="w-seating",
                title="Create seating chart",
                relative_days=-30,
                depends_on=["w-invitations"],
                vendor_category="planning",
            ),
            TemplateTask(
                template_task_id="w-rehearsal",
                title="Conduct wedding rehearsal",
                relative_days=-1,
                depends_on=["w-seating"],
                vendor_category="ceremony",
            ),
        ],
    )
