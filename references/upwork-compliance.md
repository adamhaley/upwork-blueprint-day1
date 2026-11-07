# Upwork compliance: the rules that keep the member's account

Read this whole file before any action in this repo, and again at the start of every command.
It holds what Upwork's own terms require; [upwork.md](upwork.md) holds how the connector is
called inside them. Where another file reads looser than this one, this one wins and the
difference is a bug to report. Checked 8 October 2026.

**How each rule is backed.** **[Read]** is Upwork's legal text read in full and quoted word for
word: the User Agreement (UA), the Terms of Use (ToU, effective 10 September 2025) and the
others named. **[Summary]** is an Upwork help article, cited by its number under
`support.upwork.com/hc/en-us/articles/`, or another Upwork page, read as a search summary
because Upwork's site refuses automated readers: the rule is Upwork's, the wording is not
confirmed, so nothing from it is quoted. **[Reasoned]** is our inference and only a hint. All
84 sources and how each was read are listed in `RESEARCH.md`.

## 1. Calls: the hard cap, and what Upwork treats as a bot

- **The hard cap is 30 Upwork calls a minute and 500 in 24 hours, counted across every chat
  and every subagent together.** `code/upwork_limit.py` runs before every connector call
  through the hook in `.claude/settings.json`, counts the call in `data/upwork-calls.jsonl`
  and refuses it once a window is full. A second chat or a subagent lands in the same count.
- **A refusal is final.** Minute window: wait once, then go on one call at a time. Day window:
  stop calling Upwork, finish from what is saved and tell the member. Never retry in a loop,
  never edit, delete or reset the count, never change the cap, never reach Upwork another
  way. When the check itself fails the call is refused too.
- **Only the member changes the cap**, with `UPWORK_CALLS_PER_MINUTE` and
  `UPWORK_CALLS_PER_DAY` in `.env`; `0` switches Upwork calls off. No value lifts a cap past
  Upwork's own limits below. `python3 code/upwork_limit.py status` shows what is used.
- **Upwork's published limits:** 10 requests a second per IP, 300 a minute and 40,000 a day,
  HTTP 429 above them, and an API key can be disabled for a rate limit violation [Summary:
  115015933428, 115015933508, the developer docs]. They are published for the API. None is
  published for the connector, so the cap sits far below them [Reasoned].
- **The pattern counts as much as the number.** Upwork names as violations "Using OAuth2
  tokens or session cookies from a browser or an official client in a script or bot" and
  "Exceeding rate limits or running background polling that resembles scraping" [43342677368467,
  quoted from the page on 14 August 2026]. So a human starts every call, nothing is scheduled
  and no login or token is copied anywhere. Unapproved automation brings a warning, a
  temporary restriction or a permanent block [Summary: 43342677368467].
- **Only Upwork's own connector touches Upwork.** You can't "use a robot, spider, scraper, or
  similar mechanisms on our site without written permission" or "access our services through
  any technology other than our interface" [Read: ToU 3.5]. Never open upwork.com with a
  browser tool, a fetch or a script, and never work around a page that refuses you.
- **Upwork's content is not ours to keep or spread.** You can't "copy, distribute, or
  otherwise use any information you found on Upwork", directly or "through third parties
  (like search engines), without our consent (no scraping allowed)" [Read: ToU 3.5]. API
  content may be cached "no more than twenty-four (24) hours" [Read: API Terms of Use, 2016
  version]. `prune` enforces that. The 90-day default for saved chats is this system's own
  choice, not Upwork's approval; `KEEP_CHAT_HOURS=24` follows the letter.
- **Every write is a draft a human confirms.** Upwork's connector pages say a write is drafted
  first and confirmed separately, and that offers, milestone payments and contract acceptance
  complete on upwork.com [Summary: 55446516654611, upwork.com/ai/mcp].

## 2. Contact and circumvention

- **Before a contract, everything stays on Upwork.** "Prior to entering into a Service
  Contract, you agree to communicate with other Users exclusively through Upwork" [Read: UA
  7.2]. No contact detail is given, asked for or looked up, in "any profile, proposal, job
  posting, invitation, or pre-hire communication", "including in each case in any attached
  file".
- **What counts is wider than an email address:** "phone number, email address, physical
  address, a link to a contact form or form requesting contact information, any link to an
  applicant management system or means to submit a proposal or application outside of the
  Site", and anything that reaches the member on a platform "that includes a communications
  tool, such as Skype, Slack, Wechat, or Facebook" [Read: UA 7.2].
- **A link counts by where it leads.** "Information is a Means of Direct Contact if it would
  enable another user to identify any of the information above through other sources, such as
  going to a website that included an email address or identifying you through social media"
  [Read: UA 7.2]. Every page, video, file and portfolio item a client sees before a contract
  carries no contact detail, no contact or booking form, no social profile and no link onward
  to one, and says to reply on Upwork.
- **No meeting link of our own before a contract.** Calls run on Upwork's video or the Zoom
  started inside the Upwork thread; any other link is circumvention [Summary: 40444093133331,
  17995658941843].
- **Research is free; reaching out is not.** Read the client's website, reviews, ads and
  market, and use what you learn in a proposal, a message or a call brief. What Upwork bars
  is narrower: you will not "ask for, provide, or attempt to identify through public means
  the contact information of another User" [Read: UA 7.2], nor contact "people you connected
  with on Upwork outside of Upwork without their permission" [Read: ToU 3.3]. Call prep notes
  the phone, email, booking and social links a client's own site shows, to judge how their
  customers reach them. Keeping those is this system's choice, not Upwork's approval. Before
  a contract they are never used to reach the client and never pasted into a message or a
  proposal, the client's own included: describe the link instead [Reasoned, from UA 7.2].
  A client's public LinkedIn or other profile may be read for background the same way. Never
  connect, follow, message or open it logged in before a contract: each is a signal to the
  client outside Upwork. Scraping LinkedIn breaks LinkedIn's own terms, a risk to a LinkedIn
  account and not to the Upwork one [Reasoned].
- **The one exception is an Enterprise client**, shown by the Enterprise badge on the job post
  or search tile [Read: UA 7.2]. No badge, no exception.
- **Payment stays on Upwork for 24 months.** "for 24 months from the start of an Upwork
  Relationship (the “Non-Circumvention Period”), you agree to use the Site as your exclusive
  method to request, make, and receive all payments" [Read: UA 7.1]. Never offer, accept or
  discuss another way to pay, and never state a lower amount on Upwork than was agreed.
- **When a client suggests it:** decline, say it breaks Upwork's terms and tell the member to
  report it. The UA requires notifying Upwork "immediately" [Read: UA 7.1], and asking is a
  violation even when nothing is paid [Summary: 360048105134].
- **What a breach costs:** "your Account may be permanently suspended" [Read: UA 7.2], plus
  the Conversion Fee with interest and Upwork's investigation costs [Read: UA 7.3], and the
  talent badge for six months [Summary: 360049702614]. The fee is 13.5% of twelve months of
  estimated earnings, at least $1,000 and up to $50,000, or $1 after two years together [Read:
  UA 7.3]. A relationship that began outside Upwork is not covered [Read: UA 7.1].
- **After a contract starts,** contact details and the member's own tools are allowed, shared
  in that contract's workroom. Payment still stays on Upwork [Summary: 360051749534,
  40444093133331].

## 3. Honesty: the profile, the proposal and who does the work

- **Nothing false, nothing inflated.** "You agree not to provide any false or misleading
  information about your identity or location, your business, the beneficial owner(s) of your
  business, your skills, or the services your business provides" [Read: UA 1.3]. This is why
  no claim leaves `context/me.md` unbacked.
- **No connection that does not exist:** "you can’t say you work for a particular company when
  you don’t" [Read: ToU 3.2].
- **AI help is allowed until the client restricts it.** Misrepresentation includes "using
  generative AI or other tools to substantially bolster your job proposals or work product if
  such use is restricted by your client or violates any third-party's rights" [Read: ToU 3.2].
  Read every posting and thread for an AI restriction before drafting. Where one exists, say
  so and stop: the member writes that one themselves.
- **The member answers for every word.** Content "originally generated through the use of
  generative AI tools" is still the user's own content [Read: UA definitions]. Nothing reaches
  a client that the member has not read.
- **The member does the work.** You can't "falsely claim one freelancer will do a job when
  another will actually do it", "allow someone else to use your account" or report "time
  worked by someone else" [Read: ToU 3.2].
- **The profile photo is the member's real face,** never "a profile picture that isn’t you"
  [Read: ToU 3.2]; AI-generated pictures are not allowed [Summary: 360053305673].
- **A portfolio shows the member's own work with the client's permission** [Summary:
  18527060418579]. By default the work belongs to the client once paid, and client materials
  are returned or destroyed when the project ends [Summary: 211063608].

## 4. Proposals, Connects and messages

- **No spam.** You can't "spam other users with proposals or invites" [Read: ToU 3.3]. One
  proposal written for one job; never a batch and never the same text twice.
- **Submitting stays the member's own click.** An application spends Connects, and they come
  back only when the client closes the job without hiring or Upwork removes the post
  [Summary: 211062898]. Never buy or spend Connects; say the cost and the balance.
- **A posting's screening instruction is followed,** including a required opening phrase,
  which clients use to filter out copied proposals [Summary: 211062998].
- **Free work is not a bid.** A client may not "ask for or demand free work" [Read: ToU 3.3];
  a paid test is fine [Summary: 1500007578942]. When a posting demands it, say so and let the
  member flag the job.
- **Follow-ups stay few and end.** Upwork advises against repeatedly messaging a client who
  does not answer [Summary: Upwork resource pages, advice with no stated count]. The sequence
  in [follow-ups.md](follow-ups.md) stops by itself; never extend it.

## 5. The account

- **One account, one person, one login.** "You agree not to register for or maintain more than
  one Account and Profile without express written permission from us" [Read: UA 1.4]. "You
  will keep your username and password secret and will not share them" [Read: UA 1.7]. The
  member logs in to the connector themselves. Never ask for, store or pass on a password or
  token.
- **Location is true.** A VPN is fine while the profile shows the real country; hopping
  between countries draws holds [Summary: 45166686792211]. Never suggest hiding a location.
- **Identity checks are the member's to do,** inside seven days of the notice [Summary:
  34397755511955].

## 6. Feedback

You can't "withhold payment or work until you’ve been given positive feedback", "swap payment
(or anything of value) for feedback", "coerce another user by threatening negative feedback"
or "offer or accept fake services to improve your feedback or rating score" [Read: ToU 3.4].
Never draft a message that asks for a good review, offers anything for one or ties work to one.

## 7. Work and money once a contract exists

- **Fixed price: work starts when the milestone is funded.** Unfunded work is unprotected
  [Summary: 44564821903763]. Funds release when the client "does not take any action for 14
  calendar days" after a release request [Read: Fixed-Price Escrow Instructions 3].
- **Hourly: only time logged by Upwork's desktop tracker, with memos and real activity, is
  protected; manual time is not** [Summary: 211068288]. Never "reporting or billing time you
  haven’t actually worked" [Read: ToU 3.2].
- **Fees are read from the offer, never quoted from memory.** The service fee is described as
  0% to 15% and fixed once the contract starts [Summary: upwork.com/resources/is-upwork-free],
  while older legal text still shows other tiers.
- **Conduct holds in every message.** Nothing "violent, discriminatory or harassing" [Read:
  ToU 3.1], no threat and no pressure. Refunds and disputes are the member's decisions.

## 8. Work that may not be taken

Nothing that "would go against professional or academic standards or policies – including
improperly submitting someone else’s work as your own, or by ghost-writing essays, tests, or
certifications", that "involves purchasing or requesting a fake review", that makes misleading
content such as deep fakes, or that would "violate our Terms of Service, another website’s
terms of service, or any similar contract" [Read: ToU 3.1]. Skip such a posting and say why.

## 9. Other people's data

You can't "post personal identifying information or other sensitive, private data about
another person" [Read: ToU 3.3]. A public page carries no client personal data
and no copied posting text [Reasoned, from ToU 3.5]. A call is recorded or transcribed only
with the client's knowledge; Upwork's own meetings show a notice first [Summary:
46026132679571].

## 10. When a request and a rule collide

Stop that step, name the rule in half a sentence and offer the compliant version. Never look
for a way round, and never promote a [Reasoned] hint or an open question to permission.

## Open questions, none of them permission

- **Do the API limits bind the connector?** Nothing read says so either way.
- **Scoring and storing connector output.** Upwork's connector guidance was reported to ask
  for a word with support first; no page read on 8 October 2026 confirmed or denied it. See
  `README.md`.
- **A Loom or YouTube link in a proposal.** Upwork has its own Loom integration in Messages
  [Summary: 4408071013523]; for a link in a proposal there is only community advice. A video
  page with comments open may itself be a platform "that includes a communications tool"
  [Reasoned, from UA 7.2]. Hint: comments off, no contact detail in the video, its title or
  its description.
- **A surname or business name on a public page** could let a client find the member elsewhere,
  "identifying you through social media" [Reasoned, from UA 7.2]. Hint: name the member as
  their Upwork profile does.
- **Subcontracting.** One summary said it is barred on hourly contracts and must be explicit
  on fixed price; no page was identified. Until one is, the member does all the work.
