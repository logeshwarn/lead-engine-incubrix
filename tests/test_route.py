"""route: a best and a backup channel per lead, only from what the creator published."""

import json

import pandas as pd
import pytest

from engine import route
from engine.score import SCORED_COLUMNS

SITE = "https://www.janedoe.com"


def c(channel, value):
    return {"channel": channel, "value": value, "evidence_url": f"{SITE}/contact", "note": ""}


def choose(*contacts, name="The Jane Doe Show", website=SITE):
    best, backup = route.choose(list(contacts), name, website)
    return (best and best["value"], backup and backup["value"])


def test_email_is_best_contact_form_is_backup():
    assert choose(c("Instagram", "https://instagram.com/janedoe"), c("Contact form", f"{SITE}/contact"),
                  c("Email", "jane@janedoe.com")) == ("jane@janedoe.com", f"{SITE}/contact")  # fmt: skip


def test_own_domain_email_beats_a_networks_address():
    best, _ = choose(c("Email", "producer@talkradio.com"), c("Email", "jane@janedoe.com"))
    assert best == "jane@janedoe.com"


def test_role_mailbox_goes_last():
    best, backup = choose(c("Email", "sales@janedoe.com"), c("Email", "jane@janedoe.com"))
    assert (best, backup) == ("jane@janedoe.com", "sales@janedoe.com")


def test_placeholder_email_is_never_used():
    assert choose(c("Email", "info@mysite.com"), c("Contact form", f"{SITE}/contact")) == (f"{SITE}/contact", None)


def test_without_email_contact_form_then_guest_pitch():
    assert choose(c("Podcast guest pitch", f"{SITE}/guest"), c("Contact form", f"{SITE}/contact")) == (
        f"{SITE}/contact",
        f"{SITE}/guest",
    )


def test_social_backup_must_be_the_creators_own():
    contacts = [c("Email", "storiedsf@gmail.com"), c("Instagram", "https://www.instagram.com/thebiscuitdan/"),
                c("Instagram", "https://www.instagram.com/storiedsf/")]  # fmt: skip
    assert choose(*contacts, name="Storied: San Francisco", website="http://www.storiedsf.com/") == (
        "storiedsf@gmail.com",
        "https://www.instagram.com/storiedsf/",
    )


def test_linkedin_preferred_among_own_socials():
    _, backup = choose(c("Email", "jane@janedoe.com"), c("Instagram", "https://instagram.com/janedoe"),
                       c("LinkedIn", "https://www.linkedin.com/in/jane-doe/"))  # fmt: skip
    assert backup == "https://www.linkedin.com/in/jane-doe/"


def test_second_email_is_the_last_resort_backup():
    assert choose(c("Email", "daniel@janedoe.com"), c("Email", "hello@janedoe.com")) == (
        "daniel@janedoe.com",
        "hello@janedoe.com",
    )


def test_one_contact_has_no_backup():
    assert choose(c("Email", "crenshawsir@gmail.com")) == ("crenshawsir@gmail.com", None)
    assert choose(c("Instagram", "https://instagram.com/janedoe")) == (None, None)  # a social alone is not checkable


def scored_row(pid, contacts, status="Qualified"):
    r = dict.fromkeys(SCORED_COLUMNS)
    r.update(platform_id=pid, creator_name="Jane Doe", website=SITE, contacts=json.dumps(contacts),
             candidate_status=status)  # fmt: skip
    return r


def test_run_writes_both_channels_with_evidence(conn, config):
    rows = [scored_row("a", [c("Email", "jane@janedoe.com"), c("Contact form", f"{SITE}/contact")]),
            scored_row("b", [], status="Rejected")]  # fmt: skip
    pd.DataFrame(rows, columns=SCORED_COLUMNS).to_sql("scored", conn, index=False)
    route.run(conn, config)
    t = pd.read_sql("SELECT * FROM routed", conn).set_index("platform_id")
    assert t.loc["a", route.ROUTE_COLUMNS].tolist() == [
        "Email", "jane@janedoe.com", f"{SITE}/contact", "Contact form", f"{SITE}/contact", f"{SITE}/contact",
    ]  # fmt: skip
    assert pd.isna(t.loc["b", "best_channel"])  # rejected rows get no channel


def test_qualified_lead_without_backup_is_a_bug(config):
    df = pd.DataFrame([scored_row("a", [c("Email", "jane@janedoe.com")])], columns=SCORED_COLUMNS)
    with pytest.raises(ValueError, match="without a best and backup channel"):
        route.route(df)


def test_single_social_on_own_pages_is_the_creators():
    # Chillscape's site links one Instagram account, the host's own handle.
    contacts = [c("Email", "chillscapevgm@gmail.com"), c("Instagram", "https://www.instagram.com/scab_zilla?igsh=MX")]
    assert choose(*contacts, name="Chillscape: A Chill VGM Podcast", website="https://chillscape.xyz")[1] == (
        "https://www.instagram.com/scab_zilla?igsh=MX"
    )
