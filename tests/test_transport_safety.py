"""Offline regressions run unchanged against source and the extracted candidate."""
import threading
import time
from email.utils import formatdate

import httpx
import pytest

import flowspeech_v1
from flowspeech_v1 import ApiError, V1Client
from test_v1_contract import INPUT, JOB, REQUEST, URL, factory, job, response, wav_bytes


class InterruptedBody(httpx.SyncByteStream):
    def __init__(self, error_type=httpx.ReadError):
        self.error_type = error_type
        self.closed = False

    def __iter__(self):
        yield b"{"
        raise self.error_type("test-only synthetic transport detail")

    def close(self):
        self.closed = True


class CloseFailureBody(InterruptedBody):
    def __iter__(self):
        yield b"{"

    def close(self):
        self.closed = True
        raise httpx.ReadError("test-only synthetic cleanup detail")


class ReadAndCloseFailureBody(CloseFailureBody):
    __iter__ = InterruptedBody.__iter__


def interrupted_call(factory, stage, status, *, retry_after="60", error_type=httpx.ReadError,
                     body_type=InterruptedBody, **kwargs):
    stream = body_type(error_type)
    broken = httpx.Response(status, headers={"Retry-After": retry_after}, stream=stream)
    if stage == "download":
        client, calls, downloads, clock = factory(
            [response(job())], [broken, httpx.Response(200, content=wav_bytes())], **kwargs)
    else:
        replies = [broken, response(job())]
        if stage == "poll":
            replies.insert(0, response(job("queued")))
        client, calls, downloads, clock = factory(replies, **kwargs)
    return client, calls, downloads, clock, stream


@pytest.mark.parametrize("stage", ["create", "poll", "download"])
@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize("error_type", [httpx.ReadError, httpx.ReadTimeout])
def test_interrupted_permanent_response_is_not_retried(factory, stage, status, error_type):
    client, calls, downloads, clock, stream = interrupted_call(factory, stage, status, error_type=error_type)
    with pytest.raises(ApiError) as caught:
        client.generate(INPUT, request_id=REQUEST)
    error = caught.value
    assert error.status_code == status and not error.retryable
    assert error.request_id == REQUEST
    assert "test-only" not in str(error) and "synthetic" not in str(error)
    assert len(calls) == (2 if stage == "poll" else 1)
    assert len(downloads) == (1 if stage == "download" else 0)
    assert clock.waits == ([5] if stage == "poll" else [])
    if stage != "create":
        assert error.job_id == JOB
    if stage == "download":
        assert error.result_url == URL
    assert stream.closed


@pytest.mark.parametrize("stage", ["create", "poll", "download"])
@pytest.mark.parametrize("status", [200, 429, 503])
@pytest.mark.parametrize("error_type", [httpx.ReadError, httpx.RemoteProtocolError])
def test_interrupted_retry_preserves_cooldown_and_recording(factory, stage, status, error_type):
    client, calls, downloads, clock, stream = interrupted_call(factory, stage, status, error_type=error_type)
    completed, audio, request_id = client.generate(INPUT, request_id=REQUEST)
    assert completed["id"] == JOB and audio == wav_bytes() and request_id == REQUEST
    assert clock.waits == ([5, 60] if stage == "poll" else [60])
    assert len(calls) == {"create": 2, "poll": 3, "download": 1}[stage]
    assert len(downloads) == (2 if stage == "download" else 1)
    creates = [call for call in calls if call.method == "POST"]
    assert len({call.content for call in creates}) == 1
    assert {call.headers["Idempotency-Key"] for call in creates} == {REQUEST}
    assert all(not ({"authorization", "cookie", "x-api-key"} & set(call.headers)) for call in downloads)
    assert stream.closed


@pytest.mark.parametrize("stage", ["create", "poll", "download"])
def test_interrupted_retry_after_cannot_exceed_total_deadline(factory, stage):
    client, calls, downloads, clock, stream = interrupted_call(factory, stage, 429, timeout=10)
    with pytest.raises(ApiError) as caught:
        client.generate(INPUT, request_id=REQUEST)
    assert caught.value.code == "deadline_exceeded" and caught.value.request_id == REQUEST
    assert len(calls) == (2 if stage == "poll" else 1)
    assert len(downloads) == (1 if stage == "download" else 0)
    assert clock.waits == ([5] if stage == "poll" else [])
    assert stream.closed


@pytest.mark.parametrize("stage", ["create", "poll", "download"])
@pytest.mark.parametrize("header,delay", [("1", 5), (formatdate(1060, usegmt=True), 60)])
def test_interrupted_retry_after_date_and_poll_minimum(factory, monkeypatch, stage, header, delay):
    parser = flowspeech_v1.retry_after
    monkeypatch.setattr(flowspeech_v1, "retry_after", lambda value: parser(value, lambda: 1000))
    client, _, _, clock, _ = interrupted_call(factory, stage, 429, retry_after=header)
    client.generate(INPUT, request_id=REQUEST)
    assert clock.waits == ([5, delay] if stage == "poll" else [delay])


@pytest.mark.parametrize("download", [False, True])
def test_interrupted_retry_limit_and_last_status(factory, download):
    streams = [InterruptedBody() for _ in range(3)]
    broken = [httpx.Response(429, headers={"Retry-After": "60"}, stream=stream) for stream in streams]
    client, calls, downloads, clock = factory([response(job())] if download else broken,
                                             broken if download else None)
    with pytest.raises(ApiError) as caught:
        client.generate(INPUT, request_id=REQUEST)
    assert caught.value.status_code == 429 and caught.value.request_id == REQUEST
    assert clock.waits == [60, 60]
    assert len(downloads if download else calls) == 3
    assert all(stream.closed for stream in streams)
    if download:
        assert len(calls) == 1 and caught.value.job_id == JOB


def test_interrupted_redirect_target_retries_without_credentials_or_new_job(factory):
    broken = InterruptedBody()
    client, calls, downloads, clock = factory([response(job())], [
        httpx.Response(302, headers={"Location": "https://second.example.test/a.wav"}),
        httpx.Response(429, headers={"Retry-After": "60"}, stream=broken),
        httpx.Response(200, content=wav_bytes()),
    ])
    client.generate(INPUT, request_id=REQUEST)
    assert len(calls) == 1 and len(downloads) == 3 and clock.waits == [60]
    assert all(not ({"authorization", "cookie", "x-api-key"} & set(call.headers)) for call in downloads)
    assert broken.closed


@pytest.mark.parametrize("stage", ["create", "poll", "download"])
@pytest.mark.parametrize("status", [401, 403, 429, 503])
@pytest.mark.parametrize("body_type", [CloseFailureBody, ReadAndCloseFailureBody])
def test_close_failure_preserves_status_and_cooldown(factory, stage, status, body_type):
    client, calls, downloads, clock, stream = interrupted_call(factory, stage, status, body_type=body_type)
    if status in (401, 403):
        with pytest.raises(ApiError) as caught:
            client.generate(INPUT, request_id=REQUEST)
        assert caught.value.status_code == status and not caught.value.retryable
        assert caught.value.request_id == REQUEST
        assert "test-only" not in str(caught.value) and "synthetic" not in str(caught.value)
        assert len(calls) == (2 if stage == "poll" else 1)
        assert len(downloads) == int(stage == "download")
        assert clock.waits == ([5] if stage == "poll" else [])
    else:
        assert client.generate(INPUT, request_id=REQUEST)[0]["id"] == JOB
        assert clock.waits == ([5, 60] if stage == "poll" else [60])
    assert stream.closed


def assert_worker_capacity_released():
    acquired = 0
    try:
        while acquired <= flowspeech_v1._HTTP_WORKER_LIMIT and flowspeech_v1._HTTP_WORKERS.acquire(blocking=False):
            acquired += 1
        assert acquired == flowspeech_v1._HTTP_WORKER_LIMIT
    finally:
        for _ in range(acquired):
            flowspeech_v1._HTTP_WORKERS.release()


def test_timeout_workers_are_bounded_across_clients_and_recover_capacity():
    limit = flowspeech_v1._HTTP_WORKER_LIMIT
    release = threading.Event()
    calls, clients, transports, workers = [], [], [], []

    def blocked(request):
        calls.append(request)
        workers.append(threading.current_thread())
        assert release.wait(5), "Test must release every mock worker"
        return response(job())

    try:
        for _ in range(limit + 5):
            transport = httpx.Client(transport=httpx.MockTransport(blocked))
            transports.append(transport)
            client = V1Client(api_key="test-only", timeout=0.03, http_client=transport, download_client=transport)
            clients.append(client)
            started = time.monotonic()
            with pytest.raises(ApiError) as caught:
                client.generate(INPUT, request_id=REQUEST)
            assert time.monotonic() - started < 0.5
            assert caught.value.code == ("deadline_exceeded" if len(clients) <= limit else "transport_busy")
            assert caught.value.request_id == REQUEST
            client.close()
        assert len(calls) == len(workers) == limit
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
            assert not worker.is_alive()
        for client in clients:
            client.close()
        for transport in transports:
            transport.close()
    with httpx.Client(transport=httpx.MockTransport(lambda _: response({"voices": [{"name": "Kore"}]}))) as transport:
        with V1Client(api_key="test-only", http_client=transport, download_client=transport) as client:
            assert client.voices() == [{"name": "Kore"}]
    assert_worker_capacity_released()


@pytest.mark.parametrize("download", [False, True])
@pytest.mark.parametrize("owned", [False, True])
def test_timeout_defers_owned_close_and_prevents_reentry(monkeypatch, download, owned):
    release = threading.Event()
    workers, calls, closed = [], [], []

    class BlockedStream(httpx.SyncByteStream):
        def __iter__(self):
            assert release.wait(3)
            yield wav_bytes()

        def close(self):
            closed.append("response")

    class TrackedTransport(httpx.MockTransport):
        def close(self):
            closed.append(self)

    def blocked(request):
        calls.append(request)
        workers.append(threading.current_thread())
        if download:
            return httpx.Response(200, stream=BlockedStream())
        assert release.wait(3)
        return response(job())

    api_transport = TrackedTransport(lambda request: response(job()) if download else blocked(request))
    audio_transport = TrackedTransport(blocked)
    api, audio = httpx.Client(transport=api_transport), httpx.Client(transport=audio_transport)
    if owned:
        with monkeypatch.context() as patch:
            clients = iter([api, audio])
            patch.setattr(flowspeech_v1.httpx, "Client", lambda **_: next(clients))
            client = V1Client(api_key="test-only", timeout=0.03)
    else:
        client = V1Client(api_key="test-only", timeout=0.03, http_client=api, download_client=audio)
    try:
        with pytest.raises(ApiError) as caught:
            client.generate(INPUT, request_id=REQUEST)
        assert caught.value.code == "deadline_exceeded" and caught.value.request_id == REQUEST
        if download:
            assert caught.value.job_id == JOB and caught.value.result_url == URL
        with pytest.raises(ApiError) as caught:
            client.generate(INPUT, request_id=REQUEST)
        assert caught.value.code == "client_busy" and len(calls) == 1
        started = time.monotonic()
        client.close()
        client.close()
        assert time.monotonic() - started < 0.1 and not api.is_closed and not audio.is_closed
        with pytest.raises(ApiError) as caught:
            client.generate(INPUT, request_id=REQUEST)
        assert caught.value.code == "client_closed" and len(calls) == 1
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
            assert not worker.is_alive()
        client.close()
        try:
            assert api.is_closed is owned and audio.is_closed is owned
            assert closed.count(api_transport) == closed.count(audio_transport) == int(owned)
            if download:
                assert closed.count("response") == 1
        finally:
            api.close()
            audio.close()


def test_worker_start_failure_releases_capacity_and_client(monkeypatch, factory):
    client, calls, _, _ = factory([response(job())])
    with monkeypatch.context() as patch:
        def fail_start(_):
            raise RuntimeError("synthetic start failure")
        patch.setattr(threading.Thread, "start", fail_start)
        with pytest.raises(ApiError) as caught:
            client.generate(INPUT, request_id=REQUEST)
        assert caught.value.code == "transport_busy" and caught.value.request_id == REQUEST
    assert calls == []
    assert client.generate(INPUT, request_id=REQUEST)[0]["id"] == JOB
    assert_worker_capacity_released()


def test_abandoned_worker_never_starts_late_post(monkeypatch, factory):
    client, calls, _, _ = factory([response(job())], timeout=0.03)
    workers = []
    start_thread = threading.Thread.start
    try:
        with monkeypatch.context() as patch:
            patch.setattr(threading.Thread, "start", lambda worker: workers.append(worker))
            with pytest.raises(ApiError) as caught:
                client.generate(INPUT, request_id=REQUEST)
            assert caught.value.code == "deadline_exceeded" and caught.value.request_id == REQUEST
    finally:
        for worker in workers:
            start_thread(worker)
            worker.join(2)
            assert not worker.is_alive()
    # The fake job clock never advanced: the abandoned flag itself prevents I/O.
    assert calls == []
    assert client.generate(INPUT, request_id=REQUEST)[0]["id"] == JOB
    assert_worker_capacity_released()


@pytest.mark.parametrize("download", [False, True])
def test_deadline_during_request_construction_prevents_late_send(monkeypatch, download):
    release = threading.Event()
    workers, calls = [], []
    make_request = httpx.Request

    def delayed_request(method, url, **kwargs):
        request = make_request(method, url, **kwargs)
        if (url == URL) == download:
            workers.append(threading.current_thread())
            assert release.wait(3)
        return request

    def handle(request):
        calls.append(request)
        return response(job())

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        with V1Client(api_key="test-only", timeout=0.03, http_client=transport, download_client=transport) as client:
            try:
                monkeypatch.setattr(httpx, "Request", delayed_request)
                with pytest.raises(ApiError) as caught:
                    client.generate(INPUT, request_id=REQUEST)
                assert caught.value.code == "deadline_exceeded" and caught.value.request_id == REQUEST
                if download:
                    assert caught.value.job_id == JOB and caught.value.result_url == URL
            finally:
                release.set()
                for worker in workers:
                    worker.join(2)
                    assert not worker.is_alive()
            assert len(calls) == int(download)
