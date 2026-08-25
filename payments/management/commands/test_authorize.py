from django.core.management.base import BaseCommand
from django.conf import settings

from authorizenet import apicontractsv1
from authorizenet.apicontrollers import getMerchantDetailsController
from authorizenet.constants import constants


class Command(BaseCommand):
    help = "Test the Authorize.net API connection without creating a transaction."

    def handle(self, *args, **options):
        self.stdout.write("Testing Authorize.net connection...\n")

        # Check Django settings
        login_id = settings.AUTHORIZE_LOGIN_ID
        transaction_key = settings.AUTHORIZE_TRANSACTION_KEY

        if not login_id:
            self.stdout.write(
                self.style.ERROR("AUTHORIZE_LOGIN_ID is missing.")
            )
            return

        if not transaction_key:
            self.stdout.write(
                self.style.ERROR("AUTHORIZE_TRANSACTION_KEY is missing.")
            )
            return

        self.stdout.write(
            f"Login ID found: {login_id}"
        )

        self.stdout.write(
            f"Environment: {getattr(settings, 'AUTHORIZE_ENVIRONMENT', 'sandbox')}"
        )

        # Create merchant authentication
        merchant_auth = apicontractsv1.merchantAuthenticationType()
        merchant_auth.name = login_id
        merchant_auth.transactionKey = transaction_key

        # Build request
        request = apicontractsv1.getMerchantDetailsRequest()
        request.merchantAuthentication = merchant_auth

        # Send request
        controller = getMerchantDetailsController(request)

        # The SDK defaults to the sandbox endpoint on every controller
        # instantiation, so it must be pointed at production explicitly
        # for live credentials or Authorize.net rejects them with E00007.
        environment = getattr(settings, "AUTHORIZE_ENVIRONMENT", "sandbox").lower()
        if environment in ("live", "production"):
            controller.setenvironment(constants.PRODUCTION)
        else:
            controller.setenvironment(constants.SANDBOX)

        try:
            controller.execute()
            response = controller.getresponse()

            if response is None:
                self.stdout.write(
                    self.style.ERROR(
                        "No response received from Authorize.net."
                    )
                )
                return

            if response.messages.resultCode == "Ok":
                self.stdout.write(
                    self.style.SUCCESS(
                        "\nSUCCESS: Authorize.net API connection works!"
                    )
                )

                self.stdout.write(
                    f"Merchant name: {response.merchantName}"
                )

                # merchantId isn't always present in the response payload.
                merchant_id = getattr(response, "merchantId", None)
                if merchant_id is not None:
                    self.stdout.write(
                        f"Merchant ID: {merchant_id}"
                    )

            else:
                self.stdout.write(
                    self.style.ERROR(
                        "\nAuthorize.net rejected the request."
                    )
                )

                if response.messages.message is not None:
                    for message in response.messages.message:
                        self.stdout.write(
                            f"Code: {message.code}"
                        )
                        self.stdout.write(
                            f"Message: {message.text}"
                        )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"\nConnection failed: {e}"
                )
            )