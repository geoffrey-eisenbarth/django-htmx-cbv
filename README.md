# Django Class Based Views for HTMX

[![codecov](https://codecov.io/gh/geoffrey-eisenbarth/django-htmx-cbv/graph/badge.svg?token=SWVCMUB48R)](https://codecov.io/gh/geoffrey-eisenbarth/django-htmx-cbv)

`django-htmx-cbv` provides HTMX-friendly mixins and views for common Django class-based view workflows.

## Requirements

- Python 3.14+
- Django 6.0+
- django-htmx

This package assumes Django 6.0 template partial support.
It does not require `django-template-partials`.

## Installation

Install the package and `django-htmx`:

```bash
pip install django-htmx-cbv django-htmx
```

Or with Poetry:

```bash
poetry add django-htmx-cbv django-htmx
```

## Django setup

Add the app to `INSTALLED_APPS`:

```py
INSTALLED_APPS = [
    # ...
    "django_htmx_cbv",
]
```

Add middleware in this order:

```py
MIDDLEWARE = [
    # Django middleware...

    "django_htmx.middleware.HtmxMiddleware",
    "django_htmx_cbv.middleware.HtmxPartialTemplateMiddleware",
    "django_htmx_cbv.middleware.HtmxVaryMiddleware",
    "django_htmx_cbv.middleware.HtmxMessageMiddleware",
    "django_htmx_cbv.middleware.HttpVerbViewMiddleware",

    # Other middleware...
]
```

Notes:

- `django_htmx.middleware.HtmxMiddleware` must run before the `django_htmx_cbv` middleware.
- `HtmxMessageMiddleware` must come after Django's `MessageMiddleware`.
- `HttpVerbViewMiddleware` should come after Django's `CsrfViewMiddleware`.

The package registers a Django system check for the `HtmxMiddleware` dependency/order.

## Template partials

This library expects Django 6.0 partial syntax:

```django
<!doctype html>
<html lang="en">
  <body>
    {% include "messages.html" %}
    {% partialdef main %}
    <main>
      <h1>Example</h1>
      {% partialdef content %}
      <div id="content">Hello</div>
      {% endpartialdef content %}
    </main>
    {% endpartialdef main %}
  </body>
</html>
```

For HTMX requests, `HtmxPartialTemplateMiddleware` rewrites template names to `template.html#partial_name`.

Partial resolution follows this order:

1. `HX-Retarget`
2. `HX-Partial-Name`
3. `request.htmx.target`
4. `DEFAULT_PARTIAL_NAME` setting, which defaults to `"main"`

## Request conventions

`HttpVerbViewMiddleware` adds two request attributes:

- `request.QUERY`: URL parameters as a `QueryDict`
- `request.BODY`: request body data as a `QueryDict`

For `PUT` and `PATCH`, the middleware supports:

- `application/x-www-form-urlencoded`
- `multipart/form-data`

This makes it possible for form-oriented CBVs to treat non-POST verbs more like normal Django form submissions.

## View conventions

The library is intentionally opinionated.

- Plain `TemplateView`, `DetailView`, and `ListView` already work with the middleware in this package.
  Use Django's stock render-only CBVs unless the view itself needs HTMX-aware response logic.
- `HtmxTemplateResponseMixin` is the reusable view-level abstraction for custom CBVs that want to render inline for HTMX requests.
- HTMX form success responses render the normal template response instead of redirecting.
- HTMX form error responses retarget to `#<request.htmx.trigger>`,
  so requests are expected to come from a form element with a stable HTML id.
- `PATCH` many-to-many updates are additive and use `.add(...)` semantics rather than replacement via `.set(...)`.
- `ModelFormView.delete()` only uses URL parameters for relationship deletion.

## Choosing between the middleware and mixins

Use plain Django CBVs when the view just renders a normal template response and HTMX only changes which partial is returned.

Use `HtmxTemplateResponseMixin` when the view itself needs to decide how to finalize a response for HTMX requests.

Use `HtmxFormMixin` when the view is form-oriented and should keep form-specific HTMX behavior like inline success rendering and error retargeting.

Use `HyperFormView` or `ModelFormView` when you want a full HTMX-aware form view with the above behavior and some opinionated defaults.

## Example imports

```py
from django_htmx_cbv.views import (
    HtmxFormMixin,
    HtmxTemplateResponseMixin,
    HyperFormView,
    ModelFormView,
    ProcessHyperFormView,
)
```

## Status

This package is still evolving.
The current API is centered on reusable HTMX behavior for Django CBVs, with explicit middleware and template conventions.
I welcome input from the community on the API design and implementation;
I want this to be something we can all use!
