"""Keywords the person chose for a line: the line may name them, and nothing else new."""

import json

import pytest

from app.ai_providers import stub
from app.ai_providers.stub import StubProvider
from app.services.keywords import KeywordError, KeywordLine, KeywordVerdict, add_keywords, check

LINE = "Designed and built a scalable, robust end-to-end event-driven service in Go"
KEYWORDS = ["Microservices", "Queues", "High-throughput systems"]
GOOD = (
    "Designed and built a scalable, robust end-to-end event-driven Go microservice "
    "using queues, built for high throughput"
)
TERMS = [*KEYWORDS, "Go", "Kafka", "Kubernetes"]


def answers(*texts, adds=False):
    replies = iter(texts)
    stub.answer("keyword_rewrite", lambda text: KeywordLine(text=next(replies)))
    stub.answer(
        "verify_keyword_rewrite",
        lambda text: KeywordVerdict(
            reasoning="", adds_anything_else=adds, added="a claim" if adds else ""
        ),
    )


@pytest.mark.parametrize(
    ("new", "reason"),
    [
        (GOOD, None),
        (LINE + " using queues", "left out Microservices, High-throughput systems"),
        (GOOD + " at 50k events/s", "added a number (50k)"),
        (GOOD + " on Kafka", "also mentioned Kafka"),
        (GOOD + ", ensuring uptime", "added “ensuring”"),
    ],
)
def test_the_line_names_every_chosen_keyword_and_nothing_else(new, reason):
    assert check(new, LINE, KEYWORDS, TERMS) == reason


def test_a_good_rewrite_is_returned():
    answers(GOOD)
    assert add_keywords(LINE, KEYWORDS, "Engineer Acme", TERMS, StubProvider()) == GOOD
    sent = json.loads(stub.calls[0]["text"])
    assert sent["keywords"] == KEYWORDS and sent["avoid"] == []


def test_a_refused_try_gets_one_more_and_is_asked_to_avoid():
    answers(GOOD + " at 50k events/s", GOOD)
    assert add_keywords(LINE, KEYWORDS, "", TERMS, StubProvider()) == GOOD
    second = json.loads(stub.calls[1]["text"])
    assert second["avoid"] == [GOOD + " at 50k events/s"]


def test_two_failures_raise_and_the_verifier_can_refuse():
    answers(GOOD, GOOD, adds=True)
    with pytest.raises(KeywordError, match="a claim"):
        add_keywords(LINE, KEYWORDS, "", TERMS, StubProvider())


def test_again_asks_for_different_wording():
    answers(GOOD)
    add_keywords(LINE, KEYWORDS, "", TERMS, StubProvider(), avoid=["the old one"])
    assert json.loads(stub.calls[0]["text"])["avoid"] == ["the old one"]
