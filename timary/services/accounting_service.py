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
        if "user" in self.kwargs:
            user = self.kwargs.get("user")
            if user.accounting_org:
                service_klass = class_for_name(self.kwargs.get("user").accounting_org)
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
            self.service_klass().get_auth_tokens(request)

    def refresh_tokens(self):
        user = self.kwargs.get("user")
        if self.service_klass:
            self.service_klass().refresh_tokens(user)

    def create_customer(self):
        invoice = self.kwargs.get("invoice")
        if self.service_klass:
            self.service_klass().create_customer(invoice)

    def create_invoice(self):
        sent_invoice = self.kwargs.get("sent_invoice")
        if self.service_klass:
            self.service_klass().create_invoice(sent_invoice)

    def sync_customers(self):
        user = self.kwargs.get("user")
        if self.service_klass:
            for invoice in user.get_invoices:
                self.service_klass().create_customer(invoice)

    def sync_invoices(self):
        from timary.models import SentInvoice

        user = self.kwargs.get("user")
        if self.service_klass:
            for sent_invoice in user.sent_invoices.filter(
                paid_status=SentInvoice.PaidStatus.PAID
            ):
                self.service_klass().create_invoice(sent_invoice)
