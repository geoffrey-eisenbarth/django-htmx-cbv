from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.contrib.messages import get_messages
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, QueryDict
from django.http.multipartparser import MultiPartParserError
from django.template.loader import render_to_string
from django.http.response import HttpResponseRedirectBase
from django.utils.cache import patch_vary_headers

from django_htmx.http import HttpResponseClientRedirect
from django_htmx.middleware import HtmxDetails


if TYPE_CHECKING:
  from typing import Any, Callable, Protocol, Sequence
  from django.http import HttpRequest
  from django.template.response import SimpleTemplateResponse

  class HtmxRequest(Protocol):
    htmx: HtmxDetails
    QUERY: QueryDict
    BODY: QueryDict


def _get_htmx_request(request: 'HttpRequest') -> 'HtmxRequest':
  if not isinstance(getattr(request, 'htmx', None), HtmxDetails):
    message = (
      "django_htmx.middleware.HtmxMiddleware must be installed and run "
      "before django_htmx_cbv middleware."
    )
    raise ImproperlyConfigured(message)
  return cast('HtmxRequest', request)


# TODO: PUSH: Make sure CSRF Protection is enabled for hx-put, patch, delete
# TODO: Add note to README about keeping HTMX default for DELETE
# https://github.com/bigskysoftware/htmx/issues/497#issuecomment-2406237261
class HtmxVaryMiddleware:
  """Sets the 'Vary' header to avoid improper caching.

  Notes
  -----
  See https://htmx.org/docs/#caching

  """

  def __init__(
    self,
    get_response: Callable[[HttpRequest], HttpResponse],
  ) -> None:
    self.get_response = get_response

  def __call__(self, request: HttpRequest) -> HttpResponse:
    response = self.get_response(request)
    htmx_request = _get_htmx_request(request)
    if htmx_request.htmx:
      patch_vary_headers(response, ['HX-Request'])
    return response


# TODO PUSH: Do we need CSRF Protection for hx-put, hx-patch, and hx-delete
class HttpVerbViewMiddleware:
  """Adds support for all HTTP verbs.

  Notes
  -----
  Django uses request.GET and request.POST to store QueryDicts
  of the request's URL parameters and body respectively. In an
  attempt to more accurately depict their roles, we store these
  values in request.QUERY and request.BODY.

  """

  def __init__(
    self,
    get_response: Callable[[HttpRequest], HttpResponse],
  ) -> None:
    self.get_response = get_response

  def __call__(self, request: HttpRequest) -> HttpResponse:
    return self.get_response(request)

  def process_view(
    self,
    request: HttpRequest,
    view_func: Callable[[HttpRequest], HttpResponse],
    view_args: Any,
    view_kwargs: Any,
  ) -> None:
    htmx_request = _get_htmx_request(request)
    htmx_request.QUERY = request.GET.copy()
    htmx_request.BODY = QueryDict()

    if request.method in ['GET', 'DELETE']:
      pass
    elif request.method == 'POST':
      htmx_request.BODY = request.POST.copy()
    elif request.method in ['PUT', 'PATCH']:
      if request.content_type == 'application/x-www-form-urlencoded':
        htmx_request.BODY = QueryDict(request.body)
      elif request.content_type == 'multipart/form-data':
        try:
          body, files = request.parse_file_upload(request.META, request)
        except MultiPartParserError as exc:
          raise ImproperlyConfigured(str(exc)) from exc
        htmx_request.BODY = body.copy()
        cast('Any', request)._post = body
        cast('Any', request)._files = files

    if not htmx_request.htmx:
      if _method := (
        htmx_request.BODY.get('_method')
        or htmx_request.QUERY.get('_method')
      ):
        request.method = _method.upper()


class HtmxPartialTemplateMiddleware:
  """Adds support for rendering partials."""

  default_partial_name = getattr(
    settings,
    'DEFAULT_PARTIAL_NAME',
    'main',
  )

  def __init__(
    self,
    get_response: Callable[[HttpRequest], HttpResponse],
  ) -> None:
    self.get_response = get_response

  def __call__(self, request: HttpRequest) -> HttpResponse:
    response = self.get_response(request)
    htmx_request = _get_htmx_request(request)
    if htmx_request.htmx and isinstance(response, HttpResponseRedirectBase):
      response = HttpResponseClientRedirect(response.url)
    return response

  def process_template_response(
    self,
    request: HttpRequest,
    response: SimpleTemplateResponse,
  ) -> SimpleTemplateResponse:
    htmx_request = _get_htmx_request(request)
    if htmx_request.htmx:
      if retarget_id := response.get('HX-Retarget'):
        partial_name = retarget_id.strip('#')
      elif partial_name := response.get('HX-Partial-Name', ''):
        # Allow the view to specify the partial name
        pass
      else:
        partial_name = htmx_request.htmx.target or self.default_partial_name

      template_name = response.template_name
      if template_name is None:
        return response
      if isinstance(template_name, str):
        template_names = [template_name]
      else:
        template_names = list(cast('Sequence[str]', template_name))

      response.template_name = [
        f'{name}#{partial_name}'
        if '#' not in name
        else name
        for name in template_names
      ]
    return response


# https://github.com/bblanchon/django-htmx-messages-framework/
# https://github.com/abe-101/django-htmx-messages
class HtmxMessageMiddleware:
  """Middleware to add HTMX support to messages framework.

  Notes
  -----
  This code comes from Benoit Blanchon:
    https://github.com/bblanchon/django-htmx-messages-framework/tree/oob

  This come come AFTER django.contrib.messages.middleware.MessageMiddleware
  in the setting's MIDDLEWARE list!

  Since our <output#messages/> element is not located in the <main/> element,
  where most HTMX partials are swapped, we must render the messages.html
  template for every response, in order to "clear out" old messages via an
  OOB swap. It would be more efficient to include the <output#messages/>
  element inside the normal HX-Target area, however this would require
  something like {% include 'messages.html' %} in every template, unless
  we changed the django-render-block logic.

  """

  messages_template = getattr(
    settings,
    'MESSAGES_TEMPLATE_NAME',
    'messages.html',
  )

  def __init__(
    self,
    get_response: Callable[[HttpRequest], HttpResponse],
  ) -> None:
    self.get_response = get_response

  def __call__(self, request: HttpRequest) -> HttpResponse:

    response = self.get_response(request)

    if 'HX-Request' not in request.headers:
      # Not an HTMX request, so full page rendering will pick up the message
      return response
    elif 300 <= response.status_code < 400:
      # Ignore redirections because HTMX cannot read the body
      return response
    elif 'HX-Redirect' in response.headers:
      # Ignore client-side redirection because HTMX drops OOB swabs
      return response

    # Add message HTML
    if messages := get_messages(request):
      html = render_to_string(
        template_name=self.messages_template,
        context={'messages': messages},
        request=request,
      )
      if response.status_code == 204:
        # 204: No Content, so replace with a contentful response
        response = HttpResponse(html, status=200)
      else:
        # Write the OOB swap into the response
        response.write(html)
    return response
