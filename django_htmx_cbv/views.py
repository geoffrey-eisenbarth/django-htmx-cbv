from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import (
  ImproperlyConfigured, PermissionDenied, BadRequest,
)
from django.db.models import Model, ManyToManyField
from django.forms import Form
from django.http import (
  HttpRequest, HttpResponse, HttpResponseRedirect,
)
from django.views.generic.base import TemplateResponseMixin, View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormMixin, ModelFormMixin


class HtmxFormMixin:
  """Mixin for facilitating HTMX submission of forms.

  Notes
  -----
  This mixin should come before any other form related mixins/views.

  """

  def form_valid(self, form: Form) -> HttpResponse:
    """The POST/Redirect/GET pattern is not necessary with HTMX.

    Notes
    -----
    In order to prevent extra db queries, we must pass the `form`
    to `get_context_data()`, otherwise Django's FormMixin will
    call `get_form()` a second time!
    """
    response = super().form_valid(form)
    if self.request.htmx:
      context = self.get_context_data(form=form)
      response = self.render_to_response(context)
    return response

  def form_invalid(self, form: Form) -> HttpResponse:
    """Retarget form errors."""
    if settings.DEBUG:
      print(form.errors)
    response = super().form_invalid(form)
    if self.request.htmx:
      if self.request.htmx.trigger is None:
        message = (
          "HtmxFormMixin requires that requests are triggered by a form "
          "with an HTML id and matching partial block name."
        )
        raise ImproperlyConfigured(message)
      response['HX-Retarget'] = f'#{self.request.htmx.trigger}'
      response['HX-Reswap'] = 'outerHTML'
    return response


class HyperFormMixin(FormMixin):
  """Add support for all HTTP Verbs to Django's FormMixin."""

  http_method_names = ['get', 'post', 'put', 'patch', 'delete']

  def get_initial(self) -> dict:
    initial = super().get_initial()
    if self.http_method_names != ['get'] and self.request.QUERY:
      # Pass relevant URL params to the form as initial values
      initial.update({
        key: value
        for key, value in self.request.QUERY.dict().items()
        if key in self.form_class.base_fields
      })
    return initial

  def get_form_kwargs(self) -> dict:
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
    kwargs = super().get_form_kwargs()
    if self.http_method_names == ['get']:
      if data := (self.request.QUERY or kwargs.get('initial')):
        kwargs.update({
          'data': data,
          'files': self.request.FILES,
        })
      else:
        # Must avoid binding the form by passing an empty dict to `data`
        pass
    elif self.request.method != 'GET':
      kwargs.update({
        'data': self.request.BODY,
        'files': self.request.FILES,
      })
    return kwargs

  def form_valid(self, form: Form) -> HttpResponse:
    """Proper response handling per HTTP verb."""
    if self.request.method == 'GET':
      message = (
        "Views that inherit from HyperFormMixin must implement "
        "a custom `form_valid()` for forms with [method=get]."
      )
      raise ImproperlyConfigured(message)

    # FormMixin.form_valid() returns HttpResponseRedirect(success_url)
    response = super().form_valid(form)
    return response


class ProcessHyperFormView(View):
  """Render a form on GET and facilitate processing on any verb."""

  def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
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
    *args,
    **kwargs,
  ) -> HttpResponse:
    form = self.get_form()
    if form.is_valid():
      response = self.form_valid(form)
    else:
      response = self.form_invalid(form)
    return response

  def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    return self.process_form(request, *args, **kwargs)

  def put(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    return self.process_form(request, *args, **kwargs)

  def patch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    return self.process_form(request, *args, **kwargs)

  def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    """No form validation is performed for DELETE requests."""
    message = (
      "ProcessHyperFormView requires that subclasses define their "
      "own `delete()` methods."
    )
    raise ImproperlyConfigured(message)


class HyperFormView(
  TemplateResponseMixin,
  HyperFormMixin,
  ProcessHyperFormView,
):
  """A view for displaying a form and rendering a template response."""
  pass


class SingleObjectPermissionMixin(SingleObjectMixin):
  def setup(self, request, *args, **kwargs) -> None:
    super().setup(request, *args, **kwargs)
    try:
      # Update or delete object
      self.object = self.get_object()
    except AttributeError:
      # Create object
      self.object = None
    else:
      # Verify the User has CRUD permissions
      if not self.has_permission(request, self.object):
        raise PermissionDenied

  def has_permission(self, request: HttpRequest, obj: Model) -> bool:
    message = (
      "SingleObjectPermissionMixin requires that subclasses define a "
      "`has_permission()` method for determining if the request "
      "is allowed or not."
    )
    raise ImproperlyConfigured(message)


class ModelFormView(
  SuccessMessageMixin,
  SingleObjectPermissionMixin,
  ModelFormMixin,
  HyperFormView,
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

  http_method_names = ['get', 'post', 'patch', 'put', 'delete']

  def form_valid(self, form: Form) -> HttpResponse:
    if (self.request.method == 'PATCH'):
      # PATCH should use ManyToManyField.add() instead of ManyToManyField.set()
      for f in self.object._meta.many_to_many:
        f.save_form_data = lambda instance, data: (
          getattr(instance, f.attname).add(*data)
        )
    return super().form_valid(form)

  def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    """Delete the object or the requested relationships.

    Notes
    -----
    While DELETE verbs should support both request bodies and URL params,
    we make the opinionated decision to only support URL params.

    """
    field_names = set(f.name for f in self.object._meta.get_fields())
    param_names = set(request.QUERY)

    for name in (related_names := (field_names & param_names)):
      if isinstance(self.object._meta.get_field(name), ManyToManyField):
        # Remove from ManyToMany relation, no need to save object afterwards
        getattr(self.object, name).remove(*request.QUERY.getlist(name))
      elif (
        (related_obj := getattr(self.object, name)) and
        (requested_pk := request.QUERY.get(name))
      ):
        # ForeignKey or OneToOneField, must save object
        if related_obj.pk == requested_pk:
          setattr(self.object, name, None)
          self.object.save(update_fields=[name])
        else:
          raise BadRequest

    if not related_names:
      # Delete the object itself
      self.object.delete()

    if message := self.get_success_message({}):
      messages.error(request, message)

    if self.request.htmx:
      # No need to redirect, just render the normal GET response
      self.request.method = 'GET'
      response = self.render_to_response(self.get_context_data())
    else:
      response = HttpResponseRedirect(self.get_success_url())
    return response


# TODO PUSH: Review this
class HtmxChainedFormView(HyperFormMixin, ProcessHyperFormView):
  """Allows dynamic chained form fields."""

  def get_options(self) -> dict:
    message = (
      "HtmxChainedFormView requires an implementation "
      "of `get_options()` that returns a dictionary "
      "of the form {field_name: [choices]}. If form "
      "values are required, they should be specified "
      "via `hx-include`."
    )
    raise ImproperlyConfigured(message)

  def get_form_kwargs(self) -> dict:
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

  def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
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
