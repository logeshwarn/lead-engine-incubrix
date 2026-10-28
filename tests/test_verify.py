"""verify: every check passes only with evidence, and every rejection says why."""

import json
from datetime import timedelta

import pandas as pd
import pytest

from engine import verify
from engine.common import now_utc

NOW = now_utc()
SITE = "https://janedoeshow.com"


def item(days_ago, minutes=30, captions=False, title="Episode", desc="", n=0):
    return {
        "item_id": f"i{days_ago}-{n}",
        "title": title,
        "url": f"{SITE}/ep/{days_ago}-{n}",
        "published": NOW - timedelta(days=days_ago),
        "published_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "duration_seconds": minutes * 60,
        "has_captions": captions,
        "description": desc,
    }


def profile(**overrides):
    base = {
        "platform": "podcast",
        "platform_id": "itunes:1",
        "name": "Jane Doe Show",
        "profile_url": "https://podcasts.apple.com/podcast/id1",
        "segment": "Podcaster/Video Podcaster",
        "niche": "biz",
        "seed_id": "S1",
        "subscribers": None,
        "website": SITE,
        "feed_url": "https://feed.example/rss",
        "country": None,
        "location": None,
        "description": "Weekly interviews. Based in Austin, Texas.",
        "emails": json.dumps([{"value": "hello@janedoeshow.com", "source_url": f"{SITE}/contact"}]),
        "links": json.dumps([]),
        "pages": json.dumps([{"url": f"{SITE}/contact", "title": "Contact", "text": "Get in touch"}]),
        "enrich_status": "ok",
        "enriched_at": NOW.date().isoformat(),
        "last_content_at": None,
    }
    base.update(overrides)
    return base


def good_items():
    # Weekly 45-minute episodes, the newest with a sponsor read: active, commercial, no transcripts.
    items = [item(d, minutes=45, n=d) for d in (2, 9, 16, 23)]
    items[0]["description"] = "This episode is sponsored by Acme Tools. Use code JANE for 10% off."
    items[0]["title"] = "How we grew to 10k listeners"
    return items


@pytest.fixture
def cfg(config):
    return config


def run_one(cfg, p=None, items=None):
    return verify.verify_profile(p or profile(), good_items() if items is None else items, cfg)


# ---------- a fully qualified creator ----------


def test_qualified_creator_has_evidence_for_every_check(cfg):
    row = run_one(cfg)
    assert row["candidate_status"] == "Qualified", row["rejection_reason"]
    assert row["country_iso2"] == "US" and "Austin, Texas" in row["country_evidence"]
    assert row["monetization_signal"] == "Sponsorship" and "sponsored by Acme" in row["monetization_evidence"]
    assert row["monetization_evidence_url"] == f"{SITE}/ep/2-2"
    assert row["need_kind"] == "captions" and row["need_evidence_url"]
    contacts = json.loads(row["contacts"])
    assert contacts[0]["channel"] == "Email" and contacts[0]["evidence_url"] == f"{SITE}/contact"
    assert row["recent_content_title"] == "How we grew to 10k listeners"


# ---------- check 2: activity rule ----------


def test_active_by_eight_items_in_30_days(cfg):
    items = [item(d, minutes=5, n=d) for d in range(1, 9)]  # 8 short items
    passed, n30, n_long = verify.activity(items, cfg)
    assert passed and n30 == 8 and n_long == 0


def test_seven_short_items_is_not_active(cfg):
    items = [item(d, minutes=5, n=d) for d in range(1, 8)]
    assert verify.activity(items, cfg)[0] is False


def test_active_by_two_long_form_in_60_days(cfg):
    items = [item(10, minutes=20), item(50, minutes=60)]  # 20 minutes counts as long-form
    assert verify.activity(items, cfg) == (True, 1, 2)


def test_long_form_needs_20_minutes_and_60_days(cfg):
    assert verify.activity([item(10, minutes=19), item(20, minutes=19)], cfg)[0] is False
    assert verify.activity([item(10, minutes=40), item(61, minutes=40)], cfg)[0] is False


def test_inactive_creator_rejected_with_counts(cfg):
    row = run_one(cfg, items=[item(40, minutes=10)])
    assert row["candidate_status"] == "Rejected"
    assert "not active (0 items in 30 days, 0 long-form in 60 days)" in row["rejection_reason"]


# ---------- missing evidence: no evidence, no pass ----------


def test_no_commercial_evidence_rejected(cfg):
    items = good_items()
    items[0]["description"] = "A great chat."
    row = run_one(cfg, items=items)
    assert row["check_commercial"] is False and row["monetization_evidence"] is None
    assert "no public commercial evidence" in row["rejection_reason"]


def test_no_country_evidence_rejected(cfg):
    row = run_one(cfg, profile(description="Weekly interviews.", website="https://janedoeshow.com"))
    assert row["country_iso2"] is None and "country not evidenced" in row["rejection_reason"]


def test_no_contact_rejected(cfg):
    row = run_one(cfg, profile(emails="[]", pages="[]"))
    assert row["check_reachable"] is False and "no published business contact" in row["rejection_reason"]


def test_enrich_failure_is_a_rejection_reason(cfg):
    row = run_one(cfg, profile(enrich_status="failed: no feed URL"), items=[])
    assert row["rejection_reason"].startswith("enrich failed: no feed URL")


def test_stale_evidence_rejected(cfg):
    old = (NOW - timedelta(days=31)).date().isoformat()
    row = run_one(cfg, profile(enriched_at=old))
    assert "evidence older than 30 days" in row["rejection_reason"]


# ---------- check 1: country, language, organisations ----------


@pytest.mark.parametrize(
    "overrides,country,evidence",
    [
        ({"country": "GB"}, "GB", "Channel country: GB"),
        ({"location": "Toronto, Ontario", "description": ""}, "CA", "Feed location tag: Toronto, Ontario"),
        ({"description": "Studio: 1 Main St, Boise, ID 83702"}, "US", "ID 83702"),
        ({"description": "Call +44 20 7946 0958"}, "GB", "+44 20 7946 0958"),
        ({"description": "A Melbourne-based coach"}, "AU", "Melbourne-based"),
        ({"description": "We are all from the Philippines"}, "Other", "from the Philippines"),
        ({"description": "", "website": "https://janedoe.co.uk"}, "GB", ".uk country domain"),
    ],
)
def test_country_sources(cfg, overrides, country, evidence):
    c, q, url = verify.find_country(profile(**overrides), [], 160)
    assert c == country and evidence in q and url


def test_mention_of_a_place_is_not_location(cfg):
    p = profile(description="Lessons from London and a trip to Sydney.", website="https://janedoeshow.com")
    assert verify.find_country(p, [], 160) == (None, None, None)


def test_non_approved_country_rejected(cfg):
    row = run_one(cfg, profile(description="We are from India."))
    assert "country Other not approved" in row["rejection_reason"]


def test_non_english_content_rejected(cfg):
    items = good_items()
    for it in items:
        it["title"] = "Wie wir unseren Podcast aufgebaut haben"
        it["description"] += " In dieser Folge sprechen wir über Wachstum und Marketing für kleine Unternehmen."
    row = run_one(cfg, items=items)
    assert row["english_share"] < 0.6 and "content not mainly English" in row["rejection_reason"]


@pytest.mark.parametrize(
    "name,desc,excluded",
    [
        ("Acme Podcast Network", "", True),
        ("Joe Rogan Clips", "", True),
        ("Jane Doe Show", "We are a full-service digital agency.", True),
        ("Jane Doe Official", "", False),  # common for solo creators
        ("Jane Doe Productions", "", False),
        ("Jane Doe Show", "I help agencies grow.", False),  # mentions agencies, is not one
        ("Smart Agency Masterclass with Jason", "", False),  # agency is the topic
        ("Your First Year In Network Marketing", "", False),
        ("Jane Doe Show", "Jane is founder of Hive, a marketing agency.", False),  # host runs an agency
    ],
)
def test_organisations_excluded(name, desc, excluded):
    ok, why = verify.check_not_organisation({"name": name, "description": desc})
    assert ok is not excluded
    assert (why is not None) is excluded


# ---------- check 3: commercial ----------


def test_commercial_from_link_alone(cfg):
    items = good_items()
    items[0]["description"] = "A great chat."
    p = profile(links=json.dumps([{"url": "https://www.patreon.com/janedoe", "source_url": SITE}]))
    kind, q, url = verify.find_commercial(p, items, 160)
    assert kind == "Membership" and "patreon.com/janedoe" in q and url == SITE


# ---------- check 4: needs IncuBrix ----------


def test_own_words_beat_observed_gaps(cfg):
    items = good_items()
    items[1]["description"] = "Sorry for the delay, we are hiring a video editor!"
    kind, summary, q, url = verify.find_need(profile(), items, cfg)
    assert kind == "own words" and "hiring a video editor" in q and url == items[1]["url"]


def test_no_captions_claim_needs_known_status(cfg):
    items = good_items()
    items[0]["has_captions"] = None  # unknown for one item: no claim
    kind = verify.find_need(profile(pages="[]"), items, cfg)[0]
    assert kind != "captions"


def test_captions_present_means_no_caption_need(cfg):
    items = good_items()
    items[2]["has_captions"] = True
    assert verify.find_need(profile(pages="[]"), items, cfg)[0] != "captions"


def test_podcast_repurposing_claim_needs_website_read(cfg):
    items = good_items()
    items[0]["has_captions"] = True  # rule out the caption signal
    p_read = profile()
    p_unread = profile(pages="[]")
    assert verify.find_need(p_read, items, cfg)[0] == "repurposing"
    assert verify.find_need(p_unread, items, cfg)[0] != "repurposing"


def test_youtube_long_videos_without_shorts(cfg):
    items = good_items()
    items[0]["has_captions"] = True
    kind, summary, _, _ = verify.find_need(profile(platform="youtube"), items, cfg)
    assert kind == "repurposing" and "no Shorts" in summary


# ---------- check 5: reachable ----------


@pytest.mark.parametrize(
    "email,source,text,accepted",
    [
        ("hello@janedoeshow.com", "https://other.example/page", "", True),  # own domain
        ("jane@gmail.com", "https://other.example/page", "Business inquiries: jane@gmail.com", True),  # labelled
        ("jane@gmail.com", "https://feed.example/rss", "", True),  # feed owner
        ("jane@gmail.com", f"{SITE}/contact-us", "", True),  # on their contact page
        ("jane@gmail.com", "https://other.example/page", "Photo by jane@gmail.com", False),  # stray
        ("shows@anchor.fm", "https://feed.example/rss", "", False),  # hosting platform address
        ("noreply@janedoeshow.com", SITE, "", False),
    ],
)
def test_email_acceptance(cfg, email, source, text, accepted):
    p = profile(
        emails=json.dumps([{"value": email, "source_url": source}]),
        pages=json.dumps([{"url": source, "title": "", "text": text}]),
    )
    contacts = verify.find_contacts(p, good_items(), cfg)
    assert any(c["value"] == email for c in contacts) is accepted


def test_social_link_alone_is_not_reachable(cfg):
    p = profile(
        emails="[]",
        pages=json.dumps([{"url": SITE, "title": "", "text": "Welcome"}]),
        links=json.dumps([{"url": "https://instagram.com/janedoe", "source_url": SITE}]),
    )
    row = run_one(cfg, p)
    assert json.loads(row["contacts"])[0]["channel"] == "Instagram"
    assert row["check_reachable"] is False


def test_guest_pitch_page_is_a_channel(cfg):
    pages = [{"url": f"{SITE}/guests", "title": "", "text": "Want to be a guest? Fill in the form."}]
    contacts = verify.find_contacts(profile(emails="[]", pages=json.dumps(pages)), good_items(), cfg)
    assert [c["channel"] for c in contacts] == ["Podcast guest pitch"]


# ---------- stage ----------


def test_run_writes_table_with_reasons(conn, cfg):
    rows = [profile(), profile(platform_id="itunes:2", name="Acme Podcast Network")]
    pd.DataFrame(rows).to_sql("profiles", conn, index=False)
    items = [
        {**it, "platform": "podcast", "platform_id": pid} for pid in ("itunes:1", "itunes:2") for it in good_items()
    ]
    pd.DataFrame(items).drop(columns=["published"]).to_sql("content_items", conn, index=False)
    verify.run(conn, cfg)
    v = pd.read_sql("SELECT * FROM verified", conn).set_index("platform_id")
    assert v.loc["itunes:1", "candidate_status"] == "Qualified"
    assert v.loc["itunes:2", "candidate_status"] == "Rejected"
    assert "not a creator: 'Podcast Network' in name" in v.loc["itunes:2", "rejection_reason"]
    assert list(pd.read_sql("SELECT * FROM verified", conn).columns) == verify.VERIFIED_COLUMNS


def test_episode_without_link_cites_show_page(cfg):
    items = good_items()
    items[0]["url"] = None
    row = run_one(cfg, items=items)
    assert row["recent_content_url"] == profile()["profile_url"] and row["check_personalisable"] is True


@pytest.mark.parametrize(
    "text,kind",
    [
        ("One-On-One Marketing Mentoring Available", "Service"),
        ("Become a sponsor of the show", "Sponsorship"),
        ("Support the podcast on our page", "Membership"),
        ("Try our fitness programs - free trial", "Product"),
        ("Join our free masterclass on Friday", "Course"),
    ],
)
def test_more_commercial_phrases(cfg, text, kind):
    p = profile(description=text, pages="[]")
    items = [item(3)]
    assert verify.find_commercial(p, items, 160)[0] == kind


@pytest.mark.parametrize("title", ["PROTEIN MASTERCLASS: how much do you need", "How to Build a Workout Program"])
def test_episode_topics_are_not_offers(cfg, title):
    p = profile(description="", pages="[]")
    assert verify.find_commercial(p, [item(3, title=title)], 160)[0] is None


# ---------- evidence must be about the creator, not a guest or sponsor ----------


def test_guest_location_in_show_notes_is_not_creator_country(cfg):
    p = profile(description="Weekly interviews.", website="https://janedoeshow.com")
    items = [item(3, desc="Our guest is CEO of Howdy, an Austin-based company.")]
    assert verify.find_country(p, items, 160) == (None, None, None)


def test_rightmost_place_wins():
    assert verify.place_country("Birmingham, Alabama") == "US"
    assert verify.place_country("London, Ontario") == "CA"
    assert verify.place_country("Belfast, Northern Ireland") == "GB"


def test_street_address_only_on_contact_or_about_page(cfg):
    venue = "Workshop venue: 330 Dupont Circle, Raleigh, NC 27603"
    home = profile(description="", website="https://janedoeshow.com",
                   pages=json.dumps([{"url": SITE, "title": "", "text": venue}]))  # fmt: skip
    contact = profile(description="", website="https://janedoeshow.com",
                      pages=json.dumps([{"url": f"{SITE}/contact", "title": "", "text": venue}]))  # fmt: skip
    assert verify.find_country(home, [], 160)[0] is None
    assert verify.find_country(contact, [], 160)[0] == "US"


def test_email_only_in_show_notes_is_not_accepted(cfg):
    items = good_items()
    items[0]["description"] += " Reach our guest: contact justin@guestco.com"
    p = profile(emails=json.dumps([{"value": "justin@guestco.com", "source_url": items[0]["url"]}]))
    assert verify.find_contacts(p, items, cfg) == [
        {"channel": "Contact form", "value": f"{SITE}/contact", "evidence_url": f"{SITE}/contact",
         "note": "contact page on creator's website"}
    ]  # fmt: skip


@pytest.mark.parametrize(
    "url,channel",
    [
        ("https://www.instagram.com/janedoe/", "Instagram"),
        ("https://x.com/janedoe", "X"),
        ("https://twitter.com/intent/tweet?text=hi", None),
        ("https://www.linkedin.com/in/jane-doe/", "LinkedIn"),
        ("https://www.linkedin.com/pulse/some-article", None),
        ("https://www.instagram.com/p/Cx123/", None),
        ("https://www.tiktok.com/@janedoe", "TikTok"),
    ],
)
def test_only_profile_links_are_social_contacts(cfg, url, channel):
    p = profile(emails="[]", pages=json.dumps([{"url": SITE, "title": "", "text": "Hi"}]),
                links=json.dumps([{"url": url, "source_url": SITE}]))  # fmt: skip
    found = [c["channel"] for c in verify.find_contacts(p, good_items(), cfg) if c["channel"] != "Contact form"]
    assert found == ([channel] if channel else [])


def test_testimonial_is_not_a_guest_pitch(cfg):
    pages = [{"url": f"{SITE}/podcast", "title": "", "text": "It was a delight to be a guest on the show."}]
    contacts = verify.find_contacts(profile(emails="[]", pages=json.dumps(pages)), good_items(), cfg)
    assert contacts == []
