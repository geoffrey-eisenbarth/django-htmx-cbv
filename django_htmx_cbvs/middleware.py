from django.contrib.messages import get_messages
from django.http import HttpRequest, HttpResponse, QueryDict
from django.template.loader import render_to_string

# TODO: Remove django_htmx requirement? grep for request\.htmx
from django_htmx.http import HttpResponseClientRedirect


# TODO PUSH: Make sure CSRF Protection is enabled for hx-put, hx-patch, and hx-delete
class HttpVerbViewMiddleware:
  """Adds support for all HTTP verbs.

  Notes
  -----
  Django uses request.GET and request.POST to store QueryDicts
  of the request's URL parameters and body respectively. In an
  attempt to more accurately depict their roles, we store these
  values in request.QUERY and request.BODY.

  """

  def __init__(self, get_response) -> None:
    self.get_response = get_response

  def __call__(self, request: HttpRequest) -> HttpResponse:
    return self.get_response(request)

  def process_view(self, request, view_func, view_args, view_kwargs):
    request.QUERY = request.GET.copy()
    request.BODY = request.POST.copy() or QueryDict(request.body)
    if not request.htmx:
      if _method := (request.POST.get('_method') or request.GET.get('_method')):
        request.method = _method.upper()


class HtmxPartialTemplateMiddleware:
  """Adds support for rendering partials."""

  DEFAULT_PARTIAL_NAME = 'main'

  def __init__(self, get_response) -> None:
    self.get_response = get_response

  def __call__(self, request: HttpRequest) -> HttpResponse:
    response = self.get_response(request)
    if request.htmx and (response.status_code == 302):
      response = HttpResponseClientRedirect(response.url)
    return response

  def process_template_response(self, request, response):
    if request.htmx:
      if retarget_id := response.get('HX-Retarget'):
        partial_name = retarget_id.strip('#')
      elif partial_name := response.get('HX-Partial-Name'):
        pass
      else:
        partial_name = request.htmx.target or self.DEFAULT_PARTIAL_NAME

      response.template_name = [
        f'{template_name}#{partial_name}'
        if '#' not in template_name
        else template_name
        for template_name in response.template_name
      ]
    return response


class HtmxVaryMiddleware:
  """Sets the 'Vary' header to avoid improper caching.

  Notes
  -----
  See https://htmx.org/docs/#caching

  """

  def __init__(self, get_response) -> None:
    self.get_response = get_response

  def __call__(self, request: HttpRequest) -> HttpResponse:
    response = self.get_response(request)
    if request.htmx:
      response['Vary'] = 'HX-Request'
    return response


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

  def __init__(self, get_response) -> None:
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
        template_name="messages.html",
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
