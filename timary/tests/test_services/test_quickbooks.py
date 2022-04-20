from django.test import Client, TestCase
from django.test.client import RequestFactory
from httmock import HTTMock, all_requests
from requests import Response

from timary.services.quickbook_service import QuickbookService
from timary.tests.factories import UserFactory


class TestQuickbooksService(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()

    @all_requests
    def quickbook_oauth_mock(self, url, request):
        r = Response()
        r.status_code = 200
        r._content = b'{"refresh_token": "abc123", "access_token": "abc123"}'
        return r

    def test_oauth(self):
        rf = RequestFactory()
        get_request = rf.get("/quickbook-redirect?code=abc123&realmId=abc123")
        get_request.user = self.user

        with HTTMock(self.quickbook_oauth_mock):
            mock_request_token = QuickbookService.get_auth_tokens(get_request)
            self.assertEquals(mock_request_token, "abc123")
