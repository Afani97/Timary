import sys

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMultiAlternatives
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from weasyprint import CSS, HTML

from timary.forms import ProposalForm
from timary.models import Client, Proposal
from timary.utils import get_users_localtime, show_alert_message

PROPOSAL_TEMPLATE = """
<div>Dear {client_name},
<br><br>I am very excited to work with you on....
<br><br>As discussed, please find my offer below, which outlines the project scope, deliverables,
schedule and pricing details.
<br><br>This quote is good for <strong>30</strong> days from delivery.
<br><br>Please let me know if you have any questions.&nbsp;
<br><br>{first_name} {last_name}
</div>
<div>
    <br>
</div>
<div><strong>Description of Services</strong>
</div>
<div>
Type your text here...
<br><br><br>
</div>
<div>
<strong>Deliverables</strong>
</div>
<div>
Type your text here...
<br><br><br>
</div>
<div>
<strong>Project Schedule</strong>
</div>
<div>
Type your text here...
<br><br><br>
</div>
<div>
<strong>Pricing and Rates</strong>
</div>
<div>
Type your text here...
<br><br><br>
</div>
<div>
<strong>Payment Terms and Schedule</strong>
</div>
<div>
Type your text here...
</div>
<div>
<br>
</div>
"""


@login_required()
@require_http_methods(["GET", "POST"])
def create_proposal(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if client.user != request.user:
        raise Http404
    proposal_body = PROPOSAL_TEMPLATE.format(
        client_name=client.name,
        first_name=client.user.first_name,
        last_name=client.user.last_name,
    )
    proposal_form = ProposalForm(request.POST or None, initial={"body": proposal_body})
    if request.method == "POST":
        if proposal_form.is_valid():
            proposal_saved = proposal_form.save(commit=False)
            proposal_saved.client = client
            proposal_saved.save()
            messages.success(
                request, "Proposal created!", extra_tags="proposal-created"
            )
            return redirect(
                reverse(
                    "timary:update_proposal", kwargs={"proposal_id": proposal_saved.id}
                )
            )
        else:
            messages.warning(
                request, "Unable to create proposal", extra_tags="proposal-warning"
            )
            return render(
                request,
                "proposals/_create.html",
                {"form": proposal_form, "client": client},
            )

    response = render(
        request, "proposals/_create.html", {"form": proposal_form, "client": client}
    )
    return response


@login_required()
@require_http_methods(["GET", "POST"])
def update_proposal(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    if proposal.client.user != request.user:
        raise Http404
    proposal_form = ProposalForm(request.POST or None, instance=proposal)
    if request.method == "POST":
        if proposal_form.is_valid():
            proposal_updated = proposal_form.save(commit=False)
            proposal_updated.save(update_fields=["title", "body"])
            messages.success(
                request, "Proposal updated!", extra_tags="proposal-updated"
            )
            return render(
                request,
                "proposals/_update.html",
                {
                    "proposal": proposal_updated,
                    "form": ProposalForm(instance=proposal_updated),
                },
            )
        else:
            messages.warning(request, "Unable to update proposal", "proposal-warning")
            return render(
                request,
                "proposals/_update.html",
                {"form": proposal_form, "proposal": proposal},
            )

    response = render(
        request,
        "proposals/_update.html",
        {"form": proposal_form, "proposal": proposal},
    )
    return response


@login_required()
@require_http_methods(["DELETE"])
def delete_proposal(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    if proposal.client.user != request.user:
        raise Http404
    proposal.delete()
    response = HttpResponse("")
    response["HX-Redirect"] = "/invoices/manage/"
    show_alert_message(response, "success", "Proposal removed")
    return response


@login_required()
@require_http_methods(["GET"])
def send_proposal(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    if proposal.client.user != request.user:
        raise Http404
    if not proposal.date_send:
        proposal.date_send = get_users_localtime(request.user)
        proposal.save()

    view_proposal_link = request.build_absolute_uri(
        reverse(
            "timary:client_sign_proposal",
            kwargs={"proposal_id": proposal.id},
        )
    )
    msg_body = f"""
Hi {proposal.client.name},

{request.user} has created a proposal for you to view.

Please visit {view_proposal_link} to view and sign the proposal to continue developments.

Attached below is a copy of the proposal.

Regards,
Ari from Timary
ari@usetimary.com
        """
    if proposal.date_client_signed:
        msg_body = f"""
Hi {proposal.client.name},

Attached below is a copy of the proposal {request.user} created.

Regards,
Ari from Timary
ari@usetimary.com
        """

    msg = EmailMultiAlternatives(
        f"A proposal for work from {request.user.first_name}",
        msg_body,
        settings.DEFAULT_FROM_EMAIL,
        [proposal.client.email],
    )
    proposal_body = render_to_string(
        "proposals/print/print.html", {"proposal": proposal}
    )
    html = HTML(string=proposal_body)
    # Attach copy of pdf just in case
    stylesheet = CSS(string=render_to_string("proposals/print/print.css", {}))
    msg.attach(
        f"{proposal.title}.pdf",
        html.write_pdf(stylesheets=[stylesheet]),
        "application/pdf",
    )
    msg.send(fail_silently=False)

    response = HttpResponse("")
    show_alert_message(response, "success", f"Proposal sent to {proposal.client.name}.")
    return response


@login_required()
@require_http_methods(["GET"])
def download_proposal(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    if proposal.client.user != request.user:
        raise Http404
    proposal_body = render_to_string(
        "proposals/print/print.html", {"proposal": proposal}
    )
    html = HTML(string=proposal_body)
    stylesheet = CSS(string=render_to_string("proposals/print/print.css", {}))
    html.write_pdf(target="/tmp/mypdf.pdf", stylesheets=[stylesheet])

    fs = FileSystemStorage("/tmp")
    with fs.open("mypdf.pdf") as pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{proposal.title}.pdf"'
    return response


@login_required()
@require_http_methods(["GET", "POST"])
def client_sign_proposal(request, proposal_id):
    proposal = get_object_or_404(Proposal, id=proposal_id)
    if proposal.client.user != request.user:
        raise Http404

    if proposal.date_client_signed:
        return redirect(reverse("timary:landing_page"))

    if request.method == "POST":
        client_signature = request.POST.get("client_signature")
        if client_signature is not None and len(client_signature) > 0:
            proposal.client_signature = client_signature
            proposal.date_client_signed = timezone.now()
            proposal.save()

            response = HttpResponse(
                """
                <div class='text-2xl text-center mt-10'>Thank you for using Timary, hope to see you again soon.</div>
                """
            )
            show_alert_message(response, "success", "Signature submitted.")
            msg = EmailMultiAlternatives(
                "A copy of the signed proposal.",
                f"""
Attached below is a copy of the proposal {request.user} created and {proposal.client.name} just signed.

Regards,
Ari from Timary
ari@usetimary.com
                """,
                settings.DEFAULT_FROM_EMAIL,
                [proposal.client.email, request.user.email],
            )
            proposal_body = render_to_string(
                "proposals/print/print.html", {"proposal": proposal}
            )
            html = HTML(string=proposal_body)
            # Attach copy of pdf just in case
            stylesheet = CSS(string=render_to_string("proposals/print/print.css", {}))
            msg.attach(
                f"{proposal.title}.pdf",
                html.write_pdf(stylesheets=[stylesheet]),
                "application/pdf",
            )
            msg.send(fail_silently=False)
            return response
        else:
            response = HttpResponse(status=204)
            show_alert_message(
                response, "error", "Unable to submit signature for proposal"
            )
            print(
                f"Unable to submit signature for proposal: proposal_id={proposal.id}",
                file=sys.stderr,
            )
            return response

    return render(request, "proposals/client_sign.html", {"proposal": proposal})
