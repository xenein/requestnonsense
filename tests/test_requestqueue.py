import mock

from requestnonsense.requestnonsense import RequestQueue, RequestTuple


def test_append_simple():
    qu = RequestQueue()
    rq = RequestTuple(False, False, 1.0, "miau - meow", "Goethe")

    old_len = qu.len()
    qu.append(rq)
    new_len = qu.len()

    assert old_len + 1 == new_len
    assert rq in qu.data


@mock.patch("requestnonsense.requestnonsense.RequestQueue.safe_queue")
def test_process_upgrade(mocked_safe_queue):
    qu = RequestQueue()
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
