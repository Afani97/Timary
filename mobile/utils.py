from django.http import HttpResponse
from django.shortcuts import render
from render_block import render_block_to_string


def render_xml(r, t, c=None):
    return render(
        r,
        f"mobile/{t}",
        context=c,
        content_type="application/xml",
    )


def render_xml_frag(t, b, c=None):
    xml_block = render_block_to_string(f"mobile/{t}", b, c)
    return HttpResponse(xml_block, content_type="application/xml")
