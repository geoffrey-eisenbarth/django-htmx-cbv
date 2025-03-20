from django.urls import path

from app import views as app_views


urlpatterns = [
  path(
    'page/',
    app_views.PageView.as_view(),
    name='page',
  ),
  path(
    'page/message',
    app_views.MessageView.as_view(),
    name='message',
  ),
  path(
    'page/message-204',
    app_views.Message204View.as_view(),
    name='message_204',
  ),
  path(
    'page/hx-retarget',
    app_views.HXRetargetView.as_view(),
    name='hx_retarget',
  ),
  path(
    'page/hx-partial-name',
    app_views.HXPartialNameView.as_view(),
    name='hx_partial_name',
  ),
  path(
    'redirect_302/',
    app_views.redirect_302,
    name='redirect_302',
  ),
]
