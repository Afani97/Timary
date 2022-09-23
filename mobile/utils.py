from django.shortcuts import render


def render_xml(r, t, c=None):
    return render(
        r,
        f"mobile/{t}",
        context=c,
        content_type="application/xml",
    )
