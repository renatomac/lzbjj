from django.shortcuts import redirect


class MemberAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if request.user.is_staff or request.user.is_superuser or request.user.is_coach:
            return self.get_response(request)

        allowed_prefixes = ("/chat", "/timers", "/logout", "/static", "/media", "/change-password")
        if request.path.startswith(allowed_prefixes):
            return self.get_response(request)

        return redirect("chat:chat_home")
