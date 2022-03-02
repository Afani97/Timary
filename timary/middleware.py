class SimpleUserAgentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request.is_mobile = "Mobile" in request.META.get("HTTP_USER_AGENT", "")
        response = self.get_response(request)

        return response
