from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)

        if not username or not password:
            return None

        user_model = get_user_model()
        users = user_model._default_manager.filter(email__iexact=username)
        if users.exists():
            user = users.first()
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return super().authenticate(request, username=username, password=password, **kwargs)
