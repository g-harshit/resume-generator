"""Rewording the lines the person picks: one call for all of them, under the guard."""

import json

from app.ai_providers import stub
from app.services.reword import Reworded, RewordPlan
from app.services.tailor import Verdict, Verification
from tests.test_tailor import PROFILE, make, ready  # noqa: F401

KAFKA = "Moved settlement jobs from cron to Kafka consumers on AWS ECS."
REC = "Built a reconciliation service in Go matching 3M transactions a day."


def answer(texts: dict[str, str], flagged: set[str] = frozenset()):
    stub.answer(
        "reword_lines",
        lambda text: RewordPlan(lines=[Reworded(id=i, text=t) for i, t in texts.items()]),
    )
    stub.answer(
        "verify_tailoring",
        lambda text: Verification(
            verdicts=[
                Verdict(
                    id=i["id"],
                    reasoning="",
                    adds_information=i["id"] in flagged,
                    added="a claim" if i["id"] in flagged else "",
                )
                for i in json.loads(text)
            ]
        ),
    )


def reword(client, auth, resume_id, version, *ids, again=False):
    return client.post(
        f"/resumes/{resume_id}/reword",
        headers=auth,
        json={"version": version, "line_ids": list(ids), "again": again},
    )


def test_chosen_lines_are_reworded_in_one_call_and_marked(client, auth, ready):  # noqa: F811
    resume = make(client, auth, ready).json()
    new_kafka = "Moved settlement jobs from cron to Kafka consumers on AWS (ECS)."
    new_rec = "Built a Go reconciliation service matching 3M transactions a day."
    answer({"b_kafka": new_kafka, "b_rec": new_rec})
    r = reword(client, auth, resume["id"], 1, "b_kafka", "b_rec")
    assert r.status_code == 200, r.text
    body = r.json()
    lines = {b["id"]: b["text"] for b in body["resume"]["content"]["experience"][0]["bullets"]}
    assert lines["b_kafka"] == new_kafka and lines["b_rec"] == new_rec
    assert body["resume"]["provenance"]["b_kafka"] == {
        "original": KAFKA,
        "status": "reworded",
        "attempted": None,
        "reason": None,
    }
    assert body["refused"] == {}
    assert [c["task"] for c in stub.calls].count("reword_lines") == 1
    # Only the chosen lines were sent.
    sent = json.loads(next(c["text"] for c in stub.calls if c["task"] == "reword_lines"))
    assert [line["id"] for line in sent["lines"]] == ["b_kafka", "b_rec"]


def test_a_rewording_that_invents_keeps_the_line_and_says_why(client, auth, ready):  # noqa: F811
    resume = make(client, auth, ready).json()
    answer(
        {
            "b_kafka": "Moved 40 settlement jobs from cron to Kafka consumers on AWS ECS.",
            "b_rec": "Built a Go reconciliation service matching 3M transactions a day.",
        },
        flagged={"b_rec"},
    )
    body = reword(client, auth, resume["id"], 1, "b_kafka", "b_rec").json()
    lines = {b["id"]: b["text"] for b in body["resume"]["content"]["experience"][0]["bullets"]}
    assert lines == {**lines, "b_kafka": KAFKA, "b_rec": REC}
    assert "number" in body["refused"]["b_kafka"]
    assert "a claim" in body["refused"]["b_rec"]
    assert body["resume"]["version"] == 1  # nothing changed, nothing saved


def test_again_rewords_from_the_persons_line_avoiding_the_last(client, auth, ready):  # noqa: F811
    resume = make(client, auth, ready).json()
    first = "Moved settlement jobs from cron to Kafka consumers on AWS (ECS)."
    answer({"b_kafka": first})
    reword(client, auth, resume["id"], 1, "b_kafka")
    answer({"b_kafka": "Moved cron settlement jobs to Kafka consumers on AWS ECS."})
    r = reword(client, auth, resume["id"], 2, "b_kafka", again=True)
    sent = json.loads([c["text"] for c in stub.calls if c["task"] == "reword_lines"][-1])
    assert sent["lines"] == [
        {
            "id": "b_kafka",
            "where": "Role: Backend Engineer at Paylane",
            "text": KAFKA,
            "avoid": first,
        }
    ]
    assert r.json()["resume"]["provenance"]["b_kafka"]["original"] == KAFKA


def test_unknown_lines_are_not_found(client, auth, ready):  # noqa: F811
    resume = make(client, auth, ready).json()
    assert reword(client, auth, resume["id"], 1, "nope").status_code == 404


def test_a_rewording_that_drops_a_number_is_refused(client, auth, ready):  # noqa: F811
    resume = make(client, auth, ready).json()
    answer({"b_rec": "Built a Go reconciliation service for daily transactions."})
    body = reword(client, auth, resume["id"], 1, "b_rec").json()
    assert body["refused"]["b_rec"] == "it dropped 3m from your line"
