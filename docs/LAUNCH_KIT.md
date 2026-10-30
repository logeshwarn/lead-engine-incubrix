# IncuBrix creator outreach: 30-day launch kit

One plan IncuBrix can start on a Monday. It uses the files the engine writes (`leads.csv`, `outreach/`, `run_report.md`) and needs no code changes.

Numbers marked **[final run]** come from the final `run_report.md` and are filled in once that run finishes. Rates marked **assumption** are planning numbers with the reasoning shown. They are not measurements: week 1 replaces them with real numbers (see "Measure and adjust").

## 1. Who we target first

- **Who:** independent English-language podcasters and video podcasters. Their content is the long recordings that IncuBrix's editing, captions and repurposing work on.
- **Where:** the United States, United Kingdom, Canada, Australia, New Zealand, Ireland and Singapore. No country is above 60% of the list.
- **Active:** they published 8 or more items in the last 30 days, or 2 or more long-form items in the last 60.
- **Earning:** each has a public sign of income (services, sponsors, membership, a course, products or affiliate links), with a link to it.
- **A gap we can name:** most have no transcript on any recent episode (917 of the 1,083 leads). Most of the rest post long episodes with no short clips (141); a few say so themselves (15) or post irregularly (10). The message quotes that gap and links the episode.
- **Size:** small to mid-sized. Where a show links a YouTube channel, it is at most 250,000 subscribers. Large networks, broadcasters, agencies and brands are rejected.
- **First in line:** the 25 **Priority A** leads (highest score: biggest need, most active, clear income, reachable). Each has a personalised first message and 2 follow-ups ready in `outreach/A/`. Next come the 1,056 Priority B leads, then the 2 C leads.

## 2. Channels and why

| Channel | Role | Why |
|---|---|---|
| **Email** | best channel for 973 of the 1,083 leads | The address is the one the creator publishes for their show (podcast feed or own website), so it reaches the owner and is meant for business contact. It is also the only channel that can be tracked and sent at volume safely. |
| **Contact form** | best channel when no email is published (105 leads); the most common backup (645) | It is on the creator's own site, and the creator chose it as the way to be contacted. It is sent by hand. |
| **Instagram DM** | backup (203) | Only the creator's own profile, linked from their show or site. Sent by hand from a real team account; Instagram does not allow automated DMs. |
| **LinkedIn** | backup (173), mainly expert-led creators | A connection note of 300 characters or less, by hand. LinkedIn does not allow automation tools. |
| **Podcast guest pitch** | best channel for 5 leads, backup for 25 | The show's own "be a guest" page. Use it only for a genuine guest offer (an IncuBrix founder talking about content workflows), never as a disguised sales message. |

Each lead's `best_channel` and `backup_channel` in `leads.csv` were chosen by the engine from that creator's own published contacts, with an evidence URL for each. Counts are from the final run's `run_report.md` (29 Oct, 1,083 leads); X (15) and TikTok (4) are rare backups.

## 3. Safe daily volume per channel

These limits cover first messages and follow-ups together. Stay below them even when replies are good.

| Channel | Week 1 | Week 2 | Weeks 3-4 | Basis |
|---|---|---|---|---|
| Email, per mailbox (2 mailboxes) | 20 a day | 30 a day | 40 a day | A new sending domain has no reputation yet. Raise the volume only while bounces stay under 2% and nobody marks the mail as spam. Google's sender guidelines ask senders to keep the spam rate under 0.3%; aim for 0.1%. |
| Contact form (by hand) | 10 a day | 10 a day | 15 a day | Each form takes about 3 minutes and some forms use CAPTCHAs, so these are filled in by a person. |
| Instagram DM (by hand) | 10 a day | 15 a day | 15 a day | A warmed-up account that already has posts. Instagram publishes no fixed limit, so stay well under what triggers its "try again later" blocks. |
| LinkedIn note (by hand) | 10 a day | 15 a day | 15 a day | LinkedIn limits invitations per week. 15 a day on 5 days stays under the commonly reported weekly ceiling. |
| Guest pitch (by hand) | 3 a day | 5 a day | 5 a day | Each pitch is written for that show. |

Maximum email sends in 30 days with 2 mailboxes (5 working days a week): 200 + 300 + 400 + 400 = **1,300**. The final run has 973 leads whose best channel is email (25 A, 948 B), so that covers a first email to every one of them, with 327 sends left for follow-ups. B and C follow-ups that don't fit go to month 2.

## 4. Step-by-step plan

### Before Monday (day 0, about 3 hours)

| Step | Owner | Tool |
|---|---|---|
| Buy a separate outreach domain (for example a variant of incubrix.com), so cold email never puts the main domain's reputation at risk | Ops | domain registrar |
| Create 2 mailboxes on it under real team members' names. Set up SPF, DKIM and DMARC, and point the domain's website to incubrix.com | Ops | Google Workspace |
| Fill in the postal address in `config.yaml` (`sender.postal_address`) and set the sender name and role to the real sender (`sender.name`, `sender.description`). Rerun `python run.py --input data/seeds.csv --out output/` to regenerate every message (minutes, from the cache) | Engineer | engine |
| Approve the product line (`draft.pitch`) and the call to action. Legal/ops confirms the consent rules in section 7 for each country | Founder, Legal/ops | `config.yaml` |
| Import `leads.csv` into the CRM, with one stage column: Not contacted, Sent, Follow-up 1, Follow-up 2, Replied, Meeting, Not interested, Opted out | Growth | Google Sheets or HubSpot free CRM |
| Create a booking link for 15-minute calls | Founder | Google Calendar or Calendly |
| Register the domain in Google Postmaster Tools | Ops | Postmaster Tools |

### Week 1 (Monday to Friday): Priority A, by hand

| Day | Action | Owner | Volume |
|---|---|---|---|
| Mon | A person reads all 25 Priority A sequences in `outreach/A/`, checks every link still works, and edits anything that reads oddly | Growth | 25 leads |
| Mon-Tue | Send the 25 A first messages on each lead's `best_channel` | Growth | 13 + 12 |
| Tue-Fri | Start Priority B: first messages by email, best scores first | Growth | 20-40 a day (section 3) |
| Daily, 30 min | Log every send and reply in the CRM. Reply to every answer the same day. Add opt-outs to the suppression list and never contact them again | Growth | all |
| Fri | A follow-up 1 is due (day 4, same channel). Count bounces, replies and opt-outs | Growth | 25 |

### Weeks 2-4

| When | Action | Owner |
|---|---|---|
| Week 2, Mon | A follow-up 2 (day 9) goes out on the backup channel: contact form, Instagram, LinkedIn or guest pitch, by hand | Growth |
| Weeks 2-4, daily | B first messages, then C, best scores first, within the volume in section 3. Send a B follow-up on day 4, adapted from A follow-up 1 in `outreach/templates.md`, to anyone who has not replied | Growth |
| Every Monday | `python run.py --refresh --input data/seeds.csv --out output/` re-checks each creator's evidence and contacts and finds new creators. The same creator always keeps the same `lead_id`, so the CRM gets no duplicates. Load only new `lead_id`s into the CRM | Engineer (30 min) |
| Every Monday | Weekly review: replies and meetings by channel, priority and need (captions or repurposing). Shift volume to what works | Growth, Founder |
| Calls | 15-minute call: the creator's current workflow, then a demo on one of their own episodes | Founder |

### Measure and adjust

- After the first **150 emails**:
  - If more than 3% bounce, stop. Re-check the addresses with `--refresh` before sending again.
  - If fewer than 1.5% get a reply, pause B sends and rewrite the opening around the other need, or test a shorter message.
- Replace the reply and meeting assumptions in section 6 with the measured rates every Monday. That gives the evidence for where these creators actually respond.

## 5. Tools and monthly cost

| Tool | Used for | Monthly cost |
|---|---|---|
| Lead engine (Python; Podcast Index, YouTube Data API and Apple/iTunes APIs on free quotas; Gemini and Groq free tiers) | finding, checking, scoring, routing, drafting and refreshing | $0. Creator checks: 2,124 AI answers in the final run (1,670,970 Gemini tokens from new calls), every other call from the cache (`run_report.md`) |
| Outreach domain | separate sending reputation | about $1 (about $12 a year at most registrars) |
| Google Workspace Business Starter, 2 mailboxes | sending and replies; Calendar booking | about $14-17 (Google's list price per user; confirm when buying) |
| Google Sheets, or HubSpot free CRM | pipeline | $0 |
| Google Postmaster Tools | spam rate and domain reputation | $0 |
| Instagram, LinkedIn | backup channels, by hand from team members' existing accounts | $0 |
| **Total** | | **about $15-18 a month** |

No paid sequencing tool is needed at 40 emails a day per mailbox: a person can send that from the CRM in about an hour. If IncuBrix later wants automated sending, add one in month 2, after the domain has a reputation.

## 6. Targets after 30 days

| Measure | Target | Reasoning |
|---|---|---|
| Leads contacted (first message) | all 25 A + all 1,058 B/C (948 by email, 105 by contact form, 5 by guest pitch), within the section 3 limits | Volume is capped by safe sending, not by leads |
| Bounce rate | under 2% | Addresses come from the creator's own feed or site and are re-checked weekly |
| Spam complaints | under 0.1% | Own-contact addresses, a real reference to their work, a clear opt-out |
| Reply rate, Priority A | **assumption: 15%** (about 4 of 25) | Three touches on two channels, each naming a real recent episode and a measured gap |
| Reply rate, B and C | **assumption: 3%** | Templated messages, cold, from an unknown sender with no social proof yet |
| Meetings | **assumption: 1 in 3 replies**, so about 12 (about 4 A replies + about 32 B/C replies = 36 replies) | Many replies will be "not now" or questions; a 15-minute call is a small ask |
| Measured rates per channel | in the CRM by day 30 | This replaces the assumptions above for month 2 |

## 7. Biggest risk and how to handle it

**The biggest risk is that cold email hurts deliverability or breaks consent rules, so the channel that carries most of the leads stops working.**

- **Deliverability:**
  - Send from a separate domain, with SPF, DKIM and DMARC set up.
  - Keep to the volume in section 3, and use only the creator's own published business contact (the engine never guesses addresses).
  - Watch the spam rate in Postmaster Tools.
  - Stop if bounces go above 3%.
- **Consent rules differ by country.** Legal/ops confirms these before day 1:
  - United States (CAN-SPAM): a real postal address, a clear opt-out, and opt-outs honoured within 10 business days.
  - Canada (CASL) and Australia (Spam Act): an address the creator has published for business may give implied or inferred consent, as long as the message is about their business role.
  - United Kingdom and Ireland (PECR / ePrivacy): many podcasters are sole traders, who count as individuals, so cold marketing email to them may need consent. Contact UK and Irish sole traders through their contact form or a guest pitch until this is confirmed.
- **Platform rules:** Instagram and LinkedIn messages are sent by a person, never by a bot, within the volume in section 3.
- **Data going stale:** evidence older than 30 days is re-checked by the Monday refresh. Every row carries its `checked_date`.

## 8. What IncuBrix must provide

| Item | Why |
|---|---|
| An outreach domain and 2 Google Workspace mailboxes, under named team members | Sending and replies |
| IncuBrix's postal address | Required in commercial email (CAN-SPAM) |
| The sender's name and role, and approval of the product line and call to action | Messages must say who is writing and must not overclaim |
| A legal or ops sign-off on the consent rules in section 7 | Before the first UK, Irish or Canadian email |
| One team member's Instagram and LinkedIn accounts, used by hand | Backup channels |
| A founder's booking link and about 2 hours a week for calls | Meetings |
| Growth owner time: about 1.5 hours a day | Sending, the CRM and same-day replies |
| An engineer, 30 minutes a week, plus API keys in `.env` (YouTube Data API, Podcast Index, Gemini) | The weekly refresh |
| Budget: about $15-18 a month | Section 5 |
