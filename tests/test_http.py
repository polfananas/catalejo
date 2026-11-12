from pathlib import Path

import httpx
import pytest

from catalejo._http import USER_AGENT, CNMVRequestError, HttpClient

URL = "https://www.cnmv.es/portal/test"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(tmp_path: Path, handler, **kwargs) -> tuple[HttpClient, FakeClock]:
    clock = FakeClock()
    client = HttpClient(
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock,
        **kwargs,
    )
    return client, clock


def test_sends_identifiable_user_agent(tmp_path: Path) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers["User-Agent"]
        return httpx.Response(200, text="ok")

    client, _ = make_client(tmp_path, handler)
    client.get(URL)
    assert seen["ua"] == USER_AGENT
    assert "github.com/polfananas/catalejo" in USER_AGENT


def test_second_call_comes_from_cache(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="hola", headers={"Content-Type": "text/html"})

    client, _ = make_client(tmp_path, handler)
    first = client.get(URL, {"dias": 3})
    second = client.get(URL, {"dias": 3})

    assert calls == 1
    assert not first.from_cache
    assert second.from_cache
    assert second.text == "hola"
    assert second.content_type == "text/html"


def test_different_params_are_cached_separately(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=request.url.params["page"])

    client, _ = make_client(tmp_path, handler)
    assert client.get(URL, {"page": 1}).text == "1"
    assert client.get(URL, {"page": 2}).text == "2"


def test_requests_are_throttled(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="x")

    client, clock = make_client(tmp_path, handler, min_interval=1.0)
    client.get(URL, use_cache=False)
    client.get(URL, use_cache=False)
    assert clock.sleeps == [1.0]


def test_retries_on_503_then_succeeds(tmp_path: Path) -> None:
    answers = iter([503, 503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(answers), text="fine")

    client, _ = make_client(tmp_path, handler)
    assert client.get(URL).text == "fine"


def test_gives_up_after_max_retries(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client, _ = make_client(tmp_path, handler, max_retries=2)
    with pytest.raises(CNMVRequestError, match="3 attempts"):
        client.get(URL)


def test_404_is_not_retried(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    client, _ = make_client(tmp_path, handler)
    with pytest.raises(CNMVRequestError, match="404"):
        client.get(URL)
    assert calls == 1


@pytest.mark.parametrize(
    "url",
    ["https://example.com/", "https://cnmv.es.evil.com/", "https://notcnmv.es/"],
)
def test_refuses_hosts_other_than_cnmv(tmp_path: Path, url: str) -> None:
    client, _ = make_client(tmp_path, lambda r: httpx.Response(200))
    with pytest.raises(ValueError):
        client.get(url)
