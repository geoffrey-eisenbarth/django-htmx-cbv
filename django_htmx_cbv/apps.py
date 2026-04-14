from django.apps import AppConfig


class DjangoHtmxCbvConfig(AppConfig):
  default_auto_field = 'django.db.models.BigAutoField'
  name = 'django_htmx_cbv'

  def ready(self) -> None:
    from . import checks  # noqa: F401
