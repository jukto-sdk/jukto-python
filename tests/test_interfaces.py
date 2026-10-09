from jukto.interfaces.logistics import BaseLogisticsProvider, Parcel
from jukto.interfaces.sms import BaseSMSProvider


class DummyLogistics(BaseLogisticsProvider):
    def create_order(self, parcel: Parcel):
        return super().create_order(parcel)

    def check_status(self, consignment_id: str):
        return super().check_status(consignment_id)


class DummySMS(BaseSMSProvider):
    def send_sms(self, phone_numbers, message):
        return super().send_sms(phone_numbers, message)


def test_base_interfaces_pass_methods():
    logistics = DummyLogistics(api_key="k")
    parcel = Parcel(
        invoice_id="1",
        recipient_name="a",
        recipient_phone="01",
        recipient_address="addr",
        cod_amount=10,
    )
    assert logistics.create_order(parcel) is None
    assert logistics.check_status("cid") is None

    sms = DummySMS(api_key="k")
    assert sms.send_sms("01", "m") is None
