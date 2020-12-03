# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from diem import identifier, offchain, LocalAccount
import json


def test_entity_kyc_data():
    kyc_data = offchain.entity_kyc_data(
        given_name="hello",
        surname="world",
        address=offchain.AddressObject(city="San Francisco"),
        legal_entity_name="foo bar",
    )
    assert kyc_data.type == offchain.KycDataObjectType.entity


def test_dumps_and_loads_request_command():
    kyc_data = offchain.individual_kyc_data(
        given_name="hello",
        surname="world",
        address=offchain.AddressObject(city="San Francisco"),
        national_id=offchain.NationalIdObject(id_value="234121234"),
        legal_entity_name="foo bar",
    )
    assert offchain.from_json(offchain.to_json(kyc_data), offchain.KycDataObject) == kyc_data
    payment = offchain.PaymentObject(
        reference_id="4185027f05746f5526683a38fdb5de98",
        sender=offchain.PaymentActorObject(
            address="lbr1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t",
            status=offchain.StatusObject(status=offchain.Status.needs_kyc_data),
            kyc_data=kyc_data,
            metadata=["hello", "world"],
        ),
        receiver=offchain.PaymentActorObject(
            address="lbr1p7ujcndcl7nudzwt8fglhx6wxnvqqqqqqqqqqqqelu3xv",
            status=offchain.StatusObject(
                status=offchain.Status.abort, abort_code="code1", abort_message="code1 message"
            ),
        ),
        action=offchain.PaymentActionObject(amount=1_000_000_000_000, currency="Coin1", timestamp=1604902048),
        original_payment_reference_id="0185027f05746f5526683a38fdb5de98",
    )
    assert offchain.from_json(offchain.to_json(payment), offchain.PaymentObject) == payment

    request = offchain.CommandRequestObject(
        command_type=offchain.CommandType.PaymentCommand,
        command=offchain.Command(
            _ObjectType=offchain.CommandType.PaymentCommand,
            payment=payment,
        ),
        cid="3185027f05746f5526683a38fdb5de98",
    )
    assert offchain.from_json(offchain.to_json(request), offchain.CommandRequestObject) == request

    assert json.loads(offchain.to_json(request)) == json.loads(
        """{
  "cid": "3185027f05746f5526683a38fdb5de98",
  "command_type": "PaymentCommand",
  "command": {
    "_ObjectType": "PaymentCommand",
    "payment": {
      "reference_id": "4185027f05746f5526683a38fdb5de98",
      "sender": {
        "address": "lbr1p7ujcndcl7nudzwt8fglhx6wxn08kgs5tm6mz4usw5p72t",
        "status": {
          "status": "needs_kyc_data"
        },
        "kyc_data": {
          "type": "individual",
          "payload_type": "KYC_DATA",
          "payload_version": 1,
          "given_name": "hello",
          "surname": "world",
          "address": {
            "city": "San Francisco"
          },
          "national_id": {
            "id_value": "234121234"
          },
          "legal_entity_name": "foo bar"
        },
        "metadata": [
          "hello",
          "world"
        ]
      },
      "receiver": {
        "address": "lbr1p7ujcndcl7nudzwt8fglhx6wxnvqqqqqqqqqqqqelu3xv",
        "status": {
          "status": "abort",
          "abort_code": "code1",
          "abort_message": "code1 message"
        }
      },
      "action": {
        "amount": 1000000000000,
        "currency": "Coin1",
        "action": "charge",
        "timestamp": 1604902048
      },
      "original_payment_reference_id": "0185027f05746f5526683a38fdb5de98"
    }
  },
  "_ObjectType": "CommandRequestObject"
}"""
    )


def test_dumps_and_loads_response_command():
    response = offchain.CommandResponseObject(
        status=offchain.CommandResponseStatus.success,
        cid="3185027f05746f5526683a38fdb5de98",
    )
    assert offchain.from_json(offchain.to_json(response), offchain.CommandResponseObject) == response
    assert json.loads(offchain.to_json(response)) == json.loads(
        """{
  "status": "success",
  "_ObjectType": "CommandResponseObject",
  "cid": "3185027f05746f5526683a38fdb5de98"
}"""
    )
    response = offchain.CommandResponseObject(
        status=offchain.CommandResponseStatus.failure,
        error=[
            offchain.OffChainErrorObject(
                type=offchain.OffChainErrorType.command_error, code="code2", field="signature", message="abc"
            )
        ],
        cid="3185027f05746f5526683a38fdb5de98",
    )
    assert offchain.from_json(offchain.to_json(response), offchain.CommandResponseObject) == response
    assert json.loads(offchain.to_json(response)) == json.loads(
        """{
  "status": "failure",
  "_ObjectType": "CommandResponseObject",
  "error": [
    {
      "type": "command_error",
      "code": "code2",
      "field": "signature",
      "message": "abc"
    }
  ],
  "cid": "3185027f05746f5526683a38fdb5de98"
}"""
    )


def test_init_payment_request(factory):
    sender = LocalAccount.generate()
    receiver = LocalAccount.generate()
    request = factory.new_payment_command_request(sender, receiver)
    reference_id = request.command.payment.reference_id

    assert reference_id
    assert_cid(request.cid)

    payment = request.command.payment
    address, subaddress = identifier.decode_account(payment.sender.address, identifier.TLB)
    assert subaddress is not None
    assert address == sender.account_address
    address, subaddress = identifier.decode_account(payment.receiver.address, identifier.TLB)
    assert subaddress is not None
    assert address == receiver.account_address

    expected = f"""{{
  "cid": "{request.cid}",
  "command_type": "PaymentCommand",
  "command": {{
    "_ObjectType": "PaymentCommand",
    "payment": {{
      "reference_id": "{reference_id}",
      "sender": {{
        "address": "{payment.sender.address}",
        "status": {{
          "status": "needs_kyc_data"
        }},
        "kyc_data": {{
          "type": "individual",
          "payload_type": "KYC_DATA",
          "payload_version": 1,
          "given_name": "Jack",
          "surname": "G",
          "address": {{
            "city": "San Francisco"
          }}
        }}
      }},
      "receiver": {{
        "address": "{payment.receiver.address}",
        "status": {{
          "status": "none"
        }}
      }},
      "action": {{
        "amount": 1000000000000,
        "currency": "Coin1",
        "action": "charge",
        "timestamp": {payment.action.timestamp}
      }}
    }}
  }},
  "_ObjectType": "CommandRequestObject"
}}"""
    assert json.loads(offchain.to_json(request)) == json.loads(expected)
    assert request == offchain.from_json(expected, offchain.CommandRequestObject)


def test_reply_request():
    resp = offchain.reply_request("cid")
    assert json.loads(offchain.to_json(resp)) == json.loads(
        """{
  "cid": "cid",
  "_ObjectType": "CommandResponseObject",
  "status": "success"
}"""
    )

    resp = offchain.reply_request(
        "cid",
        offchain.OffChainErrorObject(
            type=offchain.OffChainErrorType.command_error, field="kyc_data", code="code1", message="message"
        ),
    )
    assert json.loads(offchain.to_json(resp)) == json.loads(
        """{
  "cid": "cid",
  "_ObjectType": "CommandResponseObject",
  "status": "failure",
  "error": [
    {
      "type": "command_error",
      "code": "code1",
      "field": "kyc_data",
      "message": "message"
    }
  ]
}"""
    )

    resp = offchain.reply_request(
        "cid",
        [
            offchain.OffChainErrorObject(
                type=offchain.OffChainErrorType.command_error, field="kyc_data", code="code1", message="message"
            ),
            offchain.OffChainErrorObject(
                type=offchain.OffChainErrorType.protocol_error, code="code2", message="message2"
            ),
        ],
    )
    assert json.loads(offchain.to_json(resp)) == json.loads(
        """{
  "cid": "cid",
  "_ObjectType": "CommandResponseObject",
  "status": "failure",
  "error": [
    {
      "type": "command_error",
      "code": "code1",
      "field": "kyc_data",
      "message": "message"
    },
    {
      "type": "protocol_error",
      "code": "code2",
      "message": "message2"
    }
  ]
}"""
    )


def assert_cid(cid: str):
    assert isinstance(cid, str)
    assert len(cid) == 16 * 2
