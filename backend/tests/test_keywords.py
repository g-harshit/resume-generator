"""Keywords the person chose for a line: every one goes in, nothing second-guesses it."""

import json

import pytest

from app.ai_providers import stub
from app.ai_providers.stub import StubProvider
from app.services.keywords import KeywordError, KeywordLine, add_keywords

LINE = "Designed and built a scalable, robust end-to-end event-driven service in Go"
KEYWORDS = ["Microservices", "Queues", "High-throughput systems"]
GOOD = (
    "Designed and built a scalable, robust end-to-end event-driven Go microservice "
    "using queues, built for high throughput"
)


def answers(*texts):
    replies = iter(texts)
    stub.answer("keyword_rewrite", lambda text: KeywordLine(text=next(replies)))


def test_a_line_with_every_keyword_is_returned_in_one_call():
    answers(GOOD)
    assert add_keywords(LINE, KEYWORDS, "Engineer Acme", StubProvider()) == GOOD
    assert len(stub.calls) == 1
    sent = json.loads(stub.calls[0]["text"])
    assert sent["keywords"] == KEYWORDS and sent["avoid"] == []


def test_nothing_is_refused_for_what_it_adds():
    # The person asked for these keywords; no number/term/padding rule applies.
    bold = GOOD + " across 40 Kafka clusters, ensuring reliability"
    answers(bold)
    assert add_keywords(LINE, KEYWORDS, "", StubProvider()) == bold


def test_a_left_out_keyword_gets_one_more_try_naming_it():
    answers(LINE + " using queues", GOOD)
    assert add_keywords(LINE, KEYWORDS, "", StubProvider()) == GOOD
    second = json.loads(stub.calls[1]["text"])
    assert second["missing"] == ["Microservices", "High-throughput systems"]


def test_the_closest_try_is_kept_when_none_has_them_all():
    closer = LINE + " as a microservice using queues"
    answers(LINE + " using queues", closer)
    assert add_keywords(LINE, KEYWORDS, "", StubProvider()) == closer


def test_again_asks_for_different_wording():
    answers(GOOD)
    add_keywords(LINE, KEYWORDS, "", StubProvider(), avoid=["the old one"])
    assert json.loads(stub.calls[0]["text"])["avoid"] == ["the old one"]


def test_no_line_at_all_is_an_error():
    answers("", "")
    with pytest.raises(KeywordError):
        add_keywords(LINE, KEYWORDS, "", StubProvider())
