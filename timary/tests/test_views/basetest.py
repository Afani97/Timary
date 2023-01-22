from django.template import Context, Engine, Template
from django.test import Client, TestCase


class BaseTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def setup_template(self, template_name: str, context: dict) -> Template:
        template = Engine(
            app_dirs=True,
            libraries={
                "filters": "timary.templatetags.filters",
                "tz": "django.templatetags.tz",
            },
        ).get_template(template_name)
        context = Context(context)
        return template.render(context)
