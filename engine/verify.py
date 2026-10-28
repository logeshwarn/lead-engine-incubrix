"""Stage 3, verify: profiles + content_items -> the `verified` table.

Runs the qualification checks from the brief and the assignment (docs/WORKFLOW.md) on every
profile. A check passes only with evidence: a verbatim quote from the creator's own public text
(or a count over their public items) plus the URL where it can be seen. No evidence, no pass.

Checks 6 (personalised and compliant) and 7 (complete and unique) are finished later: draft checks
the messages and dedupe/export check uniqueness and completeness. Here they only check that the
ingredients exist (a recent item to cite; evidence dated within 30 days).

Rows that fail any check keep candidate_status = Rejected and a rejection_reason; export writes
them to rejected.csv. Nothing is dropped silently.
"""

import json
import logging
import os
import re
from datetime import timedelta

import pandas as pd
import tldextract
from langdetect import DetectorFactory, LangDetectException, detect

from engine import route
from engine.common import ApiError, cached_get, gemini_json, now_utc
from engine.enrich import YT_CHANNELS_URL

log = logging.getLogger("verify")

DetectorFactory.seed = 0  # langdetect is random by default; a fixed seed makes reruns identical
DOMAINS = tldextract.TLDExtract(suffix_list_urls=())  # bundled suffix list: no network call

# ---------- check 1: not a creator (assignment section 2) ----------
# Words in the channel or show NAME that mark an organisation, not a creator.
EXCLUDE_NAME = re.compile(
    # Not "official", "TV", "productions" or "studio": many solo creators use those in their names.
    # Not "agency" or "network" alone: "Smart Agency Masterclass" (a coach for agency owners) and
    # "Network Marketing" are topics. Only names that are an organisation's own title count.
    r"\b((podcast|media|radio|tv) network|media group|news|magazine|newspaper|fan ?page|fans|clips|highlights"
    r"|compilation|bank|university|college|church|radio station|records|directory)\b",
    re.I,
)
# Phrases where the account speaks AS an organisation ("we are a digital agency"), or is a fan/repost
# account. A host who runs an agency is still an expert-led creator, so "founder of X agency" passes.
EXCLUDE_DESC = re.compile(
    r"\b(we are an? ([\w-]+ ){0,3}(agency|company|firm|network|publication)|we're an? ([\w-]+ ){0,3}(agency|company"
    r"|firm)|(a|the) (podcast|media) network|management (company|firm)|fan (account|channel|page)"
    r"|not affiliated with|unofficial)\b",
    re.I,
)

# ---------- check 1: country ----------
# Place names that identify an approved country. Longest names are tried first, so
# "northern ireland" wins over "ireland" and "new south wales" over "wales".
PLACES = {
    "US": ["united states", "usa", "u.s.a.", "u.s.", "new york", "los angeles", "chicago", "houston", "austin",
           "dallas", "san francisco", "seattle", "boston", "miami", "atlanta", "denver", "nashville", "phoenix",
           "san diego", "philadelphia", "minneapolis", "alabama", "alaska", "arizona", "arkansas", "california",
           "colorado", "connecticut", "delaware", "florida", "hawaii", "idaho", "illinois", "indiana", "iowa",
           "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota",
           "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico",
           "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
           "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
           "west virginia", "wisconsin", "wyoming"],
    "CA": ["canada", "toronto", "vancouver", "montreal", "calgary", "ottawa", "edmonton", "ontario", "quebec",
           "british columbia", "alberta", "manitoba", "saskatchewan", "nova scotia", "new brunswick"],
    "GB": ["united kingdom", "uk", "u.k.", "great britain", "britain", "england", "scotland", "wales",
           "northern ireland", "london", "manchester", "birmingham", "glasgow", "edinburgh", "bristol", "leeds",
           "liverpool", "cardiff", "belfast"],
    "IE": ["ireland", "dublin", "cork", "galway", "limerick"],
    "AU": ["australia", "sydney", "melbourne", "brisbane", "adelaide", "canberra", "queensland",
           "new south wales", "western australia", "south australia", "tasmania"],
    "NZ": ["new zealand", "auckland", "wellington", "christchurch"],
    "SG": ["singapore"],
    # Not approved, but recognised so the row is rejected for the right reason.
    "Other": ["india", "pakistan", "bangladesh", "nigeria", "philippines", "south africa", "germany", "kenya",
              "dubai", "uae", "brazil", "mexico", "spain", "france", "netherlands", "indonesia", "italy"],
}  # fmt: skip
PLACE_TO_COUNTRY = sorted(((p, c) for c, ps in PLACES.items() for p in ps), key=lambda pc: -len(pc[0]))
# A place only counts when the text says the creator is there, not just mentions it.
LOCATION_PHRASE = re.compile(
    r"\b(based|located|headquartered|living|live|lives|residing)\s+(in|out of)\s+(?P<p1>[^.;:!?\n|]{2,60})"
    r"|\b(?P<p2>[A-Z][\w .]{1,30})-based\b"
    # "from" only with a subject ("we are all from ..."), so "lessons from London" does not count
    r"|\b(i am|i'm|we are|we're|he is|she is|they are|hosts? (is|are))( all| originally| both)? from\s+"
    r"(?P<p3>[^.;:!?\n|]{2,60})",
    re.I,
)
# Country-code website domains. Most of these registries require a local connection to register,
# so the creator's own domain is public evidence of country (weaker than a stated location).
COUNTRY_DOMAINS = {"uk": "GB", "ca": "CA", "ie": "IE", "au": "AU", "nz": "NZ", "sg": "SG"}
US_STATES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK"
    "|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
)
# Postal addresses and phone prefixes are strong, unambiguous signals. (+1 is shared by US and CA, so it is skipped.)
POSTAL = [
    ("US", re.compile(rf"\b[A-Z][a-zA-Z .]+,\s*({US_STATES})\s+\d{{5}}(-\d{{4}})?\b")),
    ("CA", re.compile(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b")),
    ("GB", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s\d[A-Z]{2}\b")),
    ("AU", re.compile(r"\b(NSW|VIC|QLD|SA|TAS|ACT|NT)\s+\d{4}\b")),
]
POSTAL_PATTERNS = {pattern for _, pattern in POSTAL}  # street addresses: trusted on contact/about pages only
ADDRESS_PATTERNS = POSTAL + [
    ("GB", re.compile(r"\+44[\s\d()-]{9,}")),
    ("IE", re.compile(r"\+353[\s\d()-]{8,}")),
    ("AU", re.compile(r"\+61[\s\d()-]{8,}")),
    ("NZ", re.compile(r"\+64[\s\d()-]{7,}")),
    ("SG", re.compile(r"\+65[\s\d()-]{7,}")),
]

# ---------- check 3: commercial ----------
COMMERCIAL = [
    ("Sponsorship", re.compile(
        r"(sponsored by|this (episode|video|show) is (brought to you|sponsored) by|thanks? to (our|today's) sponsors?"
        r"|brought to you by|paid partnership|use (promo |discount )?code\s+\w+|promo code"
        # selling sponsor slots is sponsorship income too
        r"|become a sponsor|sponsor (the|our|this) (show|podcast|channel)|sponsorship (opportunities|packages|info)"
        r"|advertise (with us|on (the|our) (show|podcast)))", re.I)),
    ("Affiliate", re.compile(
        r"(affiliate link|as an amazon associate|i (may )?earn a (small )?commission|commission (from|on) (qualifying"
        r"|purchases))", re.I)),
    # Offer wording only: an episode titled "Protein Masterclass" is a topic, not a course for sale.
    ("Course", re.compile(r"((my|our) (online |new |free )?(course|masterclass|bootcamp|cohort)|online course"
                          r"|enrol+ (now|today)|(join|register for|sign up for) (my|our|the) (\w+ )?(masterclass"
                          r"|course|bootcamp|cohort))", re.I)),
    ("Service", re.compile(
        r"(work with (me|us)|book a (free )?(call|consultation|session)|coaching (program|package|call)|hire me"
        r"|consulting services|1[:-]1 (coaching|mentoring)|one-on-one (\w+ )?(coaching|mentoring)"
        r"|(coaching|consulting|mentoring) (services|programs?|packages?))", re.I)),
    ("Membership", re.compile(r"(join (my|our|the) (membership|community|patreon)|become a (member|patron)"
                              r"|paid subscribers?|premium (episodes|membership)"
                              r"|support (the|this|our) (show|podcast|channel))", re.I)),
    ("Product", re.compile(r"(buy my book|my new book|pre-?order|shop (my|our|the) (merch|store)|merch store"
                           r"|(my|our) (\w+ ){0,2}(training|fitness|workout|coaching) programs?|free trial|shop now"
                           r"|buy now)", re.I)),
]  # fmt: skip
# Links to these sites are themselves public evidence of an offer.
COMMERCIAL_DOMAINS = {
    "patreon.com": "Membership", "buymeacoffee.com": "Membership", "ko-fi.com": "Membership",
    "memberful.com": "Membership", "skool.com": "Membership", "supercast.com": "Membership",
    "teachable.com": "Course", "kajabi.com": "Course", "thinkific.com": "Course", "podia.com": "Course",
    "maven.com": "Course", "gumroad.com": "Product", "amzn.to": "Affiliate", "geni.us": "Affiliate",
    "calendly.com": "Service",
}  # fmt: skip

# ---------- check 4: needs IncuBrix (creator's own words) ----------
NEED_WORDS = re.compile(
    r"(hiring (a |an )?(video |podcast |content )?(editor|producer|assistant)|looking for (a |an )?(video |podcast )?"
    r"(editor|producer)|(sorry|apologi[sz]e) for the (delay|late (upload|episode))|been a while since (my|our) last"
    r"|taking a (short )?break|on (a )?hiatus|behind on (episodes|uploads|editing)"
    r"|editing (takes|took) (forever|so long)|transcripts? coming soon)",
    re.I,
)

# ---------- check 5: reachable ----------
# Addresses on these domains are platform, host or site-builder addresses, not the creator's inbox.
NOT_CREATOR_EMAIL_DOMAINS = {
    "anchor.fm", "spotify.com", "libsyn.com", "buzzsprout.com", "podbean.com", "megaphone.fm", "simplecast.com",
    "transistor.fm", "captivate.fm", "acast.com", "omny.fm", "redcircle.com", "spreaker.com", "audioboom.com",
    "godaddy.com", "wix.com", "squarespace.com", "wordpress.com", "sentry.io", "example.com", "domain.com",
    "promo.ly", "iheart.com", "art19.com", "podcastindex.org", "apple.com", "google.com", "youtube.com",
    "soundcloud.com", "blubrry.com", "pinecast.com", "fireside.fm", "riverside.fm", "podcastics.com",
    "podomatic.com", "castos.com", "rss.com", "zencast.fm",
}  # fmt: skip
NO_CONTACT_LOCAL = re.compile(r"^(no-?reply|donotreply|do-not-reply|privacy|abuse|dmca|unsubscribe|bounce|postmaster)")
BUSINESS_LABEL = re.compile(
    r"(business|inquir|enquir|contact|booking|partnership|sponsor|collab|press|media|work with|email (me|us))", re.I
)
# An invitation to pitch, not a testimonial ("It was a delight to be a guest on ...").
GUEST_PITCH = re.compile(r"((apply|want|interested in being|would like) to be (a|our) guest|become a guest"
                         r"|guest (application|request|form|submission)|apply to be (a|on the) (guest|show)"
                         r"|pitch (us|the show|a guest))", re.I)  # fmt: skip

# Only links shaped like a profile count; share buttons (twitter.com/intent/...) and articles
# (linkedin.com/pulse/...) are not a way to reach someone.
# Hosting platforms put their own social accounts in the footer of every show page they host.
HOSTING_BRANDS = {d.split(".")[0] for d in NOT_CREATOR_EMAIL_DOMAINS}
HOSTING_HANDLE = re.compile(rf"^({'|'.join(sorted(HOSTING_BRANDS))})(com|fm|app|hq|podcast|podcasts|podcasting)?$")


def platform_account(url):
    """True for a social profile that is a hosting platform's own, e.g. x.com/rss or instagram.com/rss_podcasting."""
    handle = re.sub(r"^https?://[^/]+/(in/|company/|@)?", "", url).split("/")[0].split("?")[0]
    return bool(HOSTING_HANDLE.match(compact(handle)))


SOCIAL_PROFILE = [
    ("LinkedIn", re.compile(r"^https?://([\w-]+\.)?linkedin\.com/(in|company)/[^/?#]+/?([?#].*)?$", re.I)),
    ("Instagram", re.compile(r"^https?://(www\.)?instagram\.com/(?!p/|reel/|explore/|stories/)[\w.]+/?([?#].*)?$",
                             re.I)),
    ("X", re.compile(r"^https?://(www\.|mobile\.)?(x|twitter)\.com/(?!intent|share|hashtag|search|i/|home)\w+/?"
                     r"([?#].*)?$", re.I)),
    ("TikTok", re.compile(r"^https?://(www\.)?tiktok\.com/@[\w.]+/?([?#].*)?$", re.I)),
]  # fmt: skip

VERIFIED_COLUMNS = [
    "platform", "platform_id", "creator_name", "creator_segment", "niche", "seed_id", "profile_url",
    "stable_creator_id", "followers_or_subscribers", "size_evidence", "website",
    "country_iso2", "country_evidence", "country_evidence_url",
    "primary_language", "english_share",
    "creator_kind", "creator_evidence", "creator_evidence_url",  # set by the LLM check (check_creator)
    "country_quote_about",  # LLM: whom a website country quote describes (check_creator)
    "content_count_30d", "longform_count_60d", "last_content_date", "recent_content_url", "recent_content_title",
    "monetization_signal", "monetization_evidence", "monetization_evidence_url",
    "incubrix_need", "need_kind", "need_evidence", "need_evidence_url",
    "contacts",  # JSON list of {"channel", "value", "evidence_url", "note"}; route picks best and backup
    "checked_date",
    "check_real_relevant", "check_active", "check_commercial", "check_needs_incubrix", "check_reachable",
    "check_personalisable", "check_fresh_evidence",
    "candidate_status", "rejection_reason",
]  # fmt: skip


# ---------- helpers ----------


def quote(text, start, end, width):
    """The matched words with some context either side, on one line, cut to `width` characters."""
    pad = max(0, (width - (end - start)) // 2)
    snippet = text[max(0, start - pad) : end + pad]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet[:width]


def registered_domain(url_or_email):
    value = (url_or_email or "").split("@")[-1]
    ext = DOMAINS(value)
    return ext.top_domain_under_public_suffix.lower() if ext.suffix else ""


def own_texts(profile):
    """Text the creator writes about themselves: the profile/show description and their own website."""
    out = [(profile["description"] or "", profile["profile_url"])]
    out += [(p["text"], p["url"]) for p in json.loads(profile["pages"] or "[]")]
    return [(t, u) for t, u in out if t and u]


def texts(profile, items):
    """Every public text we hold for a creator, newest items first, each with the URL it can be seen at.

    Item descriptions (show notes) often describe guests, so facts ABOUT the creator (country,
    contact) use own_texts only. Offers and needs may come from items: a sponsor read is the show's.
    """
    out = [(f"{it['title'] or ''}. {it['description'] or ''}", it["url"] or profile["profile_url"]) for it in items]
    return [(t, u) for t, u in out if t and u] + own_texts(profile)


# ---------- the checks; each returns (passed, details) ----------


def check_not_organisation(profile, media_domains=()):
    m = EXCLUDE_NAME.search(profile["name"] or "")
    if m:
        return False, f"not a creator: {m.group(0)!r} in name"
    m = EXCLUDE_DESC.search(profile["description"] or "")
    if m:
        return False, f"not a creator: {m.group(0)!r} in description"
    # A show whose own website or contact email is on a broadcaster's or podcast network's domain is
    # that company's programme, even with a named presenter (hand check 2026-10-28: LBC, Vox Media).
    media = set(media_domains)
    website = registered_domain(profile.get("website"))
    if website in media:
        return False, f"not a creator: website on {website} (broadcaster or network)"
    for e in json.loads(profile.get("emails") or "[]"):
        domain = registered_domain(e["value"])
        if domain in media:
            return False, f"not a creator: contact email on {domain} (broadcaster or network)"
    return True, None


def find_country(profile, items, width):
    """(country, quote, url) from the strongest public evidence, or (None, None, None).

    Order: country stated on the platform, location stated in the creator's own feed, a postal
    address or phone prefix, a "based in / from" sentence, and last the website's country domain.
    Only the creator's own texts count: show notes describe guests ("an Austin-based company").
    """
    if profile["country"]:  # stated on the platform profile itself
        return profile["country"], f"Channel country: {profile['country']}", profile["profile_url"]
    stated = profile.get("location")
    if stated and place_country(stated):
        return place_country(stated), f"Feed location tag: {stated}", profile["feed_url"]
    for text, url in own_texts(profile):
        # A street address only counts on a contact/about page or in the description: a homepage can
        # list an event venue or a client's address.
        address_ok = url == profile["profile_url"] or any(w in url.lower() for w in ("contact", "about"))
        for country, pattern in ADDRESS_PATTERNS:
            if pattern in POSTAL_PATTERNS and not address_ok:
                continue
            m = pattern.search(text)
            if m:
                return country, quote(text, m.start(), m.end(), width), url
        for m in LOCATION_PHRASE.finditer(text):
            country = place_country(m.group("p1") or m.group("p2") or m.group("p3") or "")
            if country:
                return country, quote(text, m.start(), m.end(), width), url
    suffix = DOMAINS(profile["website"] or "").suffix.split(".")[-1] if profile["website"] else ""
    if suffix in COUNTRY_DOMAINS:
        domain = registered_domain(profile["website"])
        return COUNTRY_DOMAINS[suffix], f"Website domain {domain} (.{suffix} country domain)", profile["website"]
    return None, None, None


def place_country(place_text):
    """Country for a place phrase like 'Austin, TX' or 'the UK', or None.

    The right-most place wins, because "City, Region" ends with the more telling part:
    "Birmingham, Alabama" is US and "London, Ontario" is CA.
    """
    us_state = re.search(rf",\s*({US_STATES})\b", place_text)  # "City, ST" before lower-casing
    if us_state:
        return "US"
    place_text = place_text.lower()
    found = []  # (end position, length, country)
    for place, country in PLACE_TO_COUNTRY:
        for m in re.finditer(rf"(?<![\w.]){re.escape(place)}(?![\w])", place_text):
            found.append((m.end(), len(place), country))
    return max(found)[2] if found else None


def english_share(profile, items):
    samples = [f"{it['title']}. {it['description'] or ''}"[:500] for it in items]
    samples = samples or [profile["description"] or ""]
    langs = []
    for s in samples:
        try:
            langs.append(detect(s) if len(s.strip()) >= 20 else None)
        except LangDetectException:
            langs.append(None)
    known = [lang for lang in langs if lang]
    return (sum(lang == "en" for lang in known) / len(known)) if known else None


def activity(items, config):
    now = now_utc()
    a = config["activity"]
    recent = [it for it in items if it["published"] >= now - timedelta(days=a["recent_days"])]
    long_form = [
        it
        for it in items
        if it["published"] >= now - timedelta(days=a["long_form_days"])
        and (it["duration_seconds"] or 0) >= a["long_form_min_minutes"] * 60
    ]
    passed = len(recent) >= a["recent_items"] or len(long_form) >= a["long_form_items"]
    return passed, len(recent), len(long_form)


def compact(text):
    """Lower-case letters and digits only, so "The OT Coach" and theotcoach.au can be compared."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def self_mention(profile, text, end):
    """True when the words after "brought to you by" name the show or its own website.

    "Brought to you by Alyce Svensk at The OT Coach Australia" on theotcoach.au is the creator
    promoting themselves, not a sponsor (hand check 2026-10-28).
    """
    after = compact(text[end : end + 100])
    site = compact(DOMAINS(profile["website"] or "").domain)
    name = compact(profile["name"])
    return (len(site) >= 4 and site in after) or (len(name) >= 4 and name in after)


def find_commercial(profile, items, width):
    for text, url in texts(profile, items):
        for kind, pattern in COMMERCIAL:
            for m in pattern.finditer(text):
                if "brought to you by" in m.group(0).lower() and self_mention(profile, text, m.end()):
                    continue
                return kind, quote(text, m.start(), m.end(), width), url
    own_urls = {u for _, u in own_texts(profile)} | {p["url"] for p in json.loads(profile["pages"] or "[]")}
    own_urls.add(profile["website"])
    for link in json.loads(profile["links"] or "[]"):
        if link["source_url"] not in own_urls:
            continue  # a Patreon link in show notes is often a guest's or a friend's (hand check 2026-10-28)
        kind = COMMERCIAL_DOMAINS.get(registered_domain(link["url"]))
        if kind:
            return kind, f"Link to {link['url']}", link["source_url"]
    return None, None, None


def find_need(profile, items, config):
    """(kind, summary, quote, url). Creator's own words first, then observed gaps (decision 2026-10-27)."""
    v, width = config["verify"], config["verify"]["quote_chars"]
    for text, url in texts(profile, items):
        m = NEED_WORDS.search(text)
        if m:
            q = quote(text, m.start(), m.end(), width)
            return "own words", f"Creator says: {q}", q, url
    if not items:
        return None, None, None, None
    youtube = profile["platform"] == "youtube"
    latest = items[0]
    known = [it["has_captions"] for it in items if it["has_captions"] is not None]
    # Only claim "no captions" when the caption status of every item is known.
    if len(items) >= v["caption_gap_min_items"] and len(known) == len(items) and not any(known):
        what = "videos have creator-uploaded captions" if youtube else "episodes have a transcript"
        summary = f"Captions: none of the last {len(items)} {what}"
        return "captions", summary, f"{summary} (latest: {latest['title']})", latest["url"]
    long_items = [
        it for it in items if (it["duration_seconds"] or 0) >= config["activity"]["long_form_min_minutes"] * 60
    ]
    if len(long_items) >= v["repurpose_min_long_items"]:
        if youtube and not any((it["duration_seconds"] or 0) <= v["short_max_seconds"] for it in items):
            summary = f"Repurposing: {len(long_items)} long videos and no Shorts in the last 60 days"
            return "repurposing", summary, f"{summary} (latest: {latest['title']})", latest["url"]
        has_video = any(
            registered_domain(lk["url"]) in ("youtube.com", "youtu.be", "tiktok.com")
            for lk in json.loads(profile["links"] or "[]")
        )
        # "No video presence" is only a fair claim when we actually read their website.
        if not youtube and not has_video and json.loads(profile["pages"] or "[]"):
            summary = f"Repurposing: {len(long_items)} long episodes and no YouTube or TikTok link on feed or site"
            return "repurposing", summary, f"{summary} (latest: {latest['title']})", profile["website"] or latest["url"]
    dates = sorted(it["published"] for it in items)
    gaps = [(b - a, b) for a, b in zip(dates, dates[1:], strict=False)]
    if len(dates) >= 4 and gaps:
        gap, after = max(gaps)
        if gap.days >= v["consistency_gap_days"]:
            item = next(it for it in items if it["published"] == after)
            summary = f"Consistency: {gap.days}-day gap between uploads before {after.date()}"
            return "consistency", summary, f"{summary} ({item['title']})", item["url"]
    return None, None, None, None


def find_contacts(profile, items, config):
    """Contact options the creator published, each with the URL that shows it. Never constructed."""
    contacts = []
    site_domain = registered_domain(profile["website"])
    recent_text = " ".join(f"{it['title']} {it['description'] or ''}" for it in items).lower()
    own_by_url = {u: t for t, u in own_texts(profile)}
    # Every page of the creator's own, even one with no text (a contact page that is just a mailto: link).
    own_by_url.update(
        {p["url"]: p["text"] or "" for p in json.loads(profile["pages"] or "[]") if p["url"] not in own_by_url}
    )
    for e in json.loads(profile["emails"] or "[]"):
        value, source = e["value"], e["source_url"]
        domain = registered_domain(value)
        if domain in NOT_CREATOR_EMAIL_DOMAINS or NO_CONTACT_LOCAL.match(value):
            continue
        own_domain = site_domain and domain == site_domain
        feed_owner = source == profile["feed_url"]
        if not (own_domain or feed_owner or source in own_by_url):
            continue  # only seen in show notes: it may be a guest's or a sponsor's address
        source_text = own_by_url.get(source, "")
        pos = source_text.lower().find(value)
        labelled = pos >= 0 and BUSINESS_LABEL.search(source_text[max(0, pos - 80) : pos])
        contact_page = "contact" in source.lower()  # e.g. a mailto: link on their own contact page
        if not (own_domain or labelled or feed_owner or contact_page):
            continue  # a stray address in page text is not shown to be a business contact
        if own_domain:
            note = "on creator's own domain"
        elif contact_page:
            note = "on creator's contact page"
        elif labelled:
            note = "labelled for business contact"
        else:
            note = "listed as the show's contact in its RSS feed"
        if value in recent_text:
            note += "; also in content from the last 60 days"
        contacts.append({"channel": "Email", "value": value, "evidence_url": source, "note": note})
    for page in json.loads(profile["pages"] or "[]"):
        if "contact" in page["url"].lower():
            contacts.append({"channel": "Contact form", "value": page["url"], "evidence_url": page["url"],
                             "note": "contact page on creator's website"})  # fmt: skip
        m = GUEST_PITCH.search(page["text"] or "")
        if m and profile["platform"] == "podcast":
            contacts.append({"channel": "Podcast guest pitch", "value": page["url"], "evidence_url": page["url"],
                             "note": quote(page["text"], m.start(), m.end(), 80)})  # fmt: skip
    for link in json.loads(profile["links"] or "[]"):
        if link["source_url"] not in own_by_url:
            continue  # social links in show notes are usually the guest's
        channel = next((name for name, pattern in SOCIAL_PROFILE if pattern.match(link["url"])), None)
        if channel and not platform_account(link["url"]):
            contacts.append({"channel": channel, "value": link["url"], "evidence_url": link["source_url"],
                             "note": "linked by the creator; activity not checked (platform not read)"})  # fmt: skip
    seen, unique = set(), []
    for c in contacts:
        if (c["channel"], c["value"]) not in seen:
            seen.add((c["channel"], c["value"]))
            unique.append(c)
    return unique


def verify_profile(profile, items, config):
    """All checks for one creator. Returns one `verified` row."""
    width = config["verify"]["quote_chars"]
    now = now_utc()
    row = dict.fromkeys(VERIFIED_COLUMNS)
    row.update(
        platform=profile["platform"],
        platform_id=profile["platform_id"],
        creator_name=profile["name"],
        creator_segment=profile["segment"],
        niche=profile["niche"],
        seed_id=profile["seed_id"],
        profile_url=profile["profile_url"],
        stable_creator_id=profile["platform_id"],
        followers_or_subscribers=profile["subscribers"],
        website=profile["website"],
        checked_date=profile["enriched_at"],
    )
    reasons = []

    status = profile["enrich_status"] or ""
    if status.startswith(("skipped", "failed")):
        reasons.append(f"enrich {status}")

    # 1. Real and relevant
    real_ok = True
    if not (profile["platform_id"] and profile["profile_url"]):
        real_ok = False
        reasons.append("no stable platform ID or profile URL")
    if profile["segment"] not in config["segments"]:
        real_ok = False
        reasons.append(f"segment {profile['segment']!r} not approved")
    not_org, why = check_not_organisation(profile, config["verify"]["media_domains"])
    if not not_org:
        real_ok = False
        reasons.append(why)
    country, c_quote, c_url = find_country(profile, items, width)
    row.update(country_iso2=country, country_evidence=c_quote, country_evidence_url=c_url)
    if country is None:
        real_ok = False
        reasons.append("country not evidenced")
    elif country not in config["countries"]["approved"]:
        real_ok = False
        reasons.append(f"country {country} not approved")
    share = english_share(profile, items)
    row.update(english_share=None if share is None else round(share, 2), primary_language="en" if share else None)
    if share is None or share < config["verify"]["english_min_share"]:
        real_ok = False
        reasons.append("content not mainly English" if share is not None else "language unknown")
        row["primary_language"] = None
    row["check_real_relevant"] = real_ok

    # 2. Active
    active_ok, n30, n_long = activity(items, config)
    latest = items[0] if items else None
    row.update(
        content_count_30d=n30,
        longform_count_60d=n_long,
        last_content_date=(latest["published"].date().isoformat() if latest else profile["last_content_at"]),
        # Episodes without their own link are listed on the show page, so that page is the link to cite.
        recent_content_url=(latest["url"] or profile["profile_url"]) if latest else None,
        recent_content_title=latest["title"] if latest else None,
        check_active=active_ok,
    )
    if not active_ok:
        reasons.append(f"not active ({n30} items in 30 days, {n_long} long-form in 60 days)")

    # 3. Commercial
    kind, m_quote, m_url = find_commercial(profile, items, width)
    row.update(monetization_signal=kind, monetization_evidence=m_quote, monetization_evidence_url=m_url)
    row["check_commercial"] = kind is not None
    if kind is None:
        reasons.append("no public commercial evidence")

    # 4. Needs IncuBrix
    need_kind, summary, n_quote, n_url = find_need(profile, items, config)
    row.update(incubrix_need=summary, need_kind=need_kind, need_evidence=n_quote, need_evidence_url=n_url)
    row["check_needs_incubrix"] = need_kind is not None
    if need_kind is None:
        reasons.append("no evidence of an IncuBrix need")

    # 5. Reachable: a best and a backup channel the creator published (route.choose: the best one is
    # checkable, the backup may be their own social profile); creator active in the last 60 days.
    contacts = find_contacts(profile, items, config)
    row["contacts"] = json.dumps(contacts)
    active_60 = bool(latest) and latest["published"] >= now - timedelta(days=config["reachable"]["channel_active_days"])
    best, backup = route.choose(contacts, profile["name"], profile["website"])
    row["check_reachable"] = active_60 and best is not None and backup is not None
    if not active_60:
        reasons.append("no activity in the last 60 days")
    elif best is None:
        reasons.append("no published business contact")
    elif backup is None:
        reasons.append(f"no backup channel (only {best['channel']} {best['value']})")

    # 6. Personalisable: a specific recent item to cite (the message itself is checked in draft).
    row["check_personalisable"] = bool(latest and latest["title"] and row["recent_content_url"])
    if not row["check_personalisable"]:
        reasons.append("no recent item to reference")

    # 7. Evidence fresh: checked within the last 30 days (uniqueness is checked by dedupe).
    checked = pd.to_datetime(profile["enriched_at"], utc=True) if profile["enriched_at"] else None
    fresh = checked is not None and now - checked <= timedelta(days=config["evidence"]["max_age_days"])
    row["check_fresh_evidence"] = fresh
    if not fresh:
        reasons.append("evidence older than 30 days")

    row["candidate_status"] = "Rejected" if reasons else "Qualified"
    row["rejection_reason"] = "; ".join(reasons) if reasons else None
    return row


# ---------- check 1: size of podcasts, from the creator's own linked YouTube channel ----------

# Channel links only; watch, playlist and shorts links say nothing about the creator's channel.
YT_CHANNEL_LINK = re.compile(
    r"youtube\.com/(?:channel/(?P<id>UC[\w-]{22})|@(?P<handle>[\w.-]+)|user/(?P<user>[\w.-]+)"
    r"|c/(?P<custom>[\w.-]+)|(?P<bare>(?!(watch|playlist|shorts|embed|results|redirect|live|post)\b)[\w.-]+))"
    r"/?(?:[?#]|$)",
    re.I,
)


def linked_youtube_channel(profile):
    """(channels.list params, link) for the first YouTube channel the creator links to, or (None, None)."""
    for link in json.loads(profile.get("links") or "[]"):
        m = YT_CHANNEL_LINK.search(link["url"])
        if not m:
            continue
        if m["id"]:
            return {"id": m["id"]}, link["url"]
        if m["user"]:
            return {"forUsername": m["user"]}, link["url"]
        # Old custom URLs (/c/Name, /Name) mostly became handles of the same name.
        return {"forHandle": "@" + (m["handle"] or m["custom"] or m["bare"])}, link["url"]
    return None, None


def check_podcast_size(conn, config, row, profile, api_key):
    """Reject a podcast whose linked YouTube channel is above the size limit. Unknown size is no reason.

    Podcast directories publish no audience count, so the creator's own YouTube channel (linked from
    their description or website) is the only public size figure (hand check 2026-10-28).
    """
    params, link = linked_youtube_channel(profile)
    if params is None:
        return
    try:
        data, _ = cached_get(
            conn,
            "youtube.channels",
            YT_CHANNELS_URL,
            {**params, "part": "snippet,statistics", "key": api_key},
            config["http"],
            config["cache"]["enrich_max_age_days"],
        )
    except ApiError as e:
        log.error("size check %s: %s", row["platform_id"], e)
        return
    channel = (data.get("items") or [None])[0]
    if channel is None or channel.get("statistics", {}).get("hiddenSubscriberCount"):
        return
    subs = int(channel["statistics"].get("subscriberCount", 0))
    title = channel.get("snippet", {}).get("title")
    row.update(followers_or_subscribers=subs, size_evidence=f"YouTube channel {title} ({link}): {subs} subscribers")
    limit = config["verify"]["podcast_max_youtube_subscribers"]
    if subs > limit:
        row.update(
            candidate_status="Rejected",
            check_real_relevant=False,
            rejection_reason=f"size: linked YouTube channel {title} has {subs} subscribers (above {limit})",
        )


def apply_size_check(conn, config, rows, profiles_by_id):
    todo = [r for r in rows if r["candidate_status"] == "Qualified" and r["platform"] == "podcast"]
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if todo and not api_key:
        log.error("YOUTUBE_API_KEY is empty: podcast size check skipped")
        return
    for row in todo:
        check_podcast_size(conn, config, row, profiles_by_id[row["platform_id"]], api_key)


# ---------- check 1, last step: creator or organisation (LLM, decision 2026-10-28) ----------

CREATOR_SYSTEM = """You decide who runs a podcast or YouTube channel, using ONLY the text supplied.
- "creator": one person, or a small group of named people, whose own voice and expertise are the show.
  This includes coaches, consultants and educators, and creator-led businesses where the host is the face.
- "organisation": the show is content of a company, agency, brand, publication, network or institution,
  with no individual creator as its face; or a fan or repost account. A programme of a radio or TV
  station, broadcaster, media company, podcast network, church or ministry is "organisation" even when
  a named presenter hosts it.
- "unclear": the text does not show which.
Return "quote": an exact, word-for-word copy of 10 to 200 characters from the DESCRIPTION or WEBSITE
section that best supports your answer, and "source": the section it came from.
Never write a quote that is not in the text. If unsure, answer "unclear".
If a COUNTRY QUOTE is given, return "country_quote_about": "host" if it says where the show's own
host(s) live or are based, or is the address of the host's own business, practice or show; "someone
else" if it is about another person (staff, co-founder, guest, agent) or another organisation (a parent
company, network, publisher or agency); or "unclear". If no COUNTRY QUOTE is given, return "not asked"."""

CREATOR_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "kind": {"type": "STRING", "enum": ["creator", "organisation", "unclear"]},
        "reason": {"type": "STRING"},
        "quote": {"type": "STRING"},
        "source": {"type": "STRING", "enum": ["DESCRIPTION", "WEBSITE"]},
        "country_quote_about": {"type": "STRING", "enum": ["host", "someone else", "unclear", "not asked"]},
    },
    "required": ["kind", "reason", "quote", "source", "country_quote_about"],
}


def normalise(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def creator_prompt(profile, max_chars, country_quote=None):
    pages = json.loads(profile["pages"] or "[]")
    website = "\n\n".join(f"[{p['url']}]\n{p['text']}" for p in pages)
    asked = f"COUNTRY QUOTE: {country_quote}\n\n" if country_quote else ""
    text = (
        f"NAME: {profile['name']}\nPLATFORM: {profile['platform']}\n\n{asked}"
        f"DESCRIPTION:\n{profile['description'] or ''}\n\nWEBSITE:\n{website}"
    )
    return text[:max_chars]


def country_quote_to_check(row, profile):
    """The country quote when it is a sentence or an address, else None.

    The platform country, the feed location tag and the website's own domain describe the show itself.
    A sentence or address can describe someone else (hand check 2026-10-28: "Coach Kendal lives in
    Texas" on a show hosted by Bonnie; "Moscow is a city located in northern Idaho" in a true-crime
    show's description), so the LLM says whom it is about.
    """
    q = row.get("country_evidence") or ""
    if not q or q.startswith(("Website domain", "Feed location", "Channel country")):
        return None
    return q


def check_creator(conn, config, profile, country_quote=None):
    """Ask the LLM whether a creator runs the show. Returns (kind, quote, url, reason, about, tokens).

    The model's quote must appear word for word in the creator's own text; if it does not, the
    answer is "unverified" and the row is rejected, so the model cannot invent evidence. `about` says
    whom `country_quote` describes; that quote is the engine's own, so the model only judges it.
    """
    prompt = creator_prompt(profile, config["llm"]["max_input_chars"], country_quote)
    answer, tokens, was_cached = gemini_json(conn, config, CREATOR_SYSTEM, prompt, CREATOR_SCHEMA)
    tokens = 0 if was_cached else tokens  # only new calls use the free quota
    about = answer.get("country_quote_about") if country_quote else None
    quote_text = normalise(answer.get("quote"))
    sources = own_texts(profile)
    url = next((u for t, u in sources if len(quote_text) >= 10 and quote_text in normalise(t)), None)
    if url is None:
        return "unverified", answer.get("quote"), None, "model quote not found in the creator's text", about, tokens
    return answer["kind"], answer["quote"], url, answer.get("reason"), about, tokens


def apply_creator_check(conn, config, rows, profiles_by_id):
    """Run check_creator on rows that passed everything else; reject any that are not creators."""
    tokens_used, failures_in_a_row, calls = 0, 0, 0
    for row in rows:
        if row["candidate_status"] != "Qualified":
            continue  # the LLM is only asked about rows that would otherwise qualify
        if failures_in_a_row >= 2:  # the LLM is down or out of quota: stop asking, the next run retries
            kind, reason = None, "creator check not run (LLM unavailable)"
        else:
            try:
                prof = profiles_by_id[row["platform_id"]]
                country_q = country_quote_to_check(row, prof)
                kind, q, url, note, about, tokens = check_creator(conn, config, prof, country_q)
                failures_in_a_row, calls, tokens_used = 0, calls + 1, tokens_used + tokens
                row.update(creator_kind=kind, creator_evidence=q, creator_evidence_url=url, country_quote_about=about)
                reason = {
                    "creator": None,
                    "organisation": f"not a creator (LLM): {note}",
                    "unclear": "creator status unclear (LLM)",
                    "unverified": "creator check: model quote not found in the creator's text",
                }[kind]
                if reason is None and country_q and about != "host":
                    reason = (
                        "country not evidenced: the quote is about someone else, not the host (LLM)"
                        if about == "someone else"
                        else f"country not evidenced: the quote is not shown to be about the host (LLM: {about})"
                    )
            except ApiError as e:
                failures_in_a_row += 1
                kind, reason = None, f"creator check failed ({e.reason or e.status})"
                log.error("creator check %s: %s", row["platform_id"], e)
        if reason:
            row.update(candidate_status="Rejected", rejection_reason=reason, check_real_relevant=False)
    log.info("creator check: %d LLM answers, %d tokens used by uncached calls", calls, tokens_used)
    return tokens_used


def run(conn, config):
    profiles = pd.read_sql("SELECT * FROM profiles", conn)
    profiles = profiles.astype(object).where(profiles.notna(), None)
    items = pd.read_sql("SELECT * FROM content_items", conn)
    items = items.astype(object).where(items.notna(), None)
    items["published"] = pd.to_datetime(items["published_at"], utc=True, format="ISO8601")
    items = items.sort_values("published", ascending=False)
    by_creator = {pid: g.to_dict("records") for pid, g in items.groupby("platform_id")}

    profile_rows = profiles.to_dict("records")
    rows = [verify_profile(p, by_creator.get(p["platform_id"], []), config) for p in profile_rows]
    by_id = {p["platform_id"]: p for p in profile_rows}
    apply_size_check(conn, config, rows, by_id)  # before the LLM, so a show that is too big costs no LLM call
    apply_creator_check(conn, config, rows, by_id)
    verified = pd.DataFrame(rows, columns=VERIFIED_COLUMNS)
    verified.to_sql("verified", conn, if_exists="replace", index=False)

    rejected = verified[verified["candidate_status"] == "Rejected"]
    first_reasons = rejected["rejection_reason"].str.split(";").str[0].str.replace(r"\d+", "#", regex=True)
    log.info(
        "%d profiles: %d qualified, %d rejected; top first reasons: %s",
        len(verified),
        (verified["candidate_status"] == "Qualified").sum(),
        len(rejected),
        first_reasons.value_counts().head(6).to_dict(),
    )
    return verified
