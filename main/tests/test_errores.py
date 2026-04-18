from django.test import TestCase
from django.urls import reverse


class NegativeAuthApiTests(TestCase):
    def test_login_with_invalid_credentials_returns_401(self):
        url = reverse("api_auth_login")
        response = self.client.post(
            url,
            data={"username": "noexiste", "password": "bad-pass"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_register_with_password_mismatch_returns_400(self):
        url = reverse("api_auth_register")
        payload = {
            "first_name": "X",
            "email": "x@example.com",
            "username": "x",
            "password1": "12345678",
            "password2": "87654321",
        }
        response = self.client.post(url, data=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.json())
        self.assertIn("password2", response.json()["errors"])


class NegativeClasificacionApiTests(TestCase):
    def test_clasificacion_without_temporadas_returns_404(self):
        url = reverse("api_clasificacion")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "No hay temporadas"})
