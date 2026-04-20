# FlashMind — 3 Minute Demo Video Script

> Total runtime: ~3 minutes
> Format: screen recording with voiceover
> Prep: have the app open and logged in, have a PDF ready to upload (lecture notes or a textbook chapter work best)

---

## [0:00 – 0:15] Opening — Problem statement

**Say:**
> "Most students spend more time making flashcards than actually studying. I built FlashMind to fix that — you upload a PDF, AI generates your cards, and spaced repetition schedules your reviews. Let me show you."

**Screen:** Show the FlashMind landing page / login screen. App logo and tagline visible.

---

## [0:15 – 0:35] Upload a PDF

**Say:**
> "I'm going to upload a chapter from my notes. I just drop the file here."

**Screen:** [drag a PDF onto the upload card]

**Say:**
> "The app extracts text with pdfplumber, sends it to Groq's LLaMA 3.1 model, and gets back 10 flashcards as structured JSON. There's a 3-attempt retry chain in case the model returns malformed output — which it does sometimes."

**Screen:** Watch the "Processing your PDF" loader. Wait for success toast.

---

## [0:35 – 1:00] Show the generated deck

**Say:**
> "10 cards were generated in about 15 seconds. You can see the deck name, card count, and how many cards are due for review today."

**Screen:** [show the deck card in My Decks view] [hover to show 3D tilt effect]

**Say:**
> "The due count comes from SM-2 — the spaced repetition algorithm used by Anki. Each card has its own interval, ease factor, and next review date stored in MongoDB."

---

## [1:00 – 1:45] Study session — core demo

**Say:**
> "Let me start a study session."

**Screen:** [click Study button on the deck]

**Say:**
> "Each card flips to reveal the answer. I can press Space to flip, or click."

**Screen:** [click the card to flip it]

**Say:**
> "Now I rate my recall with one of three buttons. Again means I blanked — it resets the interval. Hard means I struggled — the interval grows slowly. Easy means I knew it cold — the interval multiplies by the ease factor."

**Screen:** [click Easy on the first card]

**Say:**
> "Here's the interesting part — if I hit Again on a card..."

**Screen:** [flip next card, click Again]

**Say:**
> "...that card doesn't disappear. It gets re-inserted 3 to 7 positions ahead in the current session queue. So it comes back before the session ends. That's the actual SM-2 re-queue behavior, not just a flag."

**Screen:** [continue through 2 more cards, show the "again pending" counter in the header]

---

## [1:45 – 2:10] Completion screen + stats

**Say:**
> "When the session is done..."

**Screen:** [finish the session quickly by clicking Easy several times, then show completion screen]

**Say:**
> "You get a summary — Easy, Hard, Again counts, and a score. The SM-2 state for each card has already been updated in MongoDB. Next time you open this deck, only the cards due today will be surfaced."

**Screen:** [click Stats in sidebar, show the bar chart and streak]

**Say:**
> "Stats show 30 days of history — cards reviewed per day, best streak, average score. This is your actual retention data, not a vanity counter."

---

## [2:10 – 2:35] Security and deployment

**Say:**
> "A few things worth calling out on the engineering side."

**Screen:** [stay on stats, no rapid switching needed]

**Say:**
> "Passwords are bcrypt-hashed. Sessions use an HttpOnly SameSite-Strict cookie signed with itsdangerous — no localStorage, no XSS attack surface. There's a per-IP login rate limiter and security headers on every response. The SECRET_KEY is a 64-char random hex stored in Railway's environment — there's no insecure fallback in code."

**Say:**
> "In production, ChromaDB and the sentence-transformers model are fully disabled via a single env flag — that keeps the Docker image under 200 megabytes instead of 5.8 gigabytes, which was the first deploy problem I had to solve."

---

## [2:35 – 3:00] Closing — mobile + Claude Code

**Say:**
> "It's fully mobile responsive."

**Screen:** [open browser dev tools, switch to mobile viewport (375px), show the deck list and then the study mode]

**Say:**
> "Sidebar becomes a drawer, study buttons scale for thumb taps, particles are disabled on mobile for performance."

**Screen:** [switch back to desktop]

**Say:**
> "This was built using Claude Code as an AI pair programmer — it flagged security issues, caught the SM-2 formula bug, reviewed the session cookie implementation, and helped me move fast without cutting corners. The GitHub repo has a full ARCHITECTURE.md and DEPLOYMENT.md if you want to dig into the implementation."

**Say:**
> "FlashMind. PDF to studied in 30 seconds."

**Screen:** [end on the home screen with a deck card visible]

---

## Key Talking Points Checklist

- [ ] SM-2 algorithm — mention interval, ease factor, next_review date in MongoDB
- [ ] 3-button system — Again/Hard/Easy map to quality 0/2/5
- [ ] Again re-queue — re-inserted 3–7 positions ahead, not just flagged
- [ ] 3-attempt LLM retry with escalating prompts
- [ ] Mobile responsive — particles disabled, sidebar drawer, thumb-tap buttons
- [ ] Security — bcrypt, signed cookie, rate limiting, no insecure defaults
- [ ] DISABLE_VECTOR_STORE — 5.8GB → 200MB image story
- [ ] Claude Code as building partner — Cuemath will appreciate this
- [ ] Mention GitHub repo has ARCHITECTURE.md and DEPLOYMENT.md

---

## Pre-Recording Checklist

- [ ] Log in on a fresh account (or clear study history so the stats look reasonable)
- [ ] Have a PDF ready — something with dense, informative text (textbook chapter, lecture notes)
- [ ] Test the upload once before recording so you know the timing
- [ ] Set browser to 1080p or 1440p, zoom to 100%, dark theme
- [ ] Mute Slack/notifications
- [ ] Record at 1.25x speaking speed if you tend to rush
- [ ] Keep total runtime to 2:45–3:15
