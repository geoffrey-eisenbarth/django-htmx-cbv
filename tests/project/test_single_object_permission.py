from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.views.generic.base import View

from django_htmx_cbv.views import SingleObjectPermissionMixin

if TYPE_CHECKING:
  from django.db.models import QuerySet
  from django.http import HttpRequest


class PermissiveView(SingleObjectPermissionMixin[ContentType], View):
  def has_permission(
    self,
    request: HttpRequest,
    obj: ContentType | None,
  ) -> bool:
    return True


class SingleObjectPermissionMixinTest(TestCase):
  def _setup[V: PermissiveView](self, view: V) -> V:
    view.setup(RequestFactory().get("/"))
    return view

  def test_object_is_none_without_pk_or_slug(self) -> None:
    view = self._setup(PermissiveView())
    self.assertIsNone(view.object)

  def test_override_resolves_object_without_url_kwargs(self) -> None:
    instance = ContentType()

    class UserScopedView(PermissiveView):
      def get_object_or_none(
        self,
        queryset: QuerySet[ContentType] | None = None,
      ) -> ContentType | None:
        return instance

    view = self._setup(UserScopedView())
    self.assertIs(view.object, instance)

  def test_denied_permission_raises(self) -> None:
    class DeniedView(PermissiveView):
      def has_permission(
        self,
        request: HttpRequest,
        obj: ContentType | None,
      ) -> bool:
        return False

    with self.assertRaises(PermissionDenied):
      self._setup(DeniedView())
