---
name: vinyl
description: Judge the pressing quality of a vinyl record before buying it, from a barcode (EAN/UPC), a Discogs link, a shop URL, or just an artist and title. Pulls the pressing plant, lacquer-cut and mastering credits, disc count, gram weight, colour, owner ratings and worldwide marketplace prices from Discogs, then renders a comparison table and a buy/skip verdict. Use this whenever the user mentions a record, an LP, vinyl, a Schallplatte, a pressing, a reissue, a repress, or an album barcode, or asks whether a record is worth buying, why one pressing sounds or feels better than another, which edition to pick, or what the difference between two editions is - including when they just paste a shop link or a bare number with no other context.
---

# Vinyl pressing lookup

The question behind every invocation is "is this specific pressing any good, and
should I buy it?" Price and cover art are visible on any shop page; what is not
visible is who pressed the record, whether anyone cut a lacquer for it, how many
discs the music is spread over, and whether it will arrive flat. That is what
this skill surfaces.

## Workflow

Run the lookup, then read the JSON and reason about it. Everything it uses is a
public endpoint with no API key, so there is nothing to configure.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/vinyl/scripts/vinyl_lookup.py" <input>
```

If `${CLAUDE_PLUGIN_ROOT}` is not set, the script sits beside this file at
`scripts/vinyl_lookup.py`.

It accepts whatever the user has to hand:

| Input | Example |
|---|---|
| Barcode (EAN/UPC) | `190296611902` |
| Discogs release URL or id | `https://www.discogs.com/release/24455669-...` |
| Any shop product URL | `--shop https://www.example-records.com/...` or as the bare argument |
| Artist and title | `--search "daft punk discovery"` |

A shop URL is read for the barcode and the price, then the barcode drives
everything else. If the shop returns `blocked` or `no_data`, the page defeated
a scripted fetch - **Amazon always does this**, as do many large retailers,
because their product data is rendered client-side behind bot protection. Do not
fight it. Either read the page with your own web-fetch tool, or ask the user for
the barcode printed next to the sleeve's spine. The barcode is the better input
anyway: it identifies the pressing, which a shop listing often does not.

### Pick the right pressing, and say which one you picked

One barcode routinely covers several pressings - the US and the European run of
the same reissue, a later repress from a different plant, sometimes the CD. They
can differ substantially in quality. The script returns up to five, vinyl first,
most-owned first.

Pick the one the user would actually receive, using where they are buying from:
a European shop means `Europe`, `EU`, `UK`, `Germany` or `Worldwide`; a US shop
means `US` or `USA & Canada`. Lead with that one, name its Discogs release id,
and mention the siblings in a line when they differ in a way that matters ("the
same barcode also covers a 2023 Pallas-pressed run"). When you genuinely cannot
tell which one ships - labels reuse barcodes across decades - say so, lead with
the most likely, and note that the credits may belong to a different run.

If you do not know where the user is buying, ask only when the pressings
actually differ in quality. If they are all the same plant and cut, it does not
matter and the question is noise.

## Output format

Open with the record and what it costs, then this table. Drop rows the data does
not cover rather than filling them with "unknown".

```
**<Artist> - <Title>**, <price if known>, barcode <barcode>

| | |
|---|---|
| Release      | <label> / <catalogue>, <country>, <release date>, Discogs <release id> |
| Format       | <N>x LP, <colour>, <weight if stated>, <gatefold / single sleeve> |
| Pressed by   | <plant>, made in <country> |
| Cut / mastering | <lacquer cut at> / <mastered at> |
| Discogs rating | <avg> / 5 from <n> ratings, <have> copies owned |
| Market       | <num_for_sale> for sale, from $<lowest_price_usd> |
```

Then a short verdict in bold, three or four bullets on what is in its favour,
and the honest caveats. Close with source links (the shop page, the Discogs
release).

Keep the prose tight. The table carries the facts; the bullets explain which of
them the user will actually notice, and why.

The `lowest_price_usd` and `num_for_sale` figures are the Discogs marketplace,
which is worldwide secondhand plus some dealers. They are always USD - the
anonymous API ignores the currency parameter - so label them as dollars. They
are most useful as a sanity check on the shop's price and as a signal of how
easy the record is to find.

## Reading the signals

`references/pressing-quality.md` holds the plant reputations, the green and red
flags, and the reasoning behind each. Read it before writing the verdict - the
judgement calls live there, and answering from memory produces confident wrong
claims about specific plants.

The two things worth internalising now:

**A lacquer-cut credit is the single most informative field.** A reissue with a
named cutting room had someone cut a master specifically for vinyl. A reissue
without one is usually a CD master stamped onto a record, which is where the
loudness-war flatness comes from. Absence on Discogs is weaker evidence than
presence - contributors fill these in unevenly - so phrase it as "no cut credit
listed", not "it was never cut properly".

**Transparency and colour are not quality.** Black vinyl contains carbon black;
colour and splatter use dye instead, so they are translucent by nature. Carbon
black also makes for a slightly quieter surface, so if anything colour is the
compromise. If the user treats translucency as a good sign, correct it gently -
it is one of the most common misreadings, and it leads people to buy worse
records.

## Being honest about the gaps

Discogs is a volunteer database and most shops' spec tables are close to useless
for records. A missing gram weight means nobody typed it in, not that the record
is lightweight - though standard weight (~140 g) is the safe assumption when a
"limited" or "audiophile" edition does not advertise 180 g.

Separate what the data says from what you are inferring. "Pressed by GZ Media"
is a fact; "likely to arrive flat" is a judgement, and the user is better served
by seeing which is which. Warps in particular are a handling and storage story
rather than a plant story, so resist blaming the pressing plant when the record's
route to the buyer is the more likely culprit.
