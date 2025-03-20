from typing import Optional

from django.db.models import QuerySet
from django.forms import Form
from django.utils.translation import gettext_lazy as _


class HtmxChainedForm(Form):
  """Custom form subclass to work with HtmxChainedFormView."""
  def __init__(self, options: Optional[dict] = None, *args, **kwargs):
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
            message = (
              f'The choices for {field_name} must be a list of tuples!'
            )
            raise TypeError(message)
        self.fields[field_name] = form_field
