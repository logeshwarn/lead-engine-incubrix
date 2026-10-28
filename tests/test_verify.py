"""verify: every check passes only with evidence, and every rejection says why."""

import json
from datetime import timedelta

import pandas as pd
import pytest
from conftest import FakeResponse, gemini_reply

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


CREATOR = {
    "kind": "creator",
    "reason": "host Jane",
    "quote": "Weekly interviews. Based in Austin",
    "source": "DESCRIPTION",
    "country_quote_about": "host",
}


@pytest.fixture(autouse=True)
def llm_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")


def load(conn, rows):
    pd.DataFrame(rows).to_sql("profiles", conn, index=False)
    items = [{**it, "platform": "podcast", "platform_id": r["platform_id"]} for r in rows for it in good_items()]
    pd.DataFrame(items).drop(columns=["published"]).to_sql("content_items", conn, index=False)


def verified(conn):
    return pd.read_sql("SELECT * FROM verified", conn).set_index("platform_id")


def test_run_writes_table_with_reasons(conn, cfg, fake_http):
    fake_http(lambda url, params: gemini_reply(CREATOR))
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


# ---------- creator or organisation (LLM) ----------


def test_llm_creator_answer_passes_with_checked_quote(conn, cfg, fake_http):
    fake = fake_http(lambda url, params: gemini_reply(CREATOR))
    load(conn, [profile()])
    verify.run(conn, cfg)
    v = verified(conn).loc["itunes:1"]
    assert v.candidate_status == "Qualified" and v.creator_kind == "creator"
    assert v.creator_evidence_url == profile()["profile_url"]  # the description the quote came from
    call = fake.calls[0]
    assert "gemini-" in call["url"] and "test-key" not in call["url"]  # key in the header, not the URL
    assert call["headers"]["x-goog-api-key"] == "test-key"


def test_llm_organisation_answer_rejects(conn, cfg, fake_http):
    org = {"kind": "organisation", "reason": "an agency's show", "quote": "Get in touch", "source": "WEBSITE"}
    fake_http(lambda url, params: gemini_reply(org))
    load(conn, [profile()])
    verify.run(conn, cfg)
    v = verified(conn).loc["itunes:1"]
    assert v.candidate_status == "Rejected" and v.rejection_reason == "not a creator (LLM): an agency's show"
    assert v.creator_evidence_url == f"{SITE}/contact"


def test_invented_quote_is_rejected(conn, cfg, fake_http):
    made_up = {**CREATOR, "quote": "Jane is a famous solo creator from Austin"}
    fake_http(lambda url, params: gemini_reply(made_up))
    load(conn, [profile()])
    verify.run(conn, cfg)
    v = verified(conn).loc["itunes:1"]
    assert v.candidate_status == "Rejected" and v.creator_kind == "unverified"
    assert "model quote not found" in v.rejection_reason


def test_unclear_is_rejected(conn, cfg, fake_http):
    fake_http(lambda url, params: gemini_reply({**CREATOR, "kind": "unclear"}))
    load(conn, [profile()])
    verify.run(conn, cfg)
    assert verified(conn).loc["itunes:1", "rejection_reason"] == "creator status unclear (LLM)"


def test_llm_only_asked_about_otherwise_qualified_rows(conn, cfg, fake_http):
    fake = fake_http(lambda url, params: gemini_reply(CREATOR))
    load(conn, [profile(), profile(platform_id="itunes:2", description="Weekly interviews.", website=None)])
    verify.run(conn, cfg)
    assert len(fake.calls) == 1  # itunes:2 already fails on country, so it costs no LLM call


def test_llm_rerun_is_cached(conn, cfg, fake_http):
    fake = fake_http(lambda url, params: gemini_reply(CREATOR))
    load(conn, [profile()])
    verify.run(conn, cfg)
    verify.run(conn, cfg)
    assert len(fake.calls) == 1


def test_llm_down_stops_after_two_failures(conn, cfg, fake_http):
    fake = fake_http(lambda url, params: FakeResponse(503))
    load(conn, [profile(platform_id=f"itunes:{i}") for i in range(4)])
    verify.run(conn, cfg)
    reasons = verified(conn).rejection_reason.tolist()
    assert reasons[:2] == ["creator check failed (gave up after 3 attempts (HTTP 503))"] * 2
    assert reasons[2:] == ["creator check not run (LLM unavailable)"] * 2
    assert len(fake.calls) == 6  # 2 rows x 3 attempts, then no more calls


def test_missing_llm_key_rejects_without_calling(conn, cfg, fake_http, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    fake = fake_http(lambda url, params: gemini_reply(CREATOR))
    load(conn, [profile()])
    verify.run(conn, cfg)
    assert verified(conn).loc["itunes:1", "rejection_reason"] == "creator check failed (LLM_API_KEY is empty)"
    assert fake.calls == []


# ---------- hand check of the 2-category run (2026-10-28) ----------


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"website": "https://www.lbc.co.uk/radio/presenters/jane/"}, "website on lbc.co.uk"),
        ({"emails": json.dumps([{"value": "janeshow@global.com", "source_url": "x"}])}, "contact email on global.com"),
        ({"website": "http://podcasts.voxmedia.com"}, "website on voxmedia.com"),
    ],
)
def test_broadcaster_or_network_show_is_not_a_creator(cfg, overrides, reason):
    ok, why = verify.check_not_organisation(profile(**overrides), cfg["verify"]["media_domains"])
    assert not ok and reason in why


def test_hosting_platform_website_is_not_an_organisation(cfg):
    ok, _ = verify.check_not_organisation(profile(website="https://janedoe.libsyn.com"), cfg["verify"]["media_domains"])
    assert ok


@pytest.mark.parametrize(
    "url,params",
    [
        ("https://www.youtube.com/@JaneDoe?sub_confirmation=1", {"forHandle": "@JaneDoe"}),
        ("https://youtube.com/channel/UCvGAY-5kSoCxahkDoeCJRfA", {"id": "UCvGAY-5kSoCxahkDoeCJRfA"}),
        ("https://www.youtube.com/user/djockers", {"forUsername": "djockers"}),
        ("https://www.youtube.com/c/KatieCouric", {"forHandle": "@KatieCouric"}),
        ("https://www.youtube.com/ChrisVanVliet", {"forHandle": "@ChrisVanVliet"}),
        ("https://www.youtube.com/watch?v=BZrJraN2nOQ", None),
        ("https://www.youtube.com/playlist?list=PLKv1KCSKwOo", None),
    ],
)
def test_linked_youtube_channel(url, params):
    p = profile(links=json.dumps([{"url": url, "source_url": SITE}]))
    assert verify.linked_youtube_channel(p)[0] == params


def channel_reply(subs):
    return FakeResponse(200, {"items": [{"snippet": {"title": "Jane Doe"}, "statistics": {"subscriberCount": subs}}]})


@pytest.mark.parametrize("subs,status", [("2400000", "Rejected"), ("12000", "Qualified")])
def test_podcast_size_from_linked_youtube_channel(conn, cfg, fake_http, monkeypatch, subs, status):
    monkeypatch.setenv("YOUTUBE_API_KEY", "yt")
    fake = fake_http(
        lambda url, params: channel_reply(subs) if "googleapis.com/youtube" in url else gemini_reply(CREATOR)
    )
    load(conn, [profile(links=json.dumps([{"url": "https://www.youtube.com/@JaneDoe", "source_url": SITE}]))])
    verify.run(conn, cfg)
    v = verified(conn).loc["itunes:1"]
    assert v.candidate_status == status and v.followers_or_subscribers == int(subs)
    assert "youtube.com/@JaneDoe" in v.size_evidence
    if status == "Rejected":
        assert v.rejection_reason.startswith("size: linked YouTube channel Jane Doe has 2400000 subscribers")
        assert len(fake.calls) == 1  # too big: no LLM call


def test_no_linked_channel_means_no_size_call(conn, cfg, fake_http, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "yt")
    fake = fake_http(lambda url, params: gemini_reply(CREATOR))
    load(conn, [profile()])
    verify.run(conn, cfg)
    assert verified(conn).loc["itunes:1", "candidate_status"] == "Qualified"
    assert not any("youtube" in c["url"] for c in fake.calls)


ABOUT = f"{SITE}/about"
STAFF_PAGE = json.dumps([{"url": ABOUT, "title": "", "text": "Coach Kendal lives in Texas and helps our clients."},
                         {"url": f"{SITE}/contact", "title": "", "text": "Get in touch"}])  # fmt: skip


@pytest.mark.parametrize("about,status", [("someone else", "Rejected"), ("host", "Qualified")])
def test_website_country_quote_must_be_about_the_host(conn, cfg, fake_http, about, status):
    fake = fake_http(
        lambda url, params: gemini_reply({**CREATOR, "quote": "Weekly interviews.", "country_quote_about": about})
    )
    load(conn, [profile(description="Weekly interviews.", pages=STAFF_PAGE)])
    verify.run(conn, cfg)
    v = verified(conn).loc["itunes:1"]
    assert v.country_evidence_url == ABOUT and v.candidate_status == status
    assert "COUNTRY QUOTE: " in json.dumps(fake.calls[0]["json"])  # the quote was put to the model
    if status == "Rejected":
        assert v.rejection_reason == "country not evidenced: the quote is about someone else, not the host (LLM)"


def test_description_country_sentence_is_put_to_the_llm(conn, cfg, fake_http):
    fake = fake_http(lambda url, params: gemini_reply(CREATOR))
    load(conn, [profile()])  # "Based in Austin, Texas." is a sentence in the show's description
    verify.run(conn, cfg)
    assert "COUNTRY QUOTE: " in json.dumps(fake.calls[0]["json"])
    assert verified(conn).loc["itunes:1", "candidate_status"] == "Qualified"


def test_country_domain_is_not_put_to_the_llm(conn, cfg, fake_http):
    fake = fake_http(lambda url, params: gemini_reply({**CREATOR, "quote": "Weekly interviews."}))
    load(conn, [profile(description="Weekly interviews.", website="https://janedoe.co.uk")])
    verify.run(conn, cfg)
    assert "COUNTRY QUOTE: " not in json.dumps(fake.calls[0]["json"])
    assert verified(conn).loc["itunes:1", "country_iso2"] == "GB"


def test_unclear_country_quote_is_rejected(conn, cfg, fake_http):
    fake_http(
        lambda url, params: gemini_reply({**CREATOR, "quote": "Weekly interviews.", "country_quote_about": "unclear"})
    )
    load(conn, [profile(description="Weekly interviews.", pages=STAFF_PAGE)])
    verify.run(conn, cfg)
    reason = verified(conn).loc["itunes:1", "rejection_reason"]
    assert reason == "country not evidenced: the quote is not shown to be about the host (LLM: unclear)"
