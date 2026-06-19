from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, TestCase
from django.urls import reverse

from django_htmx_cbv.forms import HtmxChainedForm
from django_htmx_cbv.views import HtmxChainedFormView

from app.views import MAKE_CHOICES, MODEL_CHOICES_BY_MAKE, VehicleForm


if TYPE_CHECKING:
  from django.http import HttpResponse


class HtmxChainedFormTest(TestCase):

  def test_no_field_choices_leaves_fields_unchanged(self) -> None:
    form = VehicleForm()
    self.assertEqual(list(form.fields['make'].choices), MAKE_CHOICES)
    self.assertEqual(list(form.fields['model'].choices), [])

  def test_field_choices_updates_choice_field(self) -> None:
    choices = MODEL_CHOICES_BY_MAKE['sedan']
    form = VehicleForm(field_choices={'model': choices})
    self.assertEqual(list(form.fields['model'].choices), choices)

  def test_field_choices_raises_for_non_choice_field(self) -> None:
    class BadForm(HtmxChainedForm):
      name = forms.CharField()

    with self.assertRaises(ImproperlyConfigured):
      BadForm(field_choices={'name': [('a', 'A')]})


class HtmxChainedFormViewTest(TestCase):

  def setUp(self) -> None:
    self.client = Client()
    self.url = reverse('vehicle')

  def get_soup(self, response: HttpResponse) -> BeautifulSoup:
    return BeautifulSoup(response.content, features='html.parser')

  def test_non_htmx_get_renders_template(self) -> None:
    response = self.client.get(self.url)
    self.assertEqual(response.status_code, 200)
    soup = self.get_soup(response)  # type: ignore[arg-type]
    self.assertIsNotNone(soup.html)

  def test_htmx_get_returns_chained_field_html(self) -> None:
    response = self.client.get(
      self.url + '?make=sedan',
      headers={'HX-Request': 'true', 'HX-Target': 'id_model'},
    )
    self.assertEqual(response.status_code, 200)
    soup = self.get_soup(response)  # type: ignore[arg-type]
    # Response should be just the <select> widget, not a full HTML page
    assert soup.html is None

    select = soup.find('select', {'name': 'model'})
    assert select is not None

    option_values = [
      opt['value']
      for opt in select.find_all('option')
      if opt is not None
    ]
    self.assertEqual(option_values, ['camry', 'accord'])

  def test_htmx_get_unknown_target_raises(self) -> None:
    with self.assertRaises(ImproperlyConfigured):
      self.client.get(
        self.url,
        headers={'HX-Request': 'true', 'HX-Target': 'id_nonexistent'},
      )

  def test_get_field_choices_not_implemented_raises(self) -> None:
    class IncompleteView(HtmxChainedFormView[VehicleForm]):
      form_class = VehicleForm
      template_name = 'page.html'

    from django.test import RequestFactory
    from django_htmx.middleware import HtmxDetails

    factory = RequestFactory()
    request = factory.get(self.url, headers={'HX-Request': 'true'})
    request.htmx = HtmxDetails(request)  # type: ignore[attr-defined]
    request.QUERY = request.GET  # type: ignore[attr-defined]

    view = IncompleteView()
    view.setup(request)
    with self.assertRaises(ImproperlyConfigured):
      view.get_form_kwargs()
