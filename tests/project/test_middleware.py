from urllib.parse import urlencode

from bs4 import BeautifulSoup
from parameterized import parameterized

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, QueryDict
from django.test import Client, TestCase
from django.urls import reverse

from django_htmx.http import HttpResponseClientRedirect


class HttpVerbViewMiddlewareTest(TestCase):

  def setUp(self) -> None:
    self.client = Client()

  def tearDown(self) -> None:
    pass

  @parameterized.expand([
    ('GET'),
    ('POST'),
    ('PATCH'),
    ('PUT'),
    ('DELETE'),
  ])
  def test_querydicts(self, method: str) -> None:
    query = 'foo=bar'
    url = reverse('page') + '?' + query

    if method == 'GET':
      body, content_type = '', None
    else:
      content_type = 'application/x-www-form-urlencoded'
      if method in ['POST', 'PATCH', 'PUT']:
        body = urlencode({'int': 1, 'str': '1'})
      elif method == 'DELETE':
        body = ''

    response = getattr(self.client, method.lower())(
      url,
      data=body,
      content_type=content_type,
    )
    request = response.wsgi_request

    self.assertEqual(request.QUERY, QueryDict(query))
    self.assertEqual(request.BODY, QueryDict(body))

  @parameterized.expand([
    ('PATCH'),
    ('PUT'),
    ('DELETE'),
  ])
  def test_method_overriding(self, _method: str) -> None:
    response = self.client.post(
      path=reverse('page'),
      data=urlencode({
        '_method': _method,
        'foo': 'bar',
      }),
      content_type='application/x-www-form-urlencoded',
    )
    request = response.wsgi_request

    self.assertEqual(request.method, _method)


class HtmxVaryMiddlewareTest(TestCase):

  def setUp(self) -> None:
    self.client = Client()

  def test_vary(self) -> None:
    response = self.client.get(
      path=reverse('page'),
      headers={'HX-Request': 'true'},
    )
    self.assertEqual(response.headers['Vary'], 'HX-Request')


class SoupTestCase(TestCase):
  def setUp(self) -> None:
    self.client = Client()

  def get_soup(self, response: HttpResponse) -> BeautifulSoup:
    soup = BeautifulSoup(response.content, features='html.parser')
    return soup


class HtmxPartialTemplateMiddlewareTest(SoupTestCase):

  def test_response_client_redirect(self) -> None:
    response = self.client.get(
      path=reverse('redirect_302'),
      headers={'HX-Request': 'true'},
    )
    self.assertIsInstance(response, HttpResponseClientRedirect)

  def test_process_template_response(self) -> None:
    # Return full HTML response
    response = self.client.get(
      path=reverse('page'),
    )
    soup = self.get_soup(response)
    self.assertIsNotNone(soup.html)

    # Return the default partial name: 'main'
    response = self.client.get(
      path=reverse('page'),
      headers={'HX-Request': 'true'},
    )
    soup = self.get_soup(response)
    self.assertIsNone(soup.html)
    self.assertIsNotNone(soup.main)

    # Return the requested partial: 'text'
    response = self.client.get(
      path=reverse('page'),
      headers={'HX-Request': 'true', 'HX-Target': 'text'},
    )
    soup = self.get_soup(response)
    self.assertIsNone(soup.html)
    self.assertIsNone(soup.main)
    self.assertIsNotNone(soup.p)

    # Honor a HX-Retarget set in the view
    response = self.client.get(
      path=reverse('hx_retarget'),
      headers={'HX-Request': 'true', 'HX-Target': 'main'},
    )
    soup = self.get_soup(response)
    self.assertIsNone(soup.html)
    self.assertIsNone(soup.main)
    self.assertEqual(response['HX-Retarget'], 'text')

    # Honor a HX-Partial-Name set in the view
    response = self.client.get(
      path=reverse('hx_partial_name'),
      headers={'HX-Request': 'true'}
    )
    soup = self.get_soup(response)
    self.assertIsNone(soup.html)
    self.assertIsNone(soup.main)
    self.assertIsNotNone(soup.p)


class HtmxMessageMiddlewareTest(SoupTestCase):
  def test_messages(self) -> None:

    # Verify message in non-HTMX request
    response = self.client.get(
      path=reverse('message'),
    )
    soup = self.get_soup(response)
    self.assertIsNotNone(soup.html)
    self.assertIsNotNone(soup.find('li', class_='success'))

    # Verify message in non-HTMX request as OOB swap
    response = self.client.get(
      path=reverse('message'),
      headers={'HX-Request': 'true'},
    )
    soup = self.get_soup(response)
    self.assertIsNone(soup.html)
    self.assertIsNotNone(soup.find('li', class_='success'))

    # Ignore redirections because HTMX cannot read the body
    response = self.client.get(
      path=reverse('redirect_302'),
      follow=True,
    )
    soup = self.get_soup(response)
    self.assertIsNotNone(soup.html)
    self.assertIsNotNone(soup.find('li', class_='success'))

    # Ignore client-side redirection because HTMX drops OOB swabs
    response = self.client.get(
      path=reverse('redirect_302'),
      headers={'HX-Request': 'true'},
    )
    response = self.client.get(
      path=response.headers['HX-Redirect'],
      # TODO: When htmx does HX-Redirect, does it send headers?
      #headers={'HX-Request': 'true'},
    )
    soup = self.get_soup(response)
    self.assertIsNotNone(soup.html)
    self.assertIsNotNone(soup.find('li', class_='success'))

    # A 204 response should be converted to a 200 response
    response = self.client.get(
      path=reverse('message_204'),
      headers={'HX-Request': 'true'},
    )
    self.assertEqual(response.status_code, 200)
    soup = self.get_soup(response)
    self.assertIsNotNone(soup.find('li', class_='success'))
