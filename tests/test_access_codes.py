import logging

import pytest

from smartrent import API, SmartRentHTTPError, SmartRentValidationError
from smartrent.utils import (
    SMARTRENT_ACCESS_CODE_URI,
    SMARTRENT_GUEST_ACCESS_CODES_URI,
    SMARTRENT_HUBS_URI,
    SMARTRENT_UNIT_ACCESS_URI,
    Client,
)


class FakeResponse:
    def __init__(self, status, payload=None, reason=None):
        self.status = status
        self._payload = payload
        self.reason = reason

    async def json(self, content_type=None):
        if self._payload is NO_JSON:
            raise ValueError("not JSON")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.closed = False

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)

    async def close(self):
        self.closed = True


NO_JSON = object()


def make_client(*responses):
    session = FakeSession(responses)
    client = Client("resident@example.com", "secret", aiohttp_session=session)
    client._token = "access-token"
    return client, session


@pytest.mark.asyncio
async def test_high_level_hub_discovery_and_unit_access_endpoints():
    hubs = [{"id": 12, "unit_id": 34}]
    access = {
        "config": {},
        "delivery": [],
        "guests": [],
        "resident": {"code": "0012"},
    }
    session = FakeSession([FakeResponse(200, hubs), FakeResponse(200, access)])
    api = API("resident@example.com", "secret", aiohttp_session=session)
    api.client._token = "access-token"

    assert await api.async_get_hubs() == hubs
    result = await api.async_get_unit_access(34)

    assert result["resident"]["code"] == "0012"
    assert session.requests[0][0:2] == ("GET", SMARTRENT_HUBS_URI)
    assert session.requests[1][0:2] == (
        "GET",
        SMARTRENT_UNIT_ACCESS_URI.format(34),
    )
    assert "json" not in session.requests[0][2]
    assert "json" not in session.requests[1][2]


@pytest.mark.asyncio
async def test_create_permanent_guest_code_body_and_leading_zero_response():
    client, session = make_client(FakeResponse(201, {"id": 99, "code": "004321"}))

    result = await client.async_create_guest_access_code(
        34,
        "permanent",
        "Grace",
        "Hopper",
        email="grace@example.com",
    )

    assert result["code"] == "004321"
    method, url, kwargs = session.requests[0]
    assert method == "POST"
    assert url == SMARTRENT_GUEST_ACCESS_CODES_URI.format(34)
    assert kwargs["json"] == {
        "activation_type": "permanent",
        "first_name": "Grace",
        "last_name": "Hopper",
        "email": "grace@example.com",
    }


@pytest.mark.asyncio
async def test_create_temporary_guest_code_uses_production_fields_only():
    client, session = make_client(FakeResponse(201, {"id": 100, "code": "0199"}))

    await client.async_create_guest_access_code(
        34,
        "temporary",
        "Ada",
        "Lovelace",
        phone="+15555550100",
        temporary_start_at="2026-08-16T08:00:00Z",
        temporary_end_at="2026-08-16T20:00:00Z",
        recurring_start_time="09:00",
        recurring_end_time="10:00",
        recurring_repeat_on=["Monday"],
    )

    assert session.requests[0][2]["json"] == {
        "activation_type": "temporary",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "phone": "+15555550100",
        "temporary_start_at": "2026-08-16T08:00:00Z",
        "temporary_end_at": "2026-08-16T20:00:00Z",
    }


@pytest.mark.asyncio
async def test_create_recurring_guest_code_canonicalizes_weekdays():
    client, session = make_client(FakeResponse(201, {"id": 101, "code": "0008"}))

    await client.async_create_guest_access_code(
        34,
        "recurring",
        "Katherine",
        "Johnson",
        email="kj@example.com",
        recurring_start_time="09:15",
        recurring_end_time="17:30:00",
        recurring_repeat_on=["monday", "TUESDAY", "monday", "Sunday"],
    )

    assert session.requests[0][2]["json"] == {
        "activation_type": "recurring",
        "first_name": "Katherine",
        "last_name": "Johnson",
        "email": "kj@example.com",
        "recurring_start_time": "09:15",
        "recurring_end_time": "17:30:00",
        "recurring_repeat_on": ["Monday", "Tuesday", "Sunday"],
    }


@pytest.mark.asyncio
async def test_high_level_activation_convenience_methods():
    responses = [
        FakeResponse(201, {"code": "0001"}),
        FakeResponse(201, {"code": "0002"}),
        FakeResponse(201, {"code": "0003"}),
    ]
    session = FakeSession(responses)
    api = API("resident@example.com", "secret", aiohttp_session=session)
    api.client._token = "access-token"

    permanent = await api.async_create_permanent_guest_access_code(
        34, "A", "One", email="a@example.com"
    )
    temporary = await api.async_create_temporary_guest_access_code(
        34,
        "B",
        "Two",
        "2026-08-16T08:00:00+00:00",
        "2026-08-16T09:00:00+00:00",
        phone="+15555550101",
    )
    recurring = await api.async_create_recurring_guest_access_code(
        34,
        "C",
        "Three",
        "08:00",
        "09:00",
        ["friday"],
        email="c@example.com",
    )

    assert [permanent["code"], temporary["code"], recurring["code"]] == [
        "0001",
        "0002",
        "0003",
    ]
    assert [request[2]["json"]["activation_type"] for request in session.requests] == [
        "permanent",
        "temporary",
        "recurring",
    ]


@pytest.mark.asyncio
async def test_update_guest_code_metadata_and_schedule():
    client, session = make_client(FakeResponse(200, {"id": 9, "code": "0077"}))

    result = await client.async_update_guest_access_code(
        12,
        56,
        9,
        activation_type="recurring",
        first_name="New",
        recurring_start_time="10:00",
        recurring_end_time="12:00",
        recurring_repeat_on=["wednesday", "SATURDAY"],
    )

    assert result["code"] == "0077"
    method, url, kwargs = session.requests[0]
    assert method == "PATCH"
    assert url == SMARTRENT_ACCESS_CODE_URI.format(12, 56, 9)
    assert kwargs["json"] == {
        "activation_type": "recurring",
        "first_name": "New",
        "recurring_start_time": "10:00",
        "recurring_end_time": "12:00",
        "recurring_repeat_on": ["Wednesday", "Saturday"],
    }
    assert "code" not in kwargs["json"]


@pytest.mark.asyncio
async def test_delete_guest_code_accepts_empty_success_response():
    client, session = make_client(FakeResponse(204, NO_JSON))

    assert await client.async_delete_guest_access_code(12, 56, 9) is None

    method, url, kwargs = session.requests[0]
    assert method == "DELETE"
    assert url == SMARTRENT_ACCESS_CODE_URI.format(12, 56, 9)
    assert "json" not in kwargs


@pytest.mark.asyncio
async def test_auth_failure_refreshes_and_retries_with_new_token():
    client, session = make_client(
        FakeResponse(401, {"errors": [{"code": "unauthorized"}]}, "Unauthorized"),
        FakeResponse(200, {"config": {}, "guests": []}),
    )
    refresh_calls = []
    client._token_exp_time = 9999999999

    async def refresh_token():
        assert client._token_exp_time is None
        refresh_calls.append(True)
        client._token = "refreshed-token"

    client._async_refresh_token = refresh_token

    assert await client.async_get_unit_access(34) == {"config": {}, "guests": []}
    assert refresh_calls == [True]
    assert session.requests[0][2]["headers"]["authorization"] == "Bearer access-token"
    assert session.requests[1][2]["headers"]["authorization"] == (
        "Bearer refreshed-token"
    )


@pytest.mark.asyncio
async def test_non_2xx_raises_typed_sanitized_http_error(caplog):
    sensitive_pin = "004321"
    sensitive_contact = "private@example.com"
    payload = {
        "errors": [
            {
                "code": "invalid_request",
                "detail": "PIN {} belongs to {}".format(
                    sensitive_pin, sensitive_contact
                ),
            }
        ]
    }
    client, _ = make_client(
        FakeResponse(
            422,
            payload,
            reason="PIN {} belongs to {}".format(sensitive_pin, sensitive_contact),
        )
    )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SmartRentHTTPError) as error:
            await client.async_create_guest_access_code(
                34,
                "permanent",
                "Private",
                "Person",
                email=sensitive_contact,
            )

    assert error.value.status == 422
    assert error.value.reason == "invalid_request"
    combined_output = str(error.value) + caplog.text
    assert sensitive_pin not in combined_output
    assert sensitive_contact not in combined_output
    assert "PIN" not in combined_output


@pytest.mark.asyncio
async def test_second_auth_failure_is_typed_http_error():
    client, _ = make_client(
        FakeResponse(401, {"errors": [{"code": "unauthorized"}]}, "Unauthorized"),
        FakeResponse(401, {"errors": [{"code": "unauthorized"}]}, "Unauthorized"),
    )

    async def refresh_token():
        client._token = "still-invalid"

    client._async_refresh_token = refresh_token

    with pytest.raises(SmartRentHTTPError) as error:
        await client.async_get_unit_access(34)

    assert error.value.status == 401
    assert error.value.reason == "Unauthorized"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"activation_type": "sometimes"}, "activation_type"),
        ({"first_name": " "}, "first_name"),
        ({"last_name": ""}, "last_name"),
        ({"email": None}, "at least one"),
        (
            {
                "activation_type": "temporary",
                "email": "guest@example.com",
            },
            "temporary_start_at",
        ),
        (
            {
                "activation_type": "temporary",
                "email": "guest@example.com",
                "temporary_start_at": "2026-08-16T10:00:00Z",
                "temporary_end_at": "2026-08-16T09:00:00Z",
            },
            "before",
        ),
        (
            {
                "activation_type": "temporary",
                "email": "guest@example.com",
                "temporary_start_at": "2026-08-16T10:00:00",
                "temporary_end_at": "2026-08-16T11:00:00",
            },
            "ISO timestamp",
        ),
        (
            {
                "activation_type": "recurring",
                "email": "guest@example.com",
                "recurring_start_time": "09:00",
                "recurring_end_time": "10:00",
            },
            "recurring_repeat_on",
        ),
        (
            {
                "activation_type": "recurring",
                "email": "guest@example.com",
                "recurring_start_time": "09:00",
                "recurring_end_time": "10:00",
                "recurring_repeat_on": ["Mon"],
            },
            "full English weekday",
        ),
    ],
)
async def test_create_validation_happens_before_request(kwargs, message):
    client, session = make_client()
    values = {
        "activation_type": "permanent",
        "first_name": "First",
        "last_name": "Last",
        "phone": None,
        "email": "guest@example.com",
    }
    values.update(kwargs)

    with pytest.raises(SmartRentValidationError, match=message):
        await client.async_create_guest_access_code(34, **values)

    assert session.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name, args",
    [
        ("async_get_unit_access", (0,)),
        (
            "async_create_guest_access_code",
            (-1, "permanent", "First", "Last"),
        ),
        ("async_update_guest_access_code", (True, 2, 3)),
        ("async_update_guest_access_code", (1, 0, 3)),
        ("async_delete_guest_access_code", (1, 2, -3)),
    ],
)
async def test_ids_must_be_positive_integers(method_name, args):
    client, session = make_client()
    method = getattr(client, method_name)

    with pytest.raises(SmartRentValidationError, match="positive integer"):
        await method(*args)

    assert session.requests == []


@pytest.mark.asyncio
async def test_update_validation_happens_before_request():
    client, session = make_client()

    with pytest.raises(SmartRentValidationError, match="updated together"):
        await client.async_update_guest_access_code(
            1, 2, 3, temporary_start_at="2026-08-16T08:00:00Z"
        )

    with pytest.raises(SmartRentValidationError, match="at least one update"):
        await client.async_update_guest_access_code(1, 2, 3)

    assert session.requests == []
