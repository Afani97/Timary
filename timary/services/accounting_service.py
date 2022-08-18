class AccountingService:
    def __init__(self, kwargs):
        self.kwargs = kwargs

    def get_connected_accounting_service(self):
        service = self.kwargs.get("service")
        return globals()[service].get_auth_url()
