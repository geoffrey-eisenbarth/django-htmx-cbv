from typing import TYPE_CHECKING

from django import forms
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from django_htmx_cbv.forms import HtmxChainedForm
from django_htmx_cbv.views import HtmxChainedFormView


if TYPE_CHECKING:
  from typing import Any, Iterable


MAKE_CHOICES = [('sedan', 'Sedan'), ('suv', 'SUV'), ('truck', 'Truck')]
MODEL_CHOICES_BY_MAKE = {
  'sedan': [('camry', 'Camry'), ('accord', 'Accord')],
  'suv': [('rav4', 'RAV4'), ('crv', 'CR-V')],
  'truck': [('tacoma', 'Tacoma'), ('ranger', 'Ranger')],
}


class VehicleForm(HtmxChainedForm):
  make = forms.ChoiceField(choices=MAKE_CHOICES)
  model = forms.ChoiceField(choices=[])


class VehicleFormView(HtmxChainedFormView[VehicleForm]):
  form_class = VehicleForm
  template_name = 'page.html'

  def get_field_choices(self) -> dict[str, Iterable[tuple[str, str]]]:
    make = self.request.GET.get('make', '')
    return {'model': MODEL_CHOICES_BY_MAKE.get(make, [])}


def redirect_302(request: HttpRequest) -> HttpResponse:
  messages.success(request, 'Message successful!')
  return redirect('page')


class PageView(TemplateView):
  template_name = 'page.html'


class MessageView(PageView):
  def get(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    messages.success(request, 'Message successful!')
    return super().get(request, *args, **kwargs)


class Message204View(MessageView):
  def get(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    super().get(request, *args, **kwargs)
    return HttpResponse(status=204)


class HXRetargetView(PageView):
  def get(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    response = super().get(request, *args, **kwargs)
    response['HX-Retarget'] = 'text'
    return response


class HXPartialNameView(PageView):
  def get(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    response = super().get(request, *args, **kwargs)
    response['HX-Partial-Name'] = 'text'
    return response
