# pylint: disable=W0613
"""Views for React authentication using DRF and SimpleJWT."""

from http import HTTPStatus

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class LoginView(TokenObtainPairView):
    """
    Custom view for handling React login requests.

    Extends the TokenObtainPairView to provide JWT tokens upon successful authentication.
    """

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for user login.

        Returns access and refresh tokens upon successful authentication.
        """

        response = super().post(request, *args, **kwargs)

        if not isinstance(response, Response) or response.status_code != HTTPStatus.OK:
            return response

        return Response(
            {
                "access": response.data.get("access"),
                "refresh": response.data.get("refresh"),
            }
        )

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests.

        Typically not used for login.
        """
        return Response({"detail": 'Method "GET" not allowed. Use "POST".'}, status=HTTPStatus.METHOD_NOT_ALLOWED)


class CookieTokenRefreshView(TokenRefreshView):
    """
    Custom view for handling React token refresh requests.

    Extends the TokenRefreshView to provide a new access token using a refresh token.
    """

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for refreshing JWT tokens.

        Returns a new access token if the provided refresh token is valid.
        """
        refresh = request.COOKIES.get("refresh_token")
        if not refresh:
            raise InvalidToken("No refresh token cookie found.")

        serializer = self.get_serializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0]) from e

        return Response({"access": serializer.validated_data.get("access")})

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests.

        Typically not used for login.
        """
        return Response({"detail": 'Method "GET" not allowed. Use "POST".'}, status=HTTPStatus.METHOD_NOT_ALLOWED)


class LogoutView(APIView):
    """Custom view for handling React logout requests."""

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for user logout.

        Clears the refresh token cookie.
        """
        response = Response({"detail": "Logout successful."})
        response.delete_cookie("refresh_token")
        return response

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests.

        Typically not used for login.
        """
        return Response({"detail": 'Method "GET" not allowed. Use "POST".'}, status=HTTPStatus.METHOD_NOT_ALLOWED)
