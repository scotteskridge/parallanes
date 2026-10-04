from kitlib.comments import strip_comments


def test_hash_comments_removed():
    assert strip_comments("x = 1  # print(x)\n# print(y)\n", ".py") == ["x = 1  ", ""]


def test_slash_comments_and_blocks_removed():
    text = "a(); // b()\n/* c()\n d() */ e();\nf(); /* g() */ h();\n"
    assert strip_comments(text, ".ts") == ["a(); ", "", " e();", "f();   h();"]


def test_html_comments_removed_in_markdown():
    assert strip_comments("keep <!-- drop --> keep\n", ".md") == ["keep   keep"]


def test_sql_dash_comments():
    assert strip_comments("select 1; -- drop table x\n", ".sql") == ["select 1; "]


def test_line_numbers_are_preserved():
    text = "a\n/*\nb\n*/\nc\n"
    assert len(strip_comments(text, ".js")) == len(text.splitlines())


def test_unknown_extension_is_left_alone():
    assert strip_comments("x # y\n", ".unknownext") == ["x # y"]


def test_marker_inside_string_can_only_hide_code_never_invent_it():
    # Decision 23: no string parsing. The URL's // ends checking for this line (a possible miss),
    # but nothing that wasn't in the code appears in the output (no false alarm).
    stripped = strip_comments('url = "http://x"; print(1)\n', ".js")
    assert stripped == ['url = "http:']


def test_removed_block_comment_cannot_join_tokens():
    # Decision 23: stripping must never create a match that isn't in the code.
    assert "foobar" not in strip_comments("foo/* c */bar\n", ".c")[0]


def test_form_feed_does_not_shift_line_numbers():
    from kitlib.comments import split_lines

    assert split_lines("a\x0cb\nc\r\nd\n") == ["a\x0cb", "c", "d"]
