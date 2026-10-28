from textstats import tokenize, top_tokens, duplicate_groups, normalize


def test_tokenize():
    assert tokenize("GET /api/v2 200 OK") == ["get", "api", "v2", "200", "ok"]
    assert tokenize("") == []


def test_top_tokens_order_and_ties():
    lines = ["b a", "a c", "c a b", "d"]
    assert top_tokens(lines, 3) == [("a", 3), ("b", 2), ("c", 2)]
    assert top_tokens(lines, 10)[-1] == ("d", 1)


def test_normalize():
    assert normalize("user 42 logged in at 10:31") == "user # logged in at # #"


def test_duplicate_groups():
    lines = ["user 1 in", "x", "user 22 in", "y 3", "user 5 in", "y 4"]
    assert duplicate_groups(lines) == [[0, 2, 4], [3, 5]]
    assert duplicate_groups([]) == []
    assert duplicate_groups(["a"]) == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("tests ok")
