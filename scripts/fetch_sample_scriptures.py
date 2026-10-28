"""Build data/scriptures.sample.jsonl from the World English Bible (public domain) via bible-api.com.

The passage text is retrieved, not typed, so it is exactly what the source publishes. Only whitespace
is normalised: the line breaks inside a passage become single spaces. The `themes` lines are hand-written
search metadata (see PASSAGES). They are embedded with the passage and never shown to users.

    python scripts/fetch_sample_scriptures.py data/scriptures.sample.jsonl

Standard library only. The files are written once every passage has been fetched successfully. Next to
the JSONL it also writes <name>.drivers.json, which maps each passage's source to the wizard driver it
mainly speaks to; scripts/measure_spread.py --intended uses it.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://bible-api.com/{reference}?translation=web"
BELIEF_SYSTEM = "Christianity"
TRANSLATION_LABEL = "WEB"
DELAY_SECONDS = 2.2  # bible-api.com allows 15 requests per 30 seconds
ATTEMPTS = 3

# Wizard Step 3 driver -> [(reference, themes)]. The grouping is the driver each passage mainly speaks to.
# It is written to a separate .drivers.json file for scripts/measure_spread.py and is not part of the
# scripture records.
#
# Themes are written the way a person would describe their situation: the feelings, needs and relationships
# the passage genuinely speaks to, using the wizard's own words (safety, worth, autonomy, belonging,
# gratitude, connection, purpose, abundance; family, friends, co-workers) where they honestly apply.
PASSAGES = {
    "Safety": [
        (
            "Psalm 34:18",
            "sadness, grief and a broken heart, feeling crushed or depressed, comfort and closeness when "
            "hurting, being rescued, safety in sorrow",
        ),
        (
            "Psalm 56:3",
            "fear and anxiety, feeling afraid or unsafe, choosing trust over fear, safety, courage when threatened",
        ),
        (
            "Isaiah 41:10",
            "fear and dismay, feeling weak and unsafe, being strengthened and helped, not facing it alone, "
            "safety and support",
        ),
        (
            "Psalm 46:1",
            "trouble and crisis, needing a refuge and shelter, safety and strength, help when overwhelmed",
        ),
        (
            "Psalm 23:4",
            "the darkest valley, fear of danger or death, depression, comfort and protection while suffering, "
            "safety, not walking alone",
        ),
        (
            "Psalm 27:1",
            "fear of other people, courage and confidence, safety and security, light in the darkness, strength, "
            "no need to be afraid",
        ),
        (
            "1 Peter 5:6-7",
            "worry and anxiety, heavy burdens and stress, handing your cares over, being cared for, "
            "safety and relief, humility",
        ),
    ],
    "Worth": [
        (
            "Psalm 147:3",
            "healing a broken heart, emotional wounds and hurt, sadness, being restored and bandaged up, "
            "worth and being cared for",
        ),
        (
            "Psalm 139:14",
            "self-worth and self-esteem, feeling worthless or not good enough, being wonderfully made, "
            "thankfulness for who you are",
        ),
        (
            "Luke 12:7",
            "worth and value, feeling unimportant or overlooked, being known and counted, "
            "you matter more than you think, fear of insignificance",
        ),
        (
            "Isaiah 43:4",
            "feeling unloved, rejected or worthless, being precious, honored and loved, worth, self-esteem",
        ),
        (
            "Zephaniah 3:17",
            "being loved and delighted in, worth, calm and quiet love, God present with you, joy sung over you, "
            "comfort for anxious or sad hearts",
        ),
        (
            "Matthew 11:28-30",
            "exhaustion and burnout, heavy burdens, depression and weariness, rest for the soul, gentleness, "
            "relief from pressure",
        ),
    ],
    "Autonomy": [
        (
            "Galatians 5:1",
            "freedom, feeling controlled, trapped or in bondage, autonomy, standing firm, "
            "not letting others control you",
        ),
        (
            "Proverbs 3:5-6",
            "making decisions, guidance when the path is unclear, uncertainty, trust, autonomy and choosing "
            "your direction",
        ),
        (
            "2 Timothy 1:7",
            "feeling powerless, overcoming fear, power and self-control, courage, autonomy, inner strength, "
            "boundaries",
        ),
        (
            "Romans 12:18",
            "peace with other people, doing your part, healthy boundaries, conflict with family, friends or "
            "co-workers, resentment and anger, autonomy",
        ),
        (
            "Proverbs 15:1",
            "anger and arguments, calming a conflict, gentle words, answering without rage, tension at home "
            "or work",
        ),
        (
            "James 1:19-20",
            "anger, listening before speaking, patience, self-control, conflict, learning to control your temper",
        ),
        (
            "Proverbs 14:29",
            "anger and a quick temper, patience, wisdom and self-control, staying calm",
        ),
    ],
    "Belonging": [
        (
            "Psalm 68:6",
            "loneliness, belonging, family, being given a home and community, isolation and feeling left out",
        ),
        (
            "Ecclesiastes 4:9-10",
            "loneliness and isolation, friendship and companionship, someone to lift you up when you fall, "
            "belonging, not facing it alone, working together with friends or co-workers",
        ),
        (
            "Proverbs 17:17",
            "friendship, loyalty in hard times, friends and siblings who stand by you, belonging, family support",
        ),
        (
            "Hebrews 13:5",
            "fear of being abandoned or left behind, contentment with what you have, never forsaken, belonging, "
            "not being alone",
        ),
        (
            "Psalm 27:10",
            "abandonment or rejection by parents and family, estranged family, belonging, being taken in and "
            "cared for",
        ),
        (
            "John 14:18",
            "feeling orphaned or abandoned, loneliness, belonging, not being left alone, loss of family",
        ),
        (
            "Romans 8:38-39",
            "nothing can separate you from love, belonging and security, feeling cut off or rejected, "
            "fear of death or loss",
        ),
    ],
    "Gratitude": [
        (
            "1 Thessalonians 5:16-18",
            "gratitude and thankfulness, joy, rejoicing always, giving thanks in every situation, prayer, happiness",
        ),
        (
            "Psalm 118:24",
            "joy in today, gladness, gratitude for this day, celebrating, happiness",
        ),
        (
            "Psalm 136:1",
            "thankfulness for goodness and lasting kindness, gratitude, praise, happiness",
        ),
    ],
    "Connection": [
        (
            "1 John 4:7",
            "love for one another, connection with family, friends and neighbors, loving relationships, "
            "happiness in community",
        ),
        (
            "Psalm 133:1",
            "unity and harmony, family and friends living together in peace, connection, happiness in togetherness",
        ),
        (
            "Romans 12:15",
            "empathy, sharing in other people's joy and sorrow, connection with friends and family, "
            "so that no one weeps alone, compassion",
        ),
        (
            "Proverbs 27:17",
            "friendship that makes you better, encouraging each other, connection with friends and co-workers, "
            "learning from one another, growth",
        ),
    ],
    "Purpose": [
        (
            "Jeremiah 29:11",
            "hope for the future, purpose and plans, feeling lost or unsure what comes next, peace, "
            "discouragement and depression",
        ),
        (
            "Ephesians 2:10",
            "purpose and calling, being made for a reason, meaningful work, doing good, worth",
        ),
        (
            "Colossians 3:23-24",
            "purpose in daily work, co-workers and bosses, working wholeheartedly, finding meaning in your job, "
            "resentment at work, reward for faithful effort",
        ),
        (
            "Proverbs 19:21",
            "plans and purpose, uncertainty about the future, trusting a bigger plan, humility, guidance",
        ),
    ],
    "Abundance": [
        (
            "John 10:10",
            "abundant life, fullness of life, flourishing, being protected from what steals joy, abundance",
        ),
        (
            "Philippians 4:19",
            "provision, having enough, needs being met, financial worry, abundance, trust that you will be supplied",
        ),
        (
            "Psalm 23:1",
            "lacking nothing, contentment, being guided and provided for, abundance, trust, peace and security",
        ),
        (
            "2 Corinthians 9:8",
            "abundance, sufficiency, having enough to give generously, generosity, grace overflowing, doing good",
        ),
    ],
}


def fetch(reference: str) -> dict:
    url = URL.format(reference=urllib.parse.quote(reference, safe=":-"))
    request = urllib.request.Request(url, headers={"User-Agent": "spiritroute-sample-builder"})
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.load(response)
            break
        except urllib.error.URLError as exc:  # includes HTTP errors such as 429 and dropped connections
            if attempt == ATTEMPTS:
                raise
            print(f"retrying {reference} after {exc}", file=sys.stderr)
            time.sleep(5 * attempt)
    if data.get("translation_id") != "web" or not data.get("text", "").strip():
        raise ValueError(f"unexpected response for {reference!r}: {data}")
    return data


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    wanted = [(driver, reference, themes) for driver, group in PASSAGES.items() for reference, themes in group]
    records = []
    intended = {}
    for index, (driver, reference, themes) in enumerate(wanted):
        if index:
            time.sleep(DELAY_SECONDS)
        data = fetch(reference)
        canonical = data["reference"]
        source_book = f"{canonical} ({TRANSLATION_LABEL})"
        intended[source_book] = driver
        records.append(
            {
                "id": "bible-" + re.sub(r"[^a-z0-9]+", "-", canonical.lower()).strip("-"),
                "belief_system": BELIEF_SYSTEM,
                "source_book": source_book,
                "content": " ".join(data["text"].split()),
                "themes": themes,
            }
        )
        print(f"fetched {canonical}", file=sys.stderr)
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    drivers_out = out.with_suffix(".drivers.json")
    drivers_out.write_text(json.dumps(intended, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} records to {out} and their intended drivers to {drivers_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
