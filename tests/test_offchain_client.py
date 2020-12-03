# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from diem import offchain, testnet, utils


def test_send_and_deserialize_request(factory):
    receiver_port = offchain.http_server.get_available_port()
    sender = testnet.gen_vasp_account("http://localhost:8888")
    receiver = testnet.gen_vasp_account(f"http://localhost:{receiver_port}")
    sender_client = factory.create_offchain_client(sender)
    receiver_client = factory.create_offchain_client(receiver)

    def process_inbound_request(x_request_id: str, jws_key_address: str, content: bytes):
        request = receiver_client.verify_request(jws_key_address, content)
        resp = offchain.reply_request(request.cid)
        return (200, offchain.jws.serialize(resp, receiver.compliance_key.sign))

    offchain.http_server.start_local(receiver_port, process_inbound_request)

    request = factory.new_payment_command_request(sender, receiver)
    resp = sender_client.send_request(offchain.Role.SENDER, request, sender.compliance_key.sign)
    assert resp
