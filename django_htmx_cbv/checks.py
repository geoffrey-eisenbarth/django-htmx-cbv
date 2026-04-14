from typing import TYPE_CHECKING

from django.conf import settings
from django.core.checks import Error, register


if TYPE_CHECKING:
  from collections.abc import Iterable, Sequence
  from typing import Any
  from django.apps import AppConfig
  from django.core.checks import CheckMessage


HTMX_MIDDLEWARE = 'django_htmx.middleware.HtmxMiddleware'
CBV_MIDDLEWARE_PREFIX = 'django_htmx_cbv.middleware.'


@register()
def check_htmx_middleware_order(
  *,
  app_configs: Sequence[AppConfig] | None,
  databases: Sequence[str] | None = None,
  **kwargs: Any,
) -> Iterable[CheckMessage]:
  middleware = list(getattr(settings, 'MIDDLEWARE', []))
  cbv_indices = [
    index
    for index, path in enumerate(middleware)
    if path.startswith(CBV_MIDDLEWARE_PREFIX)
  ]
  if not cbv_indices:
    return []

  if HTMX_MIDDLEWARE not in middleware:
    return [
      Error(
        "django-htmx middleware is required by django-htmx-cbv middleware.",
        hint=(
          "Add 'django_htmx.middleware.HtmxMiddleware' before any "
          "'django_htmx_cbv.middleware.*' entries in MIDDLEWARE."
        ),
        id='django_htmx_cbv.E001',
      )
    ]

  htmx_index = middleware.index(HTMX_MIDDLEWARE)
  if any(index < htmx_index for index in cbv_indices):
    return [
      Error(
        "django-htmx middleware must run before django-htmx-cbv middleware.",
        hint=(
          "Move 'django_htmx.middleware.HtmxMiddleware' above all "
          "'django_htmx_cbv.middleware.*' entries in MIDDLEWARE."
        ),
        id='django_htmx_cbv.E002',
      )
    ]

  return []
