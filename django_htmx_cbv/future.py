from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.forms import Form
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _

from django_htmx_cbv.views import ProcessHyperFormView


if TYPE_CHECKING:
  from typing import Any
  from django import forms
  from django.http import HttpRequest


# forms.py
class HtmxChainedForm(Form):
  """Custom form subclass to work with HtmxChainedFormView."""
  def __init__(
    self,
    options: dict[str, Any] | None = None,
    *args: Any,
    **kwargs: Any,
  ) -> None:
    super().__init__(*args, **kwargs)

    # Set options on form
    if options is not None:
      for field_name, choices in options.items():
        form_field = self.fields[field_name]
        if hasattr(form_field, 'queryset'):
          if isinstance(choices, QuerySet):
            form_field.queryset = choices
          else:
            message = _(
              f'The choices for {field_name} must be a QuerySet!'
            )
            raise TypeError(message)
        elif hasattr(form_field, 'choices'):
          if isinstance(choices, list):
            form_field.choices = choices
          else:
            message = _(
              f'The choices for {field_name} must be a list of tuples!'
            )
            raise TypeError(message)
        self.fields[field_name] = form_field


# views.py
class HtmxChainedFormView[_F: forms.BaseForm](ProcessHyperFormView[_F]):
  """Allows dynamic chained form fields."""

  def get_options(self) -> dict[str, Any]:
    message = (
      "HtmxChainedFormView requires an implementation "
      "of `get_options()` that returns a dictionary "
      "of the form {field_name: [choices]}. If form "
      "values are required, they should be specified "
      "via `hx-include`."
    )
    raise ImproperlyConfigured(message)

  def get_form_kwargs(self) -> dict[str, Any]:
    """Override to provide `options` kwarg.

    Notes
    -----
    Django Form instances that are going to be used with this view must
    allow a `options` kwarg in their __init__ method.

    """
    kwargs = super().get_form_kwargs()
    if self.request.htmx:
      kwargs['options'] = self.get_options()
    return kwargs

  def get(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    """Override to determine what needs to be rendered."""
    # TODO PUSH: Find a proper way to get field ids? (See 'id_' below too)
    form_class = self.get_form_class()
    form_field_ids = [
      f'id_{field_name}'
      for field_name, field in form_class.base_fields.items()
      if hasattr(field, 'choices')
    ] + ['id_choices']

    if request.htmx.target in form_field_ids:
      form_class = self.get_form_class()
      kwargs = self.get_form_kwargs()
      form = form_class(**kwargs)

      html = "".join(
        map(str, (form[field_name] for field_name in kwargs['options']))
      )
      response = HttpResponse(html)
    else:
      response = HttpResponse(status=204)

    return response
