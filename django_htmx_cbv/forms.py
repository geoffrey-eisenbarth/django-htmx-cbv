from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django import forms
from django.utils.translation import gettext_lazy as _


if TYPE_CHECKING:
  from typing import Any, Iterable

  Choices = Iterable[tuple[str, str]] | QuerySet[Any]


class HtmxChainedForm(forms.Form):
  """Custom form subclass to work with HtmxChainedFormView."""

  def __init__(
    self,
    field_choices: dict[str, Choices] | None = None,
    *args: Any,
    **kwargs: Any,
  ) -> None:
    super().__init__(*args, **kwargs)
    if field_choices is not None:
      for field_name, choices in field_choices.items():
        field = self.fields[field_name]
        if isinstance(field, forms.ModelChoiceField):
          if isinstance(choices, QuerySet):
            field.queryset = choices
          else:
            field.choices = choices
        elif isinstance(field, forms.ChoiceField):
          field.choices = choices
        else:
          raise ImproperlyConfigured(_(
            f"Field '{field_name}' does not support choices."
          ))
