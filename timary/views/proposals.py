from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from timary.forms import ProposalForm
from timary.models import Client, Proposal
from timary.utils import get_users_localtime, show_alert_message


@login_required()
@require_http_methods(["GET", "POST"])
def create_proposal(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if client.user != request.user:
        raise Http404
    proposal_form = ProposalForm(request.POST or None)
    if request.method == "POST":
        if proposal_form.is_valid():
            proposal_saved = proposal_form.save(commit=False)
            proposal_saved.client = client
            proposal_saved.save()
            messages.success(
                request, "Proposal created!", extra_tags="proposal-created"
            )
            send_url = reverse(
                "timary:send_proposal",
                kwargs={"proposal_id": proposal_saved.id},
            )
            messages.info(
                request,
                {
                    "msg": f"Send {client.name} this proposal now?",
                    "link": send_url,
                },
                extra_tags="send-proposal",
            )
            return render(
                request,
                "proposals/_update.html",
                {
                    "proposal": proposal_saved,
                    "form": ProposalForm(instance=proposal_saved),
                },
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
            proposal_updated = proposal_form.save()
            messages.success(
                request, "Proposal updated!", extra_tags="proposal-updated"
            )
            send_url = reverse(
                "timary:send_proposal",
                kwargs={"proposal_id": proposal_updated.id},
            )
            messages.info(
                request,
                {
                    "msg": f"Send {proposal.client.name} this updated proposal now?",
                    "link": send_url,
                },
                extra_tags="send-proposal",
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
    response = HttpResponse("")
    show_alert_message(response, "success", f"Proposal sent to {proposal.client.name}.")
    return response
