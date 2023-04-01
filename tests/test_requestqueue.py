import mock

from requestnonsense.requestnonsense import RequestQueue, RequestTuple


def test_append_simple():
    qu = RequestQueue(path="./testqueue.bin", hackmd_token="abc")
    rq = RequestTuple(False, False, 1.0, "miau - meow", "Goethe")

    old_len = qu.len()
    qu.append(rq)
    new_len = qu.len()

    assert old_len + 1 == new_len
    assert rq in qu.data


@mock.patch("requestnonsense.requestnonsense.RequestQueue.safe_queue")
def test_process_upgrade(mocked_safe_queue):
    qu = RequestQueue(path="./testqueue.bin", hackmd_token="abc")
    requests = [
        RequestTuple(True, True, 1.0, "1", "A"),
        RequestTuple(True, True, 1.1, "2", "B"),
        RequestTuple(True, True, 1.2, "3", "C"),
        RequestTuple(True, True, 1.3, "4", "D"),
    ]
    for req in requests:
        qu.append(req)

    message = qu.process_upgrade("C", "mod")
    assert qu.len() == 4
    assert "C" in message
    assert "mod" in message
    for req in qu.data:
        if req.requestee != "C":
            assert req in requests
        else:
            assert req.waiting
            assert not req.non_prio
            assert req.song == "3"

    message = qu.process_upgrade("A", "mod")
    assert qu.len() == 4
    for req in qu.data:
        if req.requestee not in ["C", "A"]:
            assert req in requests
        else:
            assert req.waiting
            assert not req.non_prio
            assert req.song in ["1", "3"]


@mock.patch("requestnonsense.requestnonsense.RequestQueue.safe_queue")
def test_consume_all_next(mocked_safe_queue):
    qu = RequestQueue(path="./testqueue.bin", hackmd_token="abc")
    requests = [
        RequestTuple(True, True, 1.0, "1", "A"),
        RequestTuple(True, True, 1.1, "2", "B"),
        RequestTuple(True, True, 1.2, "3", "C"),
        RequestTuple(True, True, 1.3, "4", "D"),
    ]
    for req in requests:
        qu.append(req)
    while qu.len() != 0:
        next_song = qu.get_first()
        for request in qu.data:
            if request.waiting:
                next_song = request
                break
        message = qu.advance_queue(next_song)
        if qu.len() != 0:
            assert next_song.requestee in message
            assert next_song.song in message
            assert not qu.get_first().waiting
        else:
            assert "leer" in message


@mock.patch("requestnonsense.requestnonsense.RequestQueue.safe_queue")
def test_overwrite_request(mocked_safe_queue):
    qu = RequestQueue(path="./testqueue.bin", hackmd_token="abc")
    message_old = qu.process_request("1", "A")
    request_old = qu.get_first()

    message_new = qu.process_request("2", "A")
    request_new = qu.get_first()

    assert request_old.timestamp == request_new.timestamp
    assert request_old.non_prio == request_new.non_prio
    assert request_old.requestee == request_new.requestee
    assert qu.get_first().song == "2"

    assert "aktualisiert" in message_new
    assert "2" in message_new

    assert "eingetragen" in message_old
    assert "1" in message_old
