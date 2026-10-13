"""Cliente de Genesys Cloud (FE011, T2; criterios 3, 4 y 6): región, token, reintentos, errores y redacción."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from ingestion.genesys.client import (GenesysAuthError, GenesysClient, GenesysError, GenesysForbidden,
                                      GenesysNotFound)
from ingestion.genesys.fake import FakeGenesys
from ingestion.genesys.regions import GenesysConfigError, api_host

CLIENT_ID = "cliente-de-prueba"
SECRET = "secreto-de-prueba-123"
ORG = "/api/v2/organizations/me"


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **delta) -> None:
        self.value += timedelta(**delta)


@pytest.fixture
def fake():
    return FakeGenesys(client_id=CLIENT_ID, client_secret=SECRET, token_ttl_s=3600)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def client(fake, clock, sleeps):
    return GenesysClient(CLIENT_ID, SECRET, "eu-west-1", transport=fake.transport, clock=clock, sleep=sleeps.append)


def _token_requests(fake) -> int:
    return sum(1 for method, path in fake.calls if path == "/oauth/token")


def _outputs(exc: Exception) -> str:
    return f"{exc}\n{exc!r}\n{exc.args}"


# Región ----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("region, host", [("eu-west-1", "mypurecloud.ie"), ("eu-central-1", "mypurecloud.de"),
                                          ("us-east-1", "mypurecloud.com"), ("mypurecloud.ie", "mypurecloud.ie")])
def test_the_region_resolves_to_its_api_host(region, host):
    assert api_host(region) == host


def test_an_unknown_region_is_a_configuration_error():
    with pytest.raises(GenesysConfigError, match="marte-1"):
        api_host("marte-1")


def test_the_client_talks_to_the_hosts_of_its_region(client, fake):
    client.get(ORG)
    assert {request.url.host for request in fake.requests} == {"login.mypurecloud.ie", "api.mypurecloud.ie"}


# Token -----------------------------------------------------------------------------------------------------------------

def test_the_token_is_reused_until_shortly_before_it_expires(client, fake, clock):
    client.get(ORG)
    clock.advance(seconds=3600 - 301)
    client.get(ORG)
    assert _token_requests(fake) == 1
    clock.advance(seconds=2)
    client.get(ORG)
    assert _token_requests(fake) == 2


def test_api_calls_carry_the_bearer_token(client, fake):
    client.get(ORG)
    api_request = next(r for r in fake.requests if r.url.host.startswith("api."))
    assert api_request.headers["authorization"] == f"Bearer {fake.issued_tokens[-1]}"


def test_wrong_credentials_fail_at_once_with_a_clear_message(fake, clock, sleeps):
    client = GenesysClient(CLIENT_ID, "otro-secreto", "eu-west-1", transport=fake.transport, clock=clock,
                           sleep=sleeps.append)
    with pytest.raises(GenesysAuthError, match="Invalid Genesys credentials") as caught:
        client.get(ORG)
    assert _token_requests(fake) == 1 and sleeps == []
    assert "otro-secreto" not in _outputs(caught.value)


def test_a_rejected_token_is_renewed_once(client, fake):
    fake.fail("GET", ORG, 401)
    assert client.get(ORG)["name"] == "Laboratorio"
    assert _token_requests(fake) == 2


def test_a_token_rejected_twice_is_an_authentication_error(client, fake):
    fake.fail("GET", ORG, 401, 401)
    with pytest.raises(GenesysAuthError):
        client.get(ORG)
    assert _token_requests(fake) == 2


# Reintentos ------------------------------------------------------------------------------------------------------------

def test_a_429_waits_what_retry_after_says(client, fake, sleeps):
    fake.fail("GET", ORG, (429, {"Retry-After": "7"}))
    assert client.get(ORG)["name"] == "Laboratorio"
    assert sleeps == [7.0]


def test_server_errors_are_retried_three_times_with_growing_waits(client, fake, sleeps):
    fake.fail("GET", ORG, 503, 502, 500)
    assert client.get(ORG)["name"] == "Laboratorio"
    assert sleeps == [1.0, 2.0, 4.0]


def test_a_persistent_server_error_gives_up_after_three_retries(client, fake, sleeps):
    fake.fail("GET", ORG, 503, 503, 503, 503)
    with pytest.raises(GenesysError) as caught:
        client.get(ORG)
    assert caught.value.status == 503
    assert len([c for c in fake.calls if c == ("GET", ORG)]) == 4
    assert len(sleeps) == 3


def test_network_errors_are_retried(client, fake, sleeps):
    fake.fail("GET", ORG, httpx.ConnectError("sin red"), httpx.ReadTimeout("lento"))
    assert client.get(ORG)["name"] == "Laboratorio"
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize("status, error", [(403, GenesysForbidden), (404, GenesysNotFound), (400, GenesysError)])
def test_client_errors_are_not_retried(client, fake, sleeps, status, error):
    fake.fail("GET", ORG, status)
    with pytest.raises(error) as caught:
        client.get(ORG)
    assert caught.value.status == status and sleeps == []
    assert len([c for c in fake.calls if c == ("GET", ORG)]) == 1


def test_a_403_names_the_route_and_the_missing_permission(client, fake):
    fake.fail("GET", ORG, (403, {}, {"message": "Missing permission: speechandtextanalytics:data:view"}))
    with pytest.raises(GenesysForbidden) as caught:
        client.get(ORG)
    assert ORG in str(caught.value)
    assert "speechandtextanalytics:data:view" in str(caught.value)


# URL firmadas y redacción ----------------------------------------------------------------------------------------------

def test_signed_urls_are_fetched_without_the_bearer_token(client, fake):
    url = fake.signed_url("documento")
    fake.documents["documento"] = {"transcripts": []}
    assert client.get_signed(url) == {"transcripts": []}
    signed = next(r for r in fake.requests if r.url.host == fake.bucket_host)
    assert "authorization" not in signed.headers


@pytest.mark.parametrize("case", ["token", "api-403", "api-500", "red", "firmada-404", "firmada-500"])
def test_no_error_reveals_the_secret_the_token_or_a_signed_url(client, fake, case):
    url = fake.signed_url("doc")
    if case == "token":
        fake.fail("POST", "/oauth/token", (401, {}, {"error": "invalid_client", "echo": SECRET}))
    else:
        client.get(ORG)  # obtiene un token, que no debe aparecer en el error
        if case == "api-403":
            fake.fail("GET", ORG, (403, {}, {"message": f"denegado para {fake.issued_tokens[-1]}"}))
        elif case == "api-500":
            fake.fail("GET", ORG, *[(500, {}, {"message": f"fallo {SECRET}"})] * 4)
        elif case == "red":
            fake.fail("GET", ORG, *[httpx.ConnectError(f"sin red hacia {url}")] * 4)
        elif case == "firmada-404":
            fake.fail("GET", url, 404)
        else:
            fake.fail("GET", url, *[500] * 4)
    with pytest.raises(GenesysError) as caught:
        client.get_signed(url) if case.startswith("firmada") else client.get(ORG)
    text = _outputs(caught.value)
    for secret in [SECRET, url, url.split("?")[1], *fake.issued_tokens]:
        assert secret not in text, f"{case}: el error contiene {secret!r}"


def test_the_fake_rejects_api_calls_with_an_unknown_token(fake):
    http = httpx.Client(transport=fake.transport)
    assert http.get(f"https://api.mypurecloud.ie{ORG}", headers={"Authorization": "Bearer inventado"}).status_code == 401
    assert http.get(f"https://api.mypurecloud.ie{ORG}").status_code == 401
