import importlib


def class_for_name(class_name):
    # load the module, will raise ImportError if module cannot be loaded
    m = importlib.import_module(f"timary.services.{class_name}_service")
    # get the class, will raise AttributeError if class cannot be found
    c = getattr(m, f"{class_name.title()}Service")
    return c


class AccountingService:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        if "user" in self.kwargs:
            user = self.kwargs.get("user")
            if user.accounting_org:
                self.service_klass = class_for_name(
                    self.kwargs.get("user").accounting_org
                )

    def get_auth_url(self):
        service_klass = class_for_name(self.kwargs.get("service"))
        url, service = service_klass().get_auth_url()
        user = self.kwargs.get("user")
        user.accounting_org = service
        user.save()
        return url

    def get_auth_tokens(self):
        request = self.kwargs.get("request")
        return self.service_klass().get_auth_tokens(request)

    def create_customer(self):
        invoice = self.kwargs.get("invoice")
        self.service_klass.create_customer(invoice)

    def create_invoice(self):
        sent_invoice = self.kwargs.get("sent_invoice")
        self.service_klass.create_invoice(sent_invoice)
