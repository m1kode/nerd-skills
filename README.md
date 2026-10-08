# nerd-skills

Agent skills for going deep on the small stuff — the questions where the useful
answer is three layers below what the product page tells you.

Each skill is plain Markdown plus a small dependency-free Python script, so it
works in Claude Code as a plugin, as a loose skill folder, or with any other
agent that can read a file and run a shell command.

## Skills

### 🎵 `vinyl` — pressing quality before you buy

Shop listings tell you the price and show you the cover. They do not tell you
who pressed the record, whether anyone cut a lacquer for it, how many discs the
music is spread across, or whether the "limited edition" is anything more than a
colour. Those are the things that decide whether a record arrives flat and
sounds good.

Give it whatever you have:

```
/vinyl 190296611902                                    # barcode (EAN/UPC)
/vinyl https://www.discogs.com/release/24455669-...    # Discogs link
/vinyl https://any-record-shop.example/product/1234    # shop URL
/vinyl --search "daft punk discovery"                  # artist and title
```

You get back a table and a verdict:

```
**Daft Punk – Human After All**, CHF 29.50, barcode 190296611902

| Release         | Daft Life / ADA, Worldwide, 2022-09-09, Discogs 24455669 |
| Format          | 2× LP, gatefold, printed inner sleeves                   |
| Pressed by      | Record Industry, made in Netherlands                     |
| Cut / mastering | Lacquer cut at Translab / mastered at The Exchange       |
| Discogs rating  | 4.58 / 5 from 764 ratings, 6,926 copies owned            |
| Market          | 227 for sale, from $24.48                                |
```

…plus what actually matters in it: a named lacquer-cut credit means someone cut
a master for vinyl rather than stamping a CD master onto a record; two LPs for
one album means wider groove spacing; and translucent colour vinyl is *not* a
quality signal, whatever the hype sticker implies.

It reads [Discogs](https://www.discogs.com)' public API — no key, no account —
and will try to read a shop page for the barcode and price.

**On shop URLs:** many large retailers, Amazon above all, render product data
client-side behind bot protection and cannot be read by a script. The skill says
so plainly and falls back to asking for the barcode, which is the better input
anyway: a barcode identifies the pressing, and a shop listing usually does not.

More skills to follow.

## Install

### Claude Code — as a plugin

```
/plugin marketplace add m1kode/nerd-skills
/plugin install nerd-skills@nerd-skills
```

### Claude Code — as a loose skill

Clone the repo and symlink the skill you want into your skills directory:

```bash
git clone https://github.com/m1kode/nerd-skills.git ~/Projects/nerd-skills
ln -s ~/Projects/nerd-skills/skills/vinyl ~/.claude/skills/vinyl
```

Edits in the checkout take effect immediately, which makes this the better
option while you are changing things. Pick one or the other — installing the
plugin *and* symlinking gives you the skill twice.

### Other agents

See [AGENTS.md](AGENTS.md). The short version: point your agent at
`skills/vinyl/SKILL.md` and let it run the script.

### Standalone, no agent at all

The script is useful on its own if you can read JSON:

```bash
python3 skills/vinyl/scripts/vinyl_lookup.py 190296611902
```

## Requirements

Python 3.8+ and `curl`. No packages to install, no API keys.

## Licence

MIT — see [LICENSE](LICENSE).

Pressing data comes from Discogs contributors. If a record's credits are thin,
the fix is to [edit the release](https://support.discogs.com/hc/en-us/articles/360004042774)
rather than to assume the worst about the pressing.
