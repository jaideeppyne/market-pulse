# Smart-Money Registry Review

Scope: `app/engine/smart_money_intel.py` regex registry + `data/smart_money_extra.txt`.
This is a review/finding note only — no app code changed.

## How matching works today

`analyze_smart_money(titles)` scans the last 40 headlines against a `REGISTRY`
of compiled regexes (India legends, US legends, US/India politicians, foreign-India
funds, plus a file-loaded extras block). A headline matches an entry when:

1. `entry["pattern"]` matches the title, AND
2. the non-equity guard passes (see below), AND
3. if `require_buy` is `True` (default), `BUY_CONTEXT` also matches.

## False-positive risks

1. **Bare surnames are very broad.** Several patterns match a lone common surname:
   `kacholia`, `kedia`, `jhunjhunwala`, `damani`, `khanna`, `icahn`, `burry`,
   `pelosi`, `coatue`, `blackrock`, `vanguard`. A `require_buy=True` gate helps,
   but `BUY_CONTEXT` itself is loose — it fires on generic words like
   `portfolio`, `stake`, `insider`, `13f`, `entry`. So a market-wrap headline
   such as *"Damani's portfolio in focus this quarter"* will match
   `radhakishan_damani` even though nobody bought anything. The unit tests
   (`test_engine_smart_money.py`) cover the apartment/villa guard and the
   "no buy verb" guard, but this `portfolio`-style soft match is a live risk.

2. **`entry`/`entry` as a buy word.** `BUY_CONTEXT` includes `enters?|entry`.
   Headlines like *"Buffett enters the debate on AI"* combine a legend name with
   `enters` and would pass the buy gate. The non-equity guard only blocks
   property words, not generic non-equity contexts.

3. **Single-token fund/issuer names.** `blackrock`, `vanguard`, `fidelity`,
   `coatue`, `softbank` appear constantly in market news unrelated to a specific
   buy. With the loose buy context these will over-fire and inflate the S+
   `smart_money_*` factor, which carries the highest tier multiplier (6.5x) — so
   a false positive here distorts rankings the most.

4. **Politician/relative regex is positional and brittle.**
   `(son|daughter|wife|...)\s+of\s+(mp|minister|mla).* (buy|stake|share)` has a
   literal space before `(buy...)` and depends on word order; it will miss most
   real phrasings and occasionally match unrelated family-of-politician stories.

5. **The non-equity guard is allow-list-bypassed.** `_title_matches` suppresses a
   property purchase UNLESS the title also contains `stake|shares|equity|holding|
   position|bulk deal|block deal|13f|form 4|insider`. Because `shares` is such a
   common word, *"Buffett shares his thoughts after buying a villa"* slips the
   guard (`shares` present) and would match. The guard catches the simple cases
   the tests assert, but not mixed ones.

## Hardcoded vs data/*.txt overrides

`data/smart_money_extra.txt` already supports `kind|regex|Display Name` lines, all
forced to tier **S+**, and they are merged into `REGISTRY` at import. So the
*mechanism* for externalizing the registry exists, but the bulk of names
(INDIA_LEGENDS, US_LEGENDS, POLITICIANS_*, FOREIGN_INDIA) is still hardcoded with
rich `quality` strings the extras file can't express.

**Recommendation (for the app owner — not done here):**

- Move the full registry to `data/smart_money.json` (id, name, rx, kind, tier,
  quality, require_buy) and keep the Python file as the loader/validator. This
  lets the curated list be edited without code deploys and lets the extras file
  set tiers other than S+.
- Tighten the highest-risk patterns: require a full name or a fund-specific token
  (e.g. `berkshire`, `pershing square`, `scion asset`) rather than a bare surname
  for the S+ tier, since S+ has the biggest scoring impact.
- Narrow `BUY_CONTEXT`: drop `portfolio` and standalone `entry`, and require the
  buy verb to co-occur near the name rather than anywhere in the headline.
- Add a `data/smart_money_blocklist.txt` of phrases that should veto a match
  (e.g. "shares his views", "in focus", "to speak at").

## Net assessment

The guards that exist are reasonable and now test-covered, but the registry leans
on bare-surname regexes feeding the single highest-weight tier, which is the worst
place for false positives. The data-file mechanism is half-built; finishing the
move to a data-driven registry plus tightening the S+ patterns would meaningfully
reduce false-positive ranking corruption.
