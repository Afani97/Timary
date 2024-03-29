import importlib


def class_for_name(class_name):
    if class_name not in ["quickbooks", "freshbooks", "zoho", "xero", "sage"]:
        return None
    # load the module, will raise ImportError if module cannot be loaded
    m = importlib.import_module(f"timary.services.{class_name}_service")
    # get the class, will raise AttributeError if class cannot be found
    c = getattr(m, f"{class_name.title()}Service")
    return c


class AccountingService:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.service_klass = None
        if "user" in self.kwargs:
            user = self.kwargs.get("user")
            if user.accounting_org:
                service_klass = class_for_name(user.accounting_org)
                if service_klass:
                    self.service_klass = service_klass

    def get_auth_url(self):
        service_klass = class_for_name(self.kwargs.get("service"))
        if not service_klass:
            return None
        url, service = service_klass().get_auth_url()
        user = self.kwargs.get("user")
        user.accounting_org = service
        user.save()
        return url

    def get_auth_tokens(self):
        request = self.kwargs.get("request")
        if self.service_klass:
            return self.service_klass().get_auth_tokens(request)

    def refresh_tokens(self):
        user = self.kwargs.get("user")
        if self.service_klass:
            self.service_klass().refresh_tokens(user)

    def get_request_auth_token(self):
        user = self.kwargs.get("user")
        if self.service_klass:
            return self.service_klass().get_refreshed_tokens(user)

    def create_customer(self):
        client = self.kwargs.get("client")
        if self.service_klass and client.user.settings["subscription_active"]:
            self.service_klass().create_customer(client)

    def get_customers(self):
        user = self.kwargs.get("user")
        if self.service_klass and user.settings["subscription_active"]:
            return self.service_klass().get_customers(user)

    def update_customer(self):
        client = self.kwargs.get("client")
        if self.service_klass and client.user.settings["subscription_active"]:
            self.service_klass().update_customer(client)

    def create_invoice(self):
        sent_invoice = self.kwargs.get("sent_invoice")
        if self.service_klass and sent_invoice.user.settings["subscription_active"]:
            self.service_klass().create_invoice(sent_invoice)

    def test_integration(self):
        user = self.kwargs.get("user")
        if self.service_klass:
            self.service_klass().test_integration(user)
