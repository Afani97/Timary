import datetime

from django.core import mail
from django.urls import reverse

from timary.tests.factories import ClientFactory, ProposalFactory, UserFactory
from timary.tests.test_views.basetest import BaseTest
from timary.utils import get_users_localtime


class TestProposals(BaseTest):
    def setUp(self) -> None:
        super().setUp()

        self.user = UserFactory()
        self.client.force_login(self.user)
        self.today = get_users_localtime(self.user)

    @classmethod
    def extract_html(cls):
        s = mail.outbox[0].message().as_string()
        start = s.find("<body>") + len("<body>")
        end = s.find("</body>")
        message = s[start:end]
        return message

    def test_create_proposal(self):
        _client = ClientFactory(user=self.user)
        self.client.post(
            reverse("timary:create_proposal", kwargs={"client_id": _client.id}),
            {
                "title": "New proposal",
                "body": "Proposal body",
                "user_signature": self.user.get_full_name(),
                "date_user_signed": self.today,
            },
        )
        self.assertEqual(_client.proposals.count(), 1)

    def test_create_proposal_error(self):
        _client = ClientFactory(user=self.user)
        self.client.post(
            reverse("timary:create_proposal", kwargs={"client_id": _client.id}),
            {
                "body": "Proposal body",
                "user_signature": self.user.get_full_name(),
                "date_user_signed": self.today,
            },
        )
        self.assertEqual(_client.proposals.count(), 0)

    def test_update_proposal(self):
        proposal = ProposalFactory(
            client__user=self.user,
            date_user_signed=self.today - datetime.timedelta(days=1),
        )
        self.client.post(
            reverse("timary:update_proposal", kwargs={"proposal_id": proposal.id}),
            {
                "title": "Updated proposal",
                "body": "Updated Proposal body",
            },
        )

        proposal.refresh_from_db()
        self.assertEqual(proposal.title, "Updated proposal")

        # Date user signed shouldn't be updated
        self.assertNotEqual(proposal.date_user_signed.date(), self.today.date())

    def test_cannot_update_client_signed_proposal(self):
        proposal = ProposalFactory(
            client__user=self.user,
            date_user_signed=self.today - datetime.timedelta(days=1),
            date_client_signed=self.today,
        )
        response = self.client.post(
            reverse("timary:update_proposal", kwargs={"proposal_id": proposal.id}),
            {
                "title": "Updated proposal",
                "body": "Updated Proposal body",
            },
        )

        self.assertInHTML(
            "Can't update a proposal signed by the client. Create a new one to revise current.",
            response.content.decode(),
        )
        proposal.refresh_from_db()
        # Don't update proposal for wrong user
        self.assertNotEqual(proposal.title, "Updated proposal")

    def test_delete_proposal(self):
        _client = ClientFactory(user=self.user)
        proposal = ProposalFactory(
            client=_client,
            date_user_signed=self.today - datetime.timedelta(days=1),
        )

        self.client.delete(
            reverse("timary:delete_proposal", kwargs={"proposal_id": proposal.id})
        )

        _client.refresh_from_db()
        self.assertEqual(_client.proposals.count(), 0)

    def test_send_pdf_to_client_to_sign(self):
        proposal = ProposalFactory(
            client__user=self.user,
            date_user_signed=self.today - datetime.timedelta(days=1),
        )
        self.client.get(
            reverse("timary:send_proposal", kwargs={"proposal_id": proposal.id})
        )

        msg_body = self.extract_html()
        self.assertIn(f"{self.user} has created a proposal for you to view.", msg_body)

    def test_send_copy_to_client(self):
        proposal = ProposalFactory(
            client__user=self.user,
            client_signature="Signed signature",
            date_client_signed=self.today,
        )
        self.client.get(
            reverse("timary:send_proposal", kwargs={"proposal_id": proposal.id})
        )

        msg_body = self.extract_html()
        self.assertIn(
            f"Attached below is a copy of the proposal {self.user} created.",
            msg_body,
        )

    def test_send_email_after_client_signed(self):
        proposal = ProposalFactory(
            client__user=self.user,
        )
        response = self.client.post(
            reverse("timary:client_sign_proposal", kwargs={"proposal_id": proposal.id}),
            {
                "client_signature": "Bob Smith",
            },
        )

        self.assertIn(
            "Thank you for using Timary, hope to see you again soon.",
            response.content.decode(),
        )

        msg_body = self.extract_html()
        self.assertIn(
            f"Attached below is a copy of the proposal {self.user} created and {proposal.client.name} just signed.",
            msg_body,
        )
