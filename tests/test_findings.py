from kitlib.findings import Finding, format_findings


def test_format_lists_each_finding_with_location_and_rule():
    findings = [
        Finding(check="rules", path="src/b.py", line=3, message="No print.", rule="no-print"),
        Finding(check="rules", path="src/a.py", line=10, message="No eval.", rule="no-eval"),
    ]
    text = format_findings(findings)
    assert text.splitlines() == [
        "src/a.py:10: [rules/no-eval] No eval.",
        "src/b.py:3: [rules/no-print] No print.",
    ]


def test_format_of_nothing_is_empty():
    assert format_findings([]) == ""
