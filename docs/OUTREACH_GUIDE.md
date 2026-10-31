# Real outreach: step-by-step guide (for IncuBrix)

How IncuBrix's team takes the engine's leads and messages and contacts real creators. The plan behind every number here, with its reasons, is in [LAUNCH_KIT.md](LAUNCH_KIT.md).

**Who sends:** IncuBrix's own team, from IncuBrix's own domain and accounts. The engine finds, verifies and writes the messages. It never sends to a creator itself.

---

## What you work from

All files are in the engine's output folder (`output/` by default).

| File | What it is |
|---|---|
| `leads.csv` | every verified creator: name, country, the recent episode the message cites, the need, `best_channel` and `backup_channel` with the address or link, `priority` (A, B, C) and the first message |
| `outreach/sequences.csv` | every message to send: `lead_id`, `priority`, `creator_name`, `step` (`first`, `follow_up_1`, `follow_up_2`), `day`, `channel`, `send_mode`, `to`, `subject`, `message` |
| `outreach/A/`, `B/`, `C/` | one readable file per lead with all its messages |
| `outreach/templates.md` | the templates, including the follow-up wording to adapt for B and C leads |

---

## Step 1: Set up once (about 3 hours, before day 1)

| # | Task | Who | How |
|---|---|---|---|
| 1 | Buy a **separate outreach domain**, for example a variant of incubrix.com, and point its website to incubrix.com | Ops | any domain registrar |
| 2 | Create **2 mailboxes** on it under real team members' names | Ops | Google Workspace |
| 3 | Set up **SPF, DKIM and DMARC** on the domain, and add it to **Google Postmaster Tools** | Ops | the registrar's DNS settings |
| 4 | Pick **one team member's Instagram and LinkedIn** for hand messages. Use accounts that already have posts and connections | Growth | — |
| 5 | Make a **booking link** for 15-minute calls | Founder | Google Calendar or Calendly |
| 6 | Have **legal confirm the consent rules** per country (LAUNCH_KIT section 7). Until confirmed, contact UK and Irish sole traders by contact form, never cold email | Legal | — |
| 7 | Set up a **CRM** with these stages: Not contacted, Sent, Follow-up 1, Follow-up 2, Replied, Meeting, Not interested, Opted out. Also keep a **suppression list** for opt-outs | Growth | Google Sheets or HubSpot free CRM |

## Step 2: Put the real sender into the messages (15 minutes)

1. Open `config.yaml` and change the `sender` section to the real person who sends:
   ```yaml
   sender:
     name: Priya Sharma                    # the real sender's name
     description: growth lead at IncuBrix  # their role
     postal_address: "IncuBrix Private Limited, <street>, <city>, <PIN>, India"
   ```
   The postal address is required in commercial email. Keep the description a plain role. The message checks flag the phrases "IncuBrix team", "on behalf of IncuBrix" and "we work at IncuBrix", because they were written for the assessment, where the sender was not staff. To use those phrases, remove them from `EMPLOYEE_CLAIM` in `engine/draft.py`.
2. Check the product line, `draft.pitch`, and the call to action, `draft.call_to_action`, in the same file.
3. Regenerate every message with the new sender. This takes minutes, because everything else comes from the cache:
   ```bash
   python run.py --input data/seeds.csv --out output/
   ```
4. Open 3 or 4 files in `output/outreach/A/` and read them as a creator would.
5. Import `output/leads.csv` into the CRM, with every lead at the "Not contacted" stage.

## Step 3: Send, every working day

**Order:** all 25 Priority A leads first, then B, then C, each in order of `lead_score`, highest first.

**How to send each channel.** In `outreach/sequences.csv`, filter by `lead_id` and `step`. Each row has the `to` address or link, the `subject` (for email) and the `message`.

| Channel | How | Daily limit (week 1 / week 2 / weeks 3-4) |
|---|---|---|
| **Email** | from one of the 2 outreach mailboxes, or the CRM's email sequencing. One email per person, not a bulk send. Use the row's `subject` and `message` | 20 / 30 / 40 **per mailbox** |
| **Contact form** | open the `to` link, then paste the message into the creator's own form | 10 / 10 / 15 |
| **Instagram** | DM from the team member's account | 10 / 15 / 15 |
| **LinkedIn** | a connection note, or a message if you're already connected (notes are limited to 300 characters, and the messages fit) | 10 / 15 / 15 |
| **Podcast guest pitch** | the show's guest-pitch page; adapt the message to that show | 3 / 5 / 5 |

Only email may be sent from a tool. Contact forms, Instagram and LinkedIn are **always sent by a person, one at a time**, because those platforms forbid automated messages (`send_mode` = manual).

**Follow-ups:**

| Who | Day 4 | Day 9 |
|---|---|---|
| Priority A | follow-up 1, same channel (`step` = `follow_up_1`) | follow-up 2, **backup channel** (`step` = `follow_up_2`) |
| Priority B and C | one follow-up on the same channel, adapted from A follow-up 1 in `outreach/templates.md` | none |

Send a follow-up only if the creator has not replied.

**After every send:** move the lead to "Sent", "Follow-up 1" or "Follow-up 2" in the CRM, with the date.

## Step 4: Handle replies the same day

| The creator… | You… |
|---|---|
| is interested | reply with the booking link, and move them to "Replied", then "Meeting" |
| has a question | answer it, and move them to "Replied" |
| says "not now" | thank them, and move them to "Not interested". No more messages |
| says "no thanks" or asks to stop | move them to "Opted out", **add them to the suppression list**, and never contact them again on any channel |
| bounces (email) | mark the address bad, and try the backup channel only if it's a contact form or guest pitch |

On the call (15 minutes, Founder): ask about the creator's current workflow, then demo IncuBrix on one of their own episodes.

## Step 5: Watch the numbers

- **Tracking:** use the click and open tracking of the mailbox or CRM that sends the email (for example HubSpot's email tracking). Log every reply in the CRM. The engine's own click tracker (`seedtest.py clicks`) is for testing only.
- **Stop rules**, checked after the first 150 emails and then weekly:
  - bounces above **3%**: stop email, then run `--refresh` (step 6) to re-check addresses before sending again
  - replies below **1.5%**: pause B emails, then rewrite the opening around the other need, or try a shorter message
  - spam complaints above **0.1%** (Postmaster Tools): stop and lower the volume
- **Targets after 30 days:** all 25 A and all B/C leads contacted; replies of about 15% for A and 3% for B/C; about 1 meeting per 3 replies. Replace these assumptions with your measured rates every week.

## Step 6: Every Monday (30 minutes)

1. Refresh the leads. This re-checks every creator's evidence and contacts, and finds new creators:
   ```bash
   python run.py --refresh --input data/seeds.csv --out output/
   ```
2. In the CRM, import **only the `lead_id`s that are new**. A creator always keeps the same `lead_id`, so existing leads never come in twice.
3. Before sending to any new lead, check them against the suppression list.
4. Weekly review: replies and meetings by channel, priority and need. Move volume to what gets replies.

Setup, API keys and the full run command are in the [README](../README.md).

---

## Never

- Send in bulk from one tool to everyone, or go above the daily limits.
- Automate Instagram, LinkedIn or contact forms.
- Contact anyone on the suppression list, or anyone who opted out on any channel.
- Guess an email address. Use only the `to` value the engine found, which the creator published.
- Send without the real sender name and postal address filled in (step 2).
