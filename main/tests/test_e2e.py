from django.test import TestCase
from django.urls import reverse


class E2EAuthJourneyTests(TestCase):
    def test_register_me_logout_full_journey(self):
        me_url = reverse("api_me")
        register_url = reverse("api_auth_register")
        logout_url = reverse("api_auth_logout")

        initial_me = self.client.get(me_url)
        self.assertEqual(initial_me.status_code, 200)
        self.assertFalse(initial_me.json()["authenticated"])
        self.assertIn("csrftoken", initial_me.cookies)

        register_payload = {
            "email": "pablo@example.com",
            "username": "pablo",
            "password1": "super-segura-123",
            "password2": "super-segura-123",
        }
        register_response = self.client.post(register_url, data=register_payload)

        self.assertEqual(register_response.status_code, 200)
        self.assertEqual(register_response.json()["status"], "ok")

        after_register_me = self.client.get(me_url)
        self.assertEqual(after_register_me.status_code, 200)
        self.assertTrue(after_register_me.json()["authenticated"])
        self.assertEqual(after_register_me.json()["username"], "pablo")

        logout_response = self.client.post(logout_url)
        self.assertEqual(logout_response.status_code, 200)

        after_logout_me = self.client.get(me_url)
        self.assertEqual(after_logout_me.status_code, 200)
        self.assertFalse(after_logout_me.json()["authenticated"])
