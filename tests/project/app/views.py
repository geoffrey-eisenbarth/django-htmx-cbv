from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView


def redirect_302(request: HttpRequest) -> HttpResponse:
  messages.success(request, 'Message successful!')
  return redirect('page')


class PageView(TemplateView):
  template_name = 'page.html'


class MessageView(PageView):
  def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    messages.success(request, 'Message successful!')
    return super().get(request, *args, **kwargs)


class Message204View(MessageView):
  def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    super().get(request, *args, **kwargs)
    return HttpResponse(status=204)


class HXRetargetView(PageView):
  def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    response = super().get(request, *args, **kwargs)
    response['HX-Retarget'] = 'text'
    return response


class HXPartialNameView(PageView):
  def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
    response = super().get(request, *args, **kwargs)
    response['HX-Partial-Name'] = 'text'
    return response
