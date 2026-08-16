"""Canopy demo blog catalogue (PR 3, spec §3–§4).

Data only — no Django imports, so the catalogue is importable settings-free.
Consumed by management/commands/seed_demo_blog.py. Post bodies are final,
authored copy: reading_time auto-computes from these at save() (~200 wpm),
so their length is the honesty contract for the "N min read" meta line.

blocks tuple shapes (proven by the retired create_demo_blog_posts command):
("heading", str) · ("paragraph", "<p>html</p>") ·
("quote", {"quote_text": str, "attribution": str})
"""

CATEGORIES = [
    {
        "name": "Care",
        "slug": "care",
        "description": "Watering, light, and the daily habits that keep plants alive.",
    },
    {
        "name": "Propagation",
        "slug": "propagation",
        "description": "Cuttings, divisions, and making more plants from the ones you have.",
    },
    {
        "name": "Pests & diseases",
        "slug": "pests-diseases",
        "description": "Spotting trouble early and treating it without panic.",
    },
    {
        "name": "Design",
        "slug": "design",
        "description": "Shaping plants and spaces — pruning, styling, and small-space jungles.",
    },
]

# username -> (first_name, last_name). MUST equal the ForumProfile
# display_name cast split (spec §5: the same person never appears under two
# names across forum and blog). Applied fill-if-blank only.
AUTHOR_NAMES = {
    "june_park": ("June", "Park"),
    "iris_delgado": ("Iris", "Delgado"),
    "sam_whitaker": ("Sam", "Whitaker"),
    "theo_brandt": ("Theo", "Brandt"),
}

POSTS = [
    {
        # The hero's "This month" feature (spec §4 #1) — newest post,
        # "Read the latest" CTA target.
        "slug": "killed-by-kindness",
        "title": "Killed by kindness",
        "category": "care",
        "author": "june_park",
        "age_days": 3,
        "view_count": 340,
        "cover": "cover-kindness.webp",
        "introduction": (
            "<p>Most houseplants don't die of neglect. They die of attention — "
            "specifically, the watering can. Here's what actually happens below "
            "the soil line, and the one habit that prevents it.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>When a plant looks unhappy, the instinct is to do something, "
                "and the easiest something is water. So the droopy pothos gets a "
                "drink, and the yellowing philodendron gets a drink, and a week "
                "later both look worse, so they get another. In the clinic side "
                "of this community, the pattern behind dead houseplants is "
                "overwhelmingly this one: kindness, applied weekly, until the "
                "roots drown.</p>",
            ),
            ("heading", "What overwatering actually is"),
            (
                "paragraph",
                "<p>Overwatering isn't about the amount you pour — it's about "
                "oxygen. Roots respire. In soil that never dries, the air "
                "pockets stay flooded, the roots suffocate, and opportunistic "
                "fungi like <i>Pythium</i> and <i>Phytophthora</i> move into "
                "the dying tissue. That's root rot: not a disease your plant "
                "caught, but a condition you scheduled.</p>",
            ),
            (
                "paragraph",
                "<p>The cruel part is the symptom. A plant with rotting roots "
                "can't move water, so it wilts — and a wilting plant looks "
                "thirsty. If you answer the wilt with more water, you complete "
                'the loop. This is why "how often should I water?" is the '
                "wrong question. The calendar doesn't know what your soil is "
                "doing.</p>",
            ),
            (
                "quote",
                {
                    "quote_text": (
                        "The plant isn't thirsty on Tuesdays. It's thirsty "
                        "when the soil is dry — and only then."
                    ),
                    "attribution": "Every pathologist, eventually",
                },
            ),
            ("heading", "The one habit that fixes it"),
            (
                "paragraph",
                "<p>Check, then water. Push a finger two knuckles into the "
                "soil, or lift the pot and learn its dry weight. If the top "
                "few centimetres are damp, walk away — whatever the schedule "
                "says. Most common houseplants (pothos, monstera, snake "
                "plants, ZZs) would rather sit slightly dry for a week than "
                "sit wet for a day.</p>",
            ),
            (
                "paragraph",
                "<p>If you suspect rot already: tip the plant out. Healthy "
                "roots are firm and pale; rotten ones are brown, soft, and "
                "slide apart when pulled. Cut everything mushy back to clean "
                "tissue with sterilised scissors, repot into fresh, "
                "fast-draining mix in a pot with a real drainage hole, and "
                "water once. Then — this is the hard part — leave it alone. "
                "Recovery looks like nothing happening for a month. Doing "
                "less is the treatment.</p>",
            ),
        ],
    },
    {
        # Locked title (artifact card #1).
        "slug": "variegation-isnt-magic",
        "title": "Variegation isn't magic, it's mutation",
        "category": "propagation",
        "author": "iris_delgado",
        "age_days": 10,
        "view_count": 210,
        "cover": "cover-variegation.webp",
        "introduction": (
            "<p>Those white-splashed monstera leaves that cost more than your "
            "rent aren't a different species — they're a genetic accident that "
            "has to be carefully carried from cutting to cutting. Here's how it "
            "works and what that means when you propagate.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>A variegated monstera is a chimera: two genetically "
                "different tissues growing side by side in one plant. The "
                "white sectors carry a mutation that stops chlorophyll "
                "production; the green sectors don't. The pattern you're "
                "paying for is the boundary between them, drawn fresh in "
                "every new leaf.</p>",
            ),
            ("heading", "Why the price tag"),
            (
                "paragraph",
                "<p>White tissue doesn't photosynthesise. A heavily variegated "
                "plant is running on half an engine, so it grows slowly — and "
                "slow growth means slow propagation, and slow propagation "
                "means scarcity. You can't tissue-culture your way out of it "
                "reliably either: chimeral variegation often doesn't survive "
                'the process, which is why lab-grown "albo" batches keep '
                "disappointing people.</p>",
            ),
            ("heading", "Propagating without losing the pattern"),
            (
                "paragraph",
                "<p>The variegation lives in the meristem layers at each node. "
                "When you take a cutting, choose a node whose surrounding stem "
                "shows both colours — a balanced marbling on the stem is the "
                "best predictor that the new growth point inherits both "
                "tissues. A cutting from an all-green stretch of stem will "
                "grow an all-green plant, no matter how white the leaf above "
                "it was.</p>",
            ),
            (
                "paragraph",
                "<p>Reversion runs both ways. A plant can drift green (the "
                "faster tissue simply outcompetes the white) or drift white "
                "until it can't feed itself. You steer with the pruning "
                "shears: cut back to a node behind the drift and let a "
                "better-balanced growth point take over. And when you're "
                "buying: look at the newest leaf and the stem, not the "
                "prettiest old leaf — the newest growth tells you where the "
                "plant is going, the old leaf only tells you where it's "
                "been.</p>",
            ),
        ],
    },
    {
        # Locked title (artifact card #2).
        "slug": "fiddle-leaf-adjusting",
        "title": "Your fiddle leaf isn't dying, it's adjusting",
        "category": "care",
        "author": "sam_whitaker",
        "age_days": 17,
        "view_count": 290,
        "cover": "cover-fiddle.webp",
        "introduction": (
            "<p>You brought it home, gave it the perfect corner, and it dropped "
            "three leaves in a week. Before you diagnose disease or drown it in "
            "fixes — this is probably just what a ficus does when its world "
            "changes.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p><i>Ficus lyrata</i> has a reputation for drama, and it's "
                "earned — but the drama is mostly one behaviour: when "
                "conditions change, it sheds. A move across the room, a new "
                "home, a season flipping the light angle, a draft from a "
                "winter window. The tree doesn't know it was an upgrade. It "
                "just knows the light budget changed, and it balances the "
                "books by dropping the leaves it can no longer afford.</p>",
            ),
            ("heading", "Normal shedding vs. actual trouble"),
            (
                "paragraph",
                "<p>Adjustment loss looks like this: lower or interior leaves "
                "going first, browning from the edge inward, over two to six "
                "weeks after a change, while the top of the plant keeps "
                "pushing new growth. Trouble looks different: brown spots "
                "with yellow halos spreading across many leaves at once "
                "(bacterial), sudden all-over drop (cold shock), or mushy "
                "stems (rot). If the newest growth is healthy, you're almost "
                "certainly watching acclimation, not decline.</p>",
            ),
            (
                "paragraph",
                "<p>The worst response is to keep changing things. New spot, "
                "then another new spot, then extra water, then fertiliser to "
                '"help" — every intervention resets the clock. Pick the '
                "brightest spot you can offer (fiddles want more light than "
                "almost any care card admits — within a metre of a bright "
                "window), and then commit to it.</p>",
            ),
            ("heading", "The six-week rule"),
            (
                "paragraph",
                "<p>After any move: six weeks of boring consistency. Water "
                "when the top few centimetres dry out, don't feed, don't "
                "repot, don't rotate it daily. Count the dropped leaves if it "
                "helps — a healthy adjusting fiddle usually stops shedding "
                "inside a month and answers with a flush of new leaves at the "
                "top. That new growth is the tree's signature on the new "
                "lease.</p>",
            ),
        ],
    },
    {
        "slug": "spider-mites-early",
        "title": "Spider mites move in before you notice",
        "category": "pests-diseases",
        "author": "june_park",
        "age_days": 24,
        "view_count": 150,
        "cover": "cover-mites.webp",
        "introduction": (
            "<p>By the time you see webbing, the colony is weeks old. The real "
            "detection window is earlier — and it's on the side of the leaf you "
            "never look at.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>Spider mites are not insects — they're arachnids the size "
                "of a full stop, and they feed by puncturing individual leaf "
                "cells and drinking the contents. Each puncture leaves a pale "
                "pinprick. Scattered across a leaf, those pinpricks read as a "
                "dull, dusty, faded look long before any webbing appears. "
                "That stippling is your early warning, and it's visible weeks "
                "ahead of the cobwebs.</p>",
            ),
            ("heading", "The thirty-second weekly check"),
            (
                "paragraph",
                "<p>Once a week, flip a leaf on your most susceptible plants "
                "— calatheas, alocasias, palms, ivy, anything already stressed "
                "— and look at the underside against the light. Fine pale "
                "speckling on top, gritty dust that moves underneath: mites. "
                "A sheet of white paper held under a tapped leaf works too; "
                "the dust that walks is your answer.</p>",
            ),
            (
                "paragraph",
                "<p>Mites explode in warm, dry air — a radiator season "
                "special. A generation completes in under a week at room "
                'temperature, which is why an infestation that "appeared '
                "overnight\" didn't. It compounded, quietly, on the underside "
                "of the leaves.</p>",
            ),
            ("heading", "Treatment that actually sticks"),
            (
                "paragraph",
                "<p>Quarantine the plant first. Then physically knock the "
                "population down: a genuinely thorough shower, top and "
                "underside of every leaf. Follow with insecticidal soap or "
                "horticultural oil, coating the leaf undersides — contact "
                "treatments only kill what they touch. Repeat every five to "
                "seven days for three rounds; eggs survive the first pass, so "
                "one treatment is a pause, not a cure. And keep the humidity "
                "up afterwards — dry air is an invitation to reinfest.</p>",
            ),
        ],
    },
    {
        "slug": "prune-like-you-mean-it",
        "title": "Prune like you mean it",
        "category": "design",
        "author": "theo_brandt",
        "age_days": 31,
        "view_count": 120,
        "cover": "cover-pruning.webp",
        "introduction": (
            "<p>Timid pruning makes leggy plants. An arborist's case for cutting "
            "deeper than feels safe — and where exactly to make the cut.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>I prune trees for a living, and the mistake I see indoors "
                "is the same one I see in orchards: people trim the tips and "
                "call it shaping. Tip-trimming a leggy pothos or a stretched "
                "ficus just relocates the legginess. If you want a fuller "
                "plant, the cut has to go deeper — because new growth comes "
                "from where you cut, not where you wish.</p>",
            ),
            ("heading", "Where growth actually comes from"),
            (
                "paragraph",
                "<p>Every leaf meets the stem at a node, and at every node "
                "sits a dormant bud. Apical dominance — hormones from the "
                "growing tip — keeps those buds asleep. Remove the tip and "
                "the nearest buds below wake up, usually two or three of "
                "them. That's the whole trick: one cut above a node trades "
                "one growth point for several. Cut a centimetre above the "
                "node, angled away from the bud; stubs die back, and cuts "
                "made mid-internode leave a dead straw that invites rot.</p>",
            ),
            (
                "paragraph",
                "<p>So prune for the plant you want in six months, not the "
                "plant you have. A leggy pothos can lose half its length and "
                "answer with branches at every remaining node. A "
                "single-stalk ficus can be topped at the height where you "
                "want it to fork. Vigorous growers — pothos, philodendron, "
                "tradescantia, ficus — shrug off a hard cutback in growing "
                "season and hand you a pile of propagation material as "
                "change.</p>",
            ),
            (
                "quote",
                {
                    "quote_text": (
                        "A timid cut is a decision to make the same cut "
                        "again in three months."
                    ),
                    "attribution": "Theo Brandt",
                },
            ),
            (
                "paragraph",
                "<p>Timing matters less indoors than outside, but the rule of "
                "thumb holds: prune hard at the start of active growth "
                "(spring into summer) so the response is fast, and keep "
                "winter cuts to maintenance. Sharp, clean tools; wipe the "
                "blades between plants. Then put the shears down and let the "
                "plant answer.</p>",
            ),
        ],
    },
    {
        "slug": "small-space-jungle",
        "title": "A jungle in forty square feet",
        "category": "design",
        "author": "sam_whitaker",
        "age_days": 38,
        "view_count": 80,
        "cover": "cover-jungle.webp",
        "introduction": (
            "<p>You don't need a conservatory. A balcony, one good wall, and "
            "some vertical thinking will hold more plants than you can "
            "water in an evening — here's the layout maths.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>My entire growing space is a balcony you can cross in two "
                "steps, and it holds about sixty plants comfortably. The "
                "trick isn't miniature plants — it's that a jungle is "
                "measured in layers, not floor area. Floor, shelf, rail, and "
                "hanging: four storeys of growing space stacked over the "
                "same forty square feet.</p>",
            ),
            ("heading", "Layer by light, not by looks"),
            (
                "paragraph",
                "<p>Every shelf is its own microclimate. The top shelf near "
                "the glass gets triple the light of the floor in the corner "
                "— so the sun-hungry things (herbs, succulents, flowering "
                "plants) live high, and the shade-tolerant crowd (pothos, "
                "ferns, ZZ) furnishes the dim lower levels they'd choose in "
                "a forest anyway. When a plant sulks, the first move is one "
                "shelf up or down, not a new pot.</p>",
            ),
            (
                "paragraph",
                "<p>Grouping is free humidity. Plants transpire, and a dense "
                "cluster raises the local humidity a few points over the "
                "room — the difference between crispy calathea edges and "
                "none. Cluster the humidity-lovers on one shelf with a tray "
                "of damp pebbles under them, and let the succulents keep "
                "their airy corner.</p>",
            ),
            ("heading", "Edit like a curator"),
            (
                "paragraph",
                "<p>The failure mode of a small jungle isn't running out of "
                "space — it's keeping plants you don't love because space "
                "opened up. Forty square feet forces the good habit: every "
                "plant earns its spot each season. Propagate the favourites, "
                "gift the rest, and the jungle stays dense, healthy, and "
                "yours. A small collection you can water in twenty minutes "
                "beats a sprawling one you resent.</p>",
            ),
        ],
    },
]
