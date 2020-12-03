# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0


from diem import testnet, offchain, identifier, LocalAccount
import pytest


@pytest.fixture
def factory():
    return Factory()


class Factory:
    def create_offchain_client(self, account):
        return offchain.Client(account.account_address, testnet.create_client(), identifier.TLB)

    def new_payment_command_request(self, sender=LocalAccount.generate(), receiver=LocalAccount.generate()):
        amount = 1_000_000_000_000
        currency = testnet.TEST_CURRENCY_CODE
        sender_account_id = identifier.encode_account(
            sender.account_address, identifier.gen_subaddress(), identifier.TLB
        )
        sender_kyc_data = offchain.individual_kyc_data(
            given_name="Jack",
            surname="G",
            address=offchain.AddressObject(city="San Francisco"),
        )

        receiver_account_id = identifier.encode_account(
            receiver.account_address, identifier.gen_subaddress(), identifier.TLB
        )

        return offchain.init_payment_request(
            sender_account_id,
            sender_kyc_data,
            receiver_account_id,
            amount,
            currency,
        )
