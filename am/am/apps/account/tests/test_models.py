"""Test am.apps.account.models."""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.utils.functional import SimpleLazyObject

from am.apps.account.enum import AMHostingPlanTypeEnum
from am.apps.account.models import (
    Account,
    AccountContact,
    Charge,
    DailyBillingRecord,
    LLMPrices,
    PaymentMethod,
    Subscription,
    SubscriptionHosts,
    SubscriptionUser,
    User,
    get_resolved_user,
)
from am.apps.account.signals import new_charge_created
from am.apps.account.tests.mixins import AccountTestCase
from am.common.exceptions import AMConfigurationError, AMValueError


class TestModelHelpers(AccountTestCase):
    """Test the module-level helpers."""

    def test_get_resolved_user(self):
        """Users, lazy users and mocks resolve; anything else raises."""
        user = User.objects.create_user(username="models_resolved", email="models_resolved@example.com")
        anonymous = AnonymousUser()
        self.assertIsNone(get_resolved_user(None))  # type: ignore[arg-type]
        self.assertIs(get_resolved_user(user), user)
        self.assertIs(get_resolved_user(anonymous), anonymous)
        lazy = SimpleLazyObject(lambda: user)
        str(lazy)  # evaluate the lazy object
        self.assertEqual(get_resolved_user(lazy), user)
        self.assertEqual(get_resolved_user(SimpleLazyObject(lambda: "wrapped")), "wrapped")
        magic = mock.MagicMock()
        self.assertIs(get_resolved_user(magic), magic)
        with self.assertRaises(AMConfigurationError):
            get_resolved_user("not a user")  # type: ignore[arg-type]


class TestAccountModel(AccountTestCase):
    """Test Account."""

    def test_account_number_is_generated(self):
        """A new account gets a random, valid, unique account number."""
        account = Account.objects.create(company_name="Models Co")
        self.assertRegex(account.account_number, r"^\d{4}-\d{4}-\d{4}$")
        self.assertNotEqual(account.account_number, "9999-9999-9999")
        self.assertEqual(str(account), f"{account.account_number} - Models Co")

    def test_explicit_account_number_is_kept(self):
        """An explicit account number is kept; an invalid one raises."""
        account = Account.objects.create(company_name="Models Co", account_number="1234-5678-0001")
        self.assertEqual(account.account_number, "1234-5678-0001")
        with self.assertRaises(AMValueError):
            Account.objects.create(company_name="Models Bad Co", account_number="not-a-number")

    def test_randomized_account_number_avoids_collisions(self):
        """A generated number that is already taken is generated again."""
        Account.objects.create(company_name="Models Co", account_number="0001-0002-0003")
        with mock.patch("am.apps.account.models.random.randint", side_effect=[1, 2, 3, 4, 5, 6]):
            self.assertEqual(Account.randomized_account_number(), "0004-0005-0006")


class TestAccountContactModel(AccountTestCase):
    """Test AccountContact."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Contacts Co")

    def test_new_contact_is_not_emailed(self):
        """Saving a contact sends no email: Smarter, not Account Manager, welcomes its users."""
        contact = AccountContact.objects.create(
            account=self.account, first_name="jane", last_name="Doe", email="jane@example.com"
        )
        contact.phone = "555-0100"
        contact.save()
        self.send_email.assert_not_called()
        self.assertEqual(str(contact), "jane Doe")

    def test_test_contact_is_quiet(self):
        """A test contact's emails are sent in quiet mode."""
        contact = AccountContact.objects.create(
            account=self.account, first_name="T", last_name="T", email="t@example.com", is_test=True
        )
        contact.send_email(subject="Hi", body="Body")
        self.assertTrue(self.send_email.call_args.kwargs["quiet"])

    def test_send_email(self):
        """Send_email() passes its arguments to the email helper."""
        contact = AccountContact.objects.create(
            account=self.account, first_name="A", last_name="B", email="ab@example.com"
        )
        contact.send_email(subject="Hi", body="Body", from_email="from@example.com")
        self.send_email.assert_called_once_with(
            subject="Hi", to="ab@example.com", body="Body", html=False, from_email="from@example.com", quiet=False
        )

    def test_only_one_primary_contact(self):
        """A second primary contact raises; re-saving the primary one does not."""
        primary = AccountContact.objects.create(
            account=self.account, first_name="P", last_name="P", email="p@example.com", is_primary=True
        )
        primary.save()
        with self.assertRaises(AMValueError):
            AccountContact.objects.create(
                account=self.account, first_name="Q", last_name="Q", email="q@example.com", is_primary=True
            )


class TestBillingModels(AccountTestCase):
    """Test PaymentMethod, LLMPrices, Charge and DailyBillingRecord."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Billing Co")
        cls.user = User.objects.create_user(username="billing_user", email="billing@example.com")

    def test_payment_method_str(self):
        """A payment method is shown as its card type and last four digits."""
        payment_method = PaymentMethod.objects.create(
            account=self.account,
            name="card",
            stripe_id="test-stripe-id",
            card_type="visa",
            card_last_4="4242",
            card_exp_month="12",
            card_exp_year="2030",
        )
        self.assertEqual(str(payment_method), "visa 4242")

    def test_llm_prices_str(self):
        """A price is shown with its charge type, provider and model."""
        price = LLMPrices.objects.create(charge_type="completion", provider="openai", model="gpt-4", price="1.5")
        self.assertEqual(str(price), "completion - openai - gpt-4 - 1.5")

    def test_charge_sends_signal_once(self):
        """A new charge sends new_charge_created; an update does not."""
        receiver = mock.MagicMock()
        new_charge_created.connect(receiver, dispatch_uid="test_charge_sends_signal_once")
        self.addCleanup(new_charge_created.disconnect, dispatch_uid="test_charge_sends_signal_once")

        charge = Charge.objects.create(
            account=self.account,
            user=self.user,
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            model="gpt-4",
            reference="ref",
        )
        receiver.assert_called_once()
        self.assertEqual(receiver.call_args.kwargs["charge"], charge)
        charge.reference = "other"
        charge.save()
        receiver.assert_called_once()
        self.assertEqual(str(charge), f"{self.account.account_number} - billing@example.com - openai - completion - 3")

    def test_daily_billing_record_str(self):
        """A daily billing record is shown with its account, user, provider, date and tokens."""
        record = DailyBillingRecord.objects.create(
            account=self.account,
            user=self.user,
            provider="openai",
            date=date(2026, 1, 2),
            charge_type="completion",
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        )
        self.assertEqual(str(record), f"{self.account.account_number} - billing@example.com - openai - 2026-01-02 - 3")


class TestSubscriptionModels(AccountTestCase):
    """Test Subscription, SubscriptionHosts and SubscriptionUser."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Subscription Co")
        cls.subscription = Subscription.objects.create(
            account=cls.account, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
        )

    def test_default_plan_type(self):
        """The default plan type is saved and read back as multitenant."""
        subscription = Subscription.objects.get(pk=self.subscription.pk)
        self.assertEqual(subscription.plan_type, AMHostingPlanTypeEnum.MULTITENANT)
        self.assertEqual(subscription.get_plan_type_display(), "Multitenant")
        self.assertEqual(str(subscription), f"{self.account.account_number} - Multitenant - 2026-12-31")

    def test_unknown_plan_type_display(self):
        """An unknown plan type is displayed as unknown."""
        self.assertEqual(Subscription(plan_type=99).get_plan_type_display(), "unknown")

    def test_end_date_before_start_date(self):
        """An end date before the start date raises."""
        with self.assertRaises(AMValueError):
            Subscription.objects.create(
                account=self.account, start_date=date(2026, 2, 1), end_date=date(2026, 1, 1) - timedelta(days=1)
            )

    def test_subscription_host(self):
        """A host name is lower-cased; an invalid one raises."""
        host = SubscriptionHosts.objects.create(subscription=self.subscription, host_name="Platform.Example.COM")
        self.assertEqual(host.host_name, "platform.example.com")
        self.assertEqual(str(host), f"{self.account.account_number} - platform.example.com")
        with self.assertRaises(AMValueError):
            SubscriptionHosts.objects.create(subscription=self.subscription, host_name="not a host!")

    def test_subscription_user(self):
        """A subscription user is shown with the account number and email."""
        user = User.objects.create_user(username="subscription_user", email="sub@example.com")
        subscription_user = SubscriptionUser.objects.create(subscription=self.subscription, user=user)
        self.assertEqual(str(subscription_user), f"{self.account.account_number} - sub@example.com")
