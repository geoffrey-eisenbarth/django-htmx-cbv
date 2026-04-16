from typing import TYPE_CHECKING, cast

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import (
  ImproperlyConfigured, PermissionDenied, BadRequest,
)
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.base import TemplateResponseMixin, View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormMixin, ModelFormMixin


if TYPE_CHECKING:
  from collections.abc import Mapping
  from typing import Any, Protocol, Sequence
  from django import forms
  from django.db.models import Model
  from django.http import HttpRequest, QueryDict
  from django_htmx.middleware import HtmxDetails

  class HtmxRequest(Protocol):
    htmx: HtmxDetails
    method: str
    FILES: Any
    QUERY: QueryDict
    BODY: QueryDict

  class FormClassWithBaseFields[_F: forms.BaseForm](Protocol):
    base_fields: Mapping[str, object]

    def __call__(
      self,
      *args: Any,
      **kwargs: Any,
    ) -> _F:
      ...

  class SupportsSetup(Protocol):
    def setup(
      self,
      request: HttpRequest,
      *args: Any,
      **kwargs: Any,
    ) -> None:
      ...

  class SupportsContextData(Protocol):
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
      ...


class HtmxTemplateResponseMixin(TemplateResponseMixin):
  """Render template responses inline for HTMX requests."""

  def _finalize_htmx_response(
    self,
    response: HttpResponse,
    **context: 'Any',
  ) -> HttpResponse:
    request = cast('HtmxRequest', self.request)
    if request.htmx:
      context_mixin = cast('SupportsContextData', self)
      rendered_context = context_mixin.get_context_data(**context)
      response = self.render_to_response(rendered_context)
    return response


class HtmxFormMixin[_F: forms.BaseForm](
  HtmxTemplateResponseMixin,
  FormMixin[_F],
):
  """Mixin for facilitating HTMX submission of forms.

  Notes
  -----
  This mixin should come before any other form related mixins/views.

  """

  def form_valid(self, form: _F) -> HttpResponse:
    """The POST/Redirect/GET pattern is not necessary with HTMX.

    Notes
    -----
    In order to prevent extra db queries, we must pass the `form`
    to `get_context_data()`, otherwise Django's FormMixin will
    call `get_form()` a second time.
    """
    response = super().form_valid(form)
    return self._finalize_htmx_response(response, form=form)

  def form_invalid(self, form: _F) -> HttpResponse:
    """Retarget form errors."""
    response = super().form_invalid(form)
    request = cast('HtmxRequest', self.request)

    if request.htmx:
      if request.htmx.trigger is None:
        message = (
          "HtmxFormMixin requires that requests are triggered by a form "
          "with an HTML id and matching partial block name."
        )
        raise ImproperlyConfigured(message)
      response['HX-Retarget'] = f'#{request.htmx.trigger}'
      response['HX-Reswap'] = 'outerHTML'
    return response


class HyperFormMixin[_F: forms.BaseForm](HtmxFormMixin[_F]):
  """Add support for all HTTP Verbs to Django's FormMixin."""

  http_method_names: Sequence[str] = ('get', 'post', 'put', 'patch', 'delete')

  def get_initial(self) -> dict[str, Any]:
    initial = super().get_initial()

    assert self.form_class is not None
    request = cast('HtmxRequest', self.request)
    form_class = cast('FormClassWithBaseFields[_F]', self.form_class)

    form_method = getattr(form_class, 'method', '').upper()
    # TODO: Or if self.http_method_names != ['get']?
    if form_method != 'GET' and request.QUERY:
      # Pass relevant URL params to the form as initial values
      initial.update({
        key: value
        for key, value in request.QUERY.dict().items()
        if key in form_class.base_fields
      })
    return initial

  def get_form_kwargs(self) -> dict[str, Any]:
    """Allow all HTTP verbs and facilitate GET forms.

    Notes
    -----
    In the case of GET forms, it's imperative that we set the `data` form kwarg
    to `self.get_initial()` in order to actually bind the initial data to the
    form and get a proper response. Otherwise, initial data is simply for
    presentation and will not contribute towards satisfying `form.is_valid()`.
    However, if data is submitted we want that to take precedence over
    `self.get_initial()`.

    """
    request = cast('HtmxRequest', self.request)

    kwargs = super().get_form_kwargs()
    # TODO: or if self.http_method_names == ['get']?
    if getattr(self.form_class, 'method', '').upper() == 'GET':
      if data := (request.QUERY or kwargs.get('initial')):
        kwargs.update({
          'data': data,
          'files': request.FILES,
        })
      else:
        # Must avoid binding the form by passing an empty dict to `data`
        pass
    elif request.method != 'GET':
      kwargs.update({
        'data': request.BODY,
        'files': request.FILES,
      })
    return kwargs

  def form_valid(self, form: _F) -> HttpResponse:
    """Proper response handling per HTTP verb."""
    if self.request.method == 'GET':
      message = (
        "Views that inherit from HyperFormMixin must implement "
        "a custom `form_valid()` for forms with [method=get]."
      )
      raise ImproperlyConfigured(message)
    return super().form_valid(form)


class ProcessHyperFormView[_F: forms.BaseForm](HyperFormMixin[_F], View):
  """Render a form on GET and facilitate processing on any verb."""

  def get(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    form = self.get_form()
    if form.is_valid():
      response = self.form_valid(form)
    elif form.is_bound:
      response = self.form_invalid(form)
    else:
      # Render the initial GET
      response = self.render_to_response(self.get_context_data(form=form))
    return response

  def process_form(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    form = self.get_form()
    if form.is_valid():
      response = self.form_valid(form)
    else:
      response = self.form_invalid(form)
    return response

  def post(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    return self.process_form(request, *args, **kwargs)

  def put(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    return self.process_form(request, *args, **kwargs)

  def patch(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    return self.process_form(request, *args, **kwargs)

  def delete(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> HttpResponse:
    """No form validation is performed for DELETE requests."""
    message = (
      "ProcessHyperFormView requires that subclasses define their "
      "own `delete()` methods."
    )
    raise ImproperlyConfigured(message)


class HyperFormView[_F: forms.BaseForm](ProcessHyperFormView[_F]):
  """A view for displaying a form and rendering a template response."""
  pass


class SingleObjectPermissionMixin[_M: Model](SingleObjectMixin[_M]):
  """Adds a permisssions check to SingleObjectMixin."""

  object: _M | None

  def setup(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
  ) -> None:
    cast('SupportsSetup', super()).setup(request, *args, **kwargs)
    if (
      self.pk_url_kwarg in kwargs
      or self.slug_url_kwarg in kwargs
    ):
      # Update or delete object
      self.object = self.get_object(*args, **kwargs)
    else:
      # Create object
      self.object = None

    # Verify the User has CRUD permissions
    if not self.has_permission(request, self.object):
      raise PermissionDenied

  def has_permission(
    self,
    request: HttpRequest,
    obj: _M | None,
  ) -> bool:
    message = (
      "SingleObjectPermissionMixin requires that subclasses define a "
      "`has_permission()` method for determining if the request "
      "is allowed or not."
    )
    raise ImproperlyConfigured(message)


class ModelFormView[_M: Model, _F: forms.ModelForm[Any]](
  SuccessMessageMixin[_F],
  SingleObjectPermissionMixin[_M],
  ModelFormMixin[_M, _F],
  HyperFormView[_F],
):
  """Combines Django's CreateView, UpdateView, and DeleteView via HTMX.

  Notes
  -----
  Generally we use the following convention for mapping HTTP verbs to
  CRUD verbs:
    o POST = CREATE: A new object with this payload
    o GET = READ: All objects or one object
    o PUT = UPDATE: All of an existing object's data
    o PATCH = UPDATE: Some of an exisiting object's data
    o DELETE = DELETE: Delete this object

  Furthermore, the following verbs are treated as idempotent:
    o GET
    o PUT
    o DELETE

  """

  http_method_names: Sequence[str] = ('get', 'post', 'patch', 'put', 'delete')

  def form_valid(self, form: _F) -> HttpResponse:
    if self.request.method != 'PATCH':
      return super().form_valid(form)

    self.object = form.save(commit=False)
    self.object.save()

    # PATCH should append related objects instead of replacing them with set().
    for field in self.object._meta.many_to_many:
      values = form.cleaned_data.get(field.name)
      if values is not None:
        getattr(self.object, field.name).add(*values)

    if message := self.get_success_message(form.cleaned_data):
      messages.success(self.request, message)

    response = HttpResponseRedirect(self.get_success_url())
    return self._finalize_htmx_response(response, form=form)

  def delete(
    self,
    request: HttpRequest,
    *args: Any,
    **kwargs: Any,
   ) -> HttpResponse:
    """Delete the object or the requested relationships.

    Notes
    -----
    While DELETE verbs should support both request bodies and URL params,
    we make the opinionated decision to only support URL params.

    """
    assert self.object is not None
    htmx_request = cast('HtmxRequest', request)

    field_names = set(f.name for f in self.object._meta.get_fields())
    param_names = set(htmx_request.QUERY)

    if (related_names := (field_names & param_names)):
      # Do not delete the primary object, only the related data
      for name in related_names:
        field = self.object._meta.get_field(name)
        if field.many_to_many:
          # Remove from ManyToMany relation, no need to save object afterwards
          getattr(self.object, name).remove(*htmx_request.QUERY.getlist(name))
        elif field.one_to_one or field.many_to_one:
          # ForeignKey or OneToOneField, must save object
          if not field.null:
            raise BadRequest
          related_obj = getattr(self.object, name)
          requested_pk = htmx_request.QUERY.get(name)
          if related_obj and (related_obj.pk == requested_pk):
            setattr(self.object, name, None)
            self.object.save(update_fields=[name])
          else:
            raise BadRequest
    else:
      # Delete the object
      self.object.delete()

    if message := self.get_success_message({}):
      messages.error(request, message)

    if cast('HtmxRequest', self.request).htmx:
      # No need to redirect, just render the normal GET response
      response = self.render_to_response(self.get_context_data())
    else:
      response = HttpResponseRedirect(self.get_success_url())
    return response
