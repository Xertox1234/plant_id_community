"""Demo-world catalogue for `manage.py seed_demo_content`, plus the shared
demo-account guard helpers both `seed_demo_content` and apps.blog's
`seed_demo_blog` call (see the guard helpers section below).

Spec: docs/superpowers/specs/2026-08-15-canopy-forum-content-design.md §3–§5.
The catalogue data is pure — the calling command owns all ORM work for it.
Reply `age_hours` = hours before NOW the reply landed (strictly decreasing
per topic, all < the topic's age).
"""

BOARDS = [
    {
        "title": "Plant identification",
        "slug": "plant-identification",
        "description": "Post a photo, get a name. Most plants are identified within the hour.",
    },
    {
        "title": "Care & problems",
        "slug": "care-problems",
        "description": "Yellow leaves, root rot, repotting panic — bring it here.",
    },
    {
        "title": "Pests & diseases",
        "slug": "pests-diseases",
        "description": "Spot it early. Bugs, blight, and mystery spots, diagnosed together.",
    },
    {
        "title": "Garden design",
        "slug": "garden-design",
        "description": "Beds, borders, and balcony jungles. Show your plans and steal ideas.",
    },
    {
        "title": "Show & tell",
        "slug": "show-tell",
        "description": "New growth, first blooms, full shelfies. Brag freely.",
    },
]

DEMO_EMAIL_DOMAIN = "demo.houseplant-md.com"

USERS = [
    {"username": "iris_delgado", "display_name": "Iris Delgado", "title": "Head moderator", "trust_level": 4,
     "bio": "Keeping the canopy tidy since day one. Aroid collector, moss wall apologist."},
    {"username": "sam_whitaker", "display_name": "Sam Whitaker", "title": "Master gardener", "trust_level": 4,
     "bio": "Thirty years of vegetable beds and one very opinionated greenhouse."},
    {"username": "june_park", "display_name": "June Park", "title": "Plant pathologist", "trust_level": 3,
     "bio": "I look at spots on leaves so you don't have to. Fungus is usually the answer."},
    {"username": "theo_brandt", "display_name": "Theo Brandt", "title": "Arborist", "trust_level": 3,
     "bio": "Trees mostly, houseplants reluctantly, bonsai never again."},
    {"username": "maya_okafor", "display_name": "Maya Okafor", "title": "Balcony gardener", "trust_level": 2,
     "bio": "Twelve square meters, forty-one pots, zero regrets."},
    {"username": "priya_nair", "display_name": "Priya Nair", "title": "", "trust_level": 2,
     "bio": "Slowly turning a rental kitchen into a propagation lab."},
    {"username": "marcus_webb", "display_name": "Marcus Webb", "title": "", "trust_level": 1,
     "bio": "New-ish. I water too much and I'm working on it."},
    {"username": "lena_fischer", "display_name": "Lena Fischer", "title": "", "trust_level": 0,
     "bio": "Just got my first monstera. Be gentle."},
]

# Topic dict shape:
#   board, slug, title, author, age_days (float), pinned (bool),
#   opening: {"paragraphs": [str, ...], "image": asset-name-or-None}
#   identification: None | {"provider", "candidates": [...]}
#   replies: [{"author", "age_hours", "paragraphs": [...],
#              "image": asset-or-None, "solution": bool,
#              "reactions": {type: [usernames]}}, ...]
# Only keys that differ from the defaults need to appear in replies
# (the command reads them with .get()).

TOPICS = [
    {
        "board": "plant-identification", "slug": "monstera-albo-variegation",
        "title": "Monstera albo — is this variegation stable?",
        "author": "maya_okafor", "age_days": 2.0, "pinned": False,
        "opening": {"paragraphs": [
            "Picked this up in a trade last weekend and the seller swore the sectoral variegation is stable. Two of the newer leaves are almost half white though, and I've read that's actually a bad sign?",
            "Photo attached — the newest leaf is the one on the right. Should I cut back to the last balanced leaf or let it run?",
        ], "image": "post-monstera-albo.webp"},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 44,
             "paragraphs": ["Half-white leaves look spectacular and photosynthesize terribly. The plant is spending sugar it isn't making. I'd let one ride and watch the next node."]},
            {"author": "lena_fischer", "age_hours": 41,
             "paragraphs": ["No advice, just… wow. That leaf is unreal."]},
            {"author": "iris_delgado", "age_hours": 38,
             "paragraphs": ["Agree with Sam — stability in albos is a spectrum, not a yes/no. The node the leaf came from matters more than the leaf itself. If the petiole shows a good mix of green and white, you're fine."],
             "reactions": {"helpful": ["maya_okafor", "lena_fischer", "marcus_webb"]}},
            {"author": "maya_okafor", "age_hours": 36,
             "paragraphs": ["Petiole is marbled, roughly 60/40 green. That's reassuring, thank you both."]},
            {"author": "theo_brandt", "age_hours": 30,
             "paragraphs": ["One more thing — keep it out of harsh afternoon sun. White tissue scorches first and a scorched half-white leaf is a sad, expensive thing."]},
            {"author": "priya_nair", "age_hours": 26,
             "paragraphs": ["Following this thread because I have the exact same question about a mint monstera cutting."]},
            {"author": "sam_whitaker", "age_hours": 22,
             "paragraphs": ["Mint is a different beast, Priya — even less stable. Start a thread with a photo of yours and we'll take a look."]},
            {"author": "marcus_webb", "age_hours": 18,
             "paragraphs": ["How much would a plant like this even cost? Asking for my very worried wallet."]},
            {"author": "maya_okafor", "age_hours": 14,
             "paragraphs": ["More than I'll admit in public, Marcus."],
             "reactions": {"like": ["lena_fischer", "priya_nair"]}},
            {"author": "june_park", "age_hours": 9,
             "paragraphs": ["Late to this, but chiming in on the health side: variegated tissue is also more prone to fungal spotting when it stays wet. Water at the base, not over the leaves."]},
            {"author": "maya_okafor", "age_hours": 5,
             "paragraphs": ["Noted — it lives away from the mister now. This community is faster than the plant shop's own staff."]},
            {"author": "iris_delgado", "age_hours": 1.5,
             "paragraphs": ["That's the idea. Post an update when the next leaf unfurls — genuinely curious how it lands."]},
        ],
    },
    {
        "board": "plant-identification", "slug": "estate-sale-trailing-plant",
        "title": "Found this trailing thing at an estate sale — hoya or dischidia?",
        "author": "lena_fischer", "age_days": 6, "pinned": False,
        "opening": {"paragraphs": [
            "Grabbed a hanging basket of this for two dollars. Leaves are small, thick, and slightly fuzzy, growing in opposite pairs along thin stems. The tag just says 'assorted foliage'.",
            "It reminds me of the hoyas I see here but the leaves feel thinner. How do I tell hoya and dischidia apart without flowers?",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "priya_nair", "age_hours": 130,
             "paragraphs": ["Estate sales are the best plant shops. Check the sap — hoyas usually bleed white latex when you nick a stem, dischidia much less so."]},
            {"author": "sam_whitaker", "age_hours": 120,
             "paragraphs": ["Priya's sap test is the classic. Also look at the roots along the stem: dischidia throws adventitious roots at nearly every node because it climbs ant trees in habitat. Hoya does it too but far less eagerly. Fuzzy small opposite leaves plus eager rooting says dischidia to me — likely Dischidia hirsuta or a relative."],
             "solution": True,
             "reactions": {"helpful": ["lena_fischer", "maya_okafor"], "thanks": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 110,
             "paragraphs": ["Nicked a stem — barely any sap, and there are little roots at almost every node. Dischidia it is. Two dollars!"]},
            {"author": "iris_delgado", "age_hours": 100,
             "paragraphs": ["Marking Sam's answer as the solution. Nice ID without a flower in sight."]},
            {"author": "marcus_webb", "age_hours": 60,
             "paragraphs": ["I would have confidently called that a string of nickels and been wrong. Good thread."]},
            {"author": "lena_fischer", "age_hours": 30,
             "paragraphs": ["Update: it perked up after a soak and it's ALREADY growing. Estate sale of the year."]},
        ],
    },
    {
        "board": "plant-identification", "slug": "fuzzy-leaves-purple-undersides",
        "title": "ID please: fuzzy leaves, purple undersides",
        "author": "marcus_webb", "age_days": 9, "pinned": False,
        "opening": {"paragraphs": [
            "Office plant swap mystery. Soft fuzzy leaves, green on top, deep purple underneath, stems are slightly succulent. It's growing fast under a basic desk lamp.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 210,
             "paragraphs": ["Purple velvet plant — Gynura aurantiaca. The fuzz plus purple underside combination is hard to mistake. Fair warning: its flowers smell genuinely bad, most people pinch the buds."],
             "solution": True,
             "reactions": {"helpful": ["marcus_webb", "priya_nair"]}},
            {"author": "marcus_webb", "age_hours": 200,
             "paragraphs": ["That's it exactly, photos online match perfectly. Pinching buds as instructed."]},
            {"author": "maya_okafor", "age_hours": 180,
             "paragraphs": ["Gynura gets leggy fast in low light — the desk lamp is why it's sprinting. Cuttings root in water in about a week if you want to thicken the pot."]},
            {"author": "marcus_webb", "age_hours": 150,
             "paragraphs": ["Took three cuttings tonight. This is how it starts, isn't it."]},
            {"author": "iris_delgado", "age_hours": 140,
             "paragraphs": ["It is. Welcome."],
             "reactions": {"like": ["marcus_webb", "lena_fischer", "priya_nair"]}},
        ],
    },
    {
        "board": "plant-identification", "slug": "tree-bark-peels-like-paper",
        "title": "What tree is this? Bark peels like paper",
        "author": "priya_nair", "age_days": 12, "pinned": False,
        "opening": {"paragraphs": [
            "From my building's courtyard. Small tree, maybe four meters, and the bark peels off in thin coppery curls you can see light through. Leaves are in threes with toothed edges.",
            "The app gave me two suggestions (attached) — does the confidence look right to people who know trees?",
        ], "image": None},
        "identification": {
            "provider": "plant_id",
            "candidates": [
                {"name": "Paperbark maple", "scientific_name": "Acer griseum", "confidence": 0.91},
                {"name": "River birch", "scientific_name": "Betula nigra", "confidence": 0.42},
            ],
        },
        "replies": [
            {"author": "theo_brandt", "age_hours": 280,
             "paragraphs": ["The app nailed it — Acer griseum, paperbark maple. Trifoliate leaves plus that cinnamon exfoliating bark is a giveaway combination; river birch peels too but its leaves are single, not in threes."],
             "solution": True,
             "reactions": {"helpful": ["priya_nair", "sam_whitaker", "marcus_webb"]}},
            {"author": "sam_whitaker", "age_hours": 270,
             "paragraphs": ["Lucky courtyard. One of the best small trees there is — autumn color is going to be worth a photo for Show & tell."]},
            {"author": "priya_nair", "age_hours": 250,
             "paragraphs": ["Accepted Theo's answer. I walk past this tree every day and never looked twice until this week."]},
            {"author": "june_park", "age_hours": 220,
             "paragraphs": ["Paperbarks are also refreshingly pest-free, if anyone's shopping for a courtyard tree."]},
            {"author": "lena_fischer", "age_hours": 190,
             "paragraphs": ["The bark description alone made me google it. Gorgeous tree."]},
            {"author": "theo_brandt", "age_hours": 100,
             "paragraphs": ["If the building manager ever threatens to 'tidy' the peeling bark — that's the whole point of the tree. Defend it."]},
            {"author": "priya_nair", "age_hours": 60,
             "paragraphs": ["Formally appointing myself its guardian."]},
        ],
    },
    {
        "board": "care-problems", "slug": "fiddle-leaf-dropped-leaves-move",
        "title": "Fiddle leaf dropped 3 leaves after the move",
        "author": "marcus_webb", "age_days": 1.2, "pinned": False,
        "opening": {"paragraphs": [
            "Moved apartments on Saturday. By Tuesday my fiddle had dropped three lower leaves — full leaves, not brown-edged ones. It went from a south window to an east window.",
            "Is this normal adjustment or the beginning of the end? Photo of the crime scene attached.",
        ], "image": "post-fiddle-leaf.webp"},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 26,
             "paragraphs": ["Normal. Ficus lyrata treats any change of address as a personal insult. Three lower leaves after a light change is protest, not decline — watch the top growth, not the floor."],
             "reactions": {"helpful": ["marcus_webb", "lena_fischer"]}},
            {"author": "iris_delgado", "age_hours": 24,
             "paragraphs": ["Seconding Sam. The mistake people make NOW is compensating — more water, fertilizer, moving it again. Don't. Park it, water when the top two inches are dry, and ignore it for a month."]},
            {"author": "marcus_webb", "age_hours": 22,
             "paragraphs": ["I was literally holding the watering can when this notification came in. Putting it down."],
             "reactions": {"like": ["iris_delgado", "sam_whitaker", "maya_okafor", "priya_nair"]}},
            {"author": "june_park", "age_hours": 18,
             "paragraphs": ["One check worth doing once: lift it and look at drainage holes. If the move cracked the root ball and it's sitting in a saucer of water, that's a different conversation."]},
            {"author": "marcus_webb", "age_hours": 15,
             "paragraphs": ["Checked — drains fine, no standing water. It's protest then."]},
            {"author": "maya_okafor", "age_hours": 10,
             "paragraphs": ["Mine dropped five when I moved and grew seven that summer. They're drama, not fragile."]},
            {"author": "lena_fischer", "age_hours": 6,
             "paragraphs": ["Saving this whole thread for the day I inevitably buy one."]},
            {"author": "sam_whitaker", "age_hours": 2,
             "paragraphs": ["Update us in four weeks, Marcus. I have money on new growth."]},
        ],
    },
    {
        "board": "care-problems", "slug": "pothos-yellow-halo-leaves",
        "title": "Yellow halo on pothos leaves — overwatering or light?",
        "author": "lena_fischer", "age_days": 4, "pinned": False,
        "opening": {"paragraphs": [
            "Several older leaves on my golden pothos have gone yellow from the edge inward, like a halo, while the veins stay green longer. It sits two meters from a west window and I water every Sunday, religiously.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 90,
             "paragraphs": ["'Every Sunday, religiously' is the clue. Fixed-schedule watering plus edge-in yellowing on older leaves is the classic overwatering signature — roots suffocate, plant cannibalizes old leaves. Light two meters from a west window is fine.", "Switch from schedule to check: finger two knuckles into the soil, water only when dry at that depth."],
             "solution": True,
             "reactions": {"helpful": ["lena_fischer", "marcus_webb", "maya_okafor"], "thanks": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 85,
             "paragraphs": ["Guilty. Sunday watering was the one habit I was proud of."]},
            {"author": "sam_whitaker", "age_hours": 80,
             "paragraphs": ["Schedules aren't bad — schedule the CHECK, not the watering. Sunday = knuckle test day."],
             "reactions": {"like": ["lena_fischer", "june_park"]}},
            {"author": "priya_nair", "age_hours": 70,
             "paragraphs": ["Also worth sliding it out of the pot once — if the soil smells swampy, repot into something chunkier and it resets the clock."]},
            {"author": "lena_fischer", "age_hours": 50,
             "paragraphs": ["Checked the roots: white and firm, soil smells like soil. Caught it early then. Accepting June's answer."]},
            {"author": "marcus_webb", "age_hours": 40,
             "paragraphs": ["The knuckle test has saved every plant I own. All four of them."]},
            {"author": "iris_delgado", "age_hours": 20,
             "paragraphs": ["Threads like this are exactly what this board is for — clear symptom, clear cause, caught early. Well done everyone."]},
            {"author": "lena_fischer", "age_hours": 8,
             "paragraphs": ["Week one of knuckle-test Sundays complete. The pothos and I are in therapy together."]},
            {"author": "june_park", "age_hours": 3,
             "paragraphs": ["Recovery arc begins. The halos won't re-green, but no NEW halos is the win to watch for."]},
        ],
    },
    {
        "board": "care-problems", "slug": "repotting-roots-circling",
        "title": "Repotting panic: roots circling the pot three times",
        "author": "maya_okafor", "age_days": 15, "pinned": False,
        "opening": {"paragraphs": [
            "Went to repot my rubber plant and the root ball is a solid spiral — roots circling the pot at least three full turns. Internet says everything from 'tease gently' to 'slice it with a knife'. Which is it?",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 350,
             "paragraphs": ["Both, in order. Tease what teases free, and where it's woven solid, three shallow vertical cuts spaced around the ball. Circling roots that stay circling will eventually girdle the plant — a clean cut heals, a spiral doesn't."],
             "reactions": {"helpful": ["maya_okafor", "marcus_webb"]}},
            {"author": "theo_brandt", "age_hours": 340,
             "paragraphs": ["What Sam said — we do exactly this with nursery trees, just with bigger knives. The fear is worse than the surgery."]},
            {"author": "maya_okafor", "age_hours": 320,
             "paragraphs": ["Did it. Three cuts, teased the rest, new pot two sizes up. My kitchen looks like a crime scene but the patient is stable."],
             "reactions": {"like": ["sam_whitaker", "lena_fischer", "iris_delgado"]}},
            {"author": "priya_nair", "age_hours": 250,
             "paragraphs": ["This thread convinced me to finally check my dracaena. Two turns. Caught it in time."]},
            {"author": "sam_whitaker", "age_hours": 150,
             "paragraphs": ["Two-week check-in, Maya?"]},
            {"author": "maya_okafor", "age_hours": 30,
             "paragraphs": ["Two new leaves and no sulking whatsoever. Surgery recommended, would slice again."]},
        ],
    },
    {
        "board": "care-problems", "slug": "calathea-folds-at-noon",
        "title": "My calathea folds up at noon, not night. Normal?",
        "author": "priya_nair", "age_days": 20, "pinned": False,
        "opening": {"paragraphs": [
            "I know calatheas fold their leaves at night — mine does that too. But lately it ALSO folds around midday, then relaxes by late afternoon. It's near a south window with a sheer curtain.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 470,
             "paragraphs": ["Midday folding is light-avoidance — even through a sheer, noon sun can exceed what a forest-floor plant wants. It's protecting its leaf surface. Not damage, but it IS feedback: an east window or another meter of distance and it'll stop."],
             "reactions": {"helpful": ["priya_nair", "lena_fischer"]}},
            {"author": "priya_nair", "age_hours": 460,
             "paragraphs": ["That makes complete sense — it started when the days got longer. Moving it tonight."]},
            {"author": "maya_okafor", "age_hours": 440,
             "paragraphs": ["Calatheas: the only housemates who tell you EXACTLY what's wrong, in mime."],
             "reactions": {"like": ["priya_nair", "june_park", "marcus_webb"]}},
            {"author": "priya_nair", "age_hours": 200,
             "paragraphs": ["Moved to the east window: no more noon folding, still does its goodnight prayer. Case closed."]},
        ],
    },
    {
        "board": "pests-diseases", "slug": "hosta-leaves-eaten-overnight",
        "title": "What's eating my hosta leaves overnight?",
        "author": "maya_okafor", "age_days": 0.9, "pinned": False,
        "opening": {"paragraphs": [
            "Every morning there are new ragged holes in my hostas — sometimes half a leaf gone — and I never see a single culprit during the day. Photo of the damage attached. No slime trails that I can spot on the pavers.",
        ], "image": "post-hosta-damage.webp"},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 20,
             "paragraphs": ["Overnight ragged holes on hosta is slugs until proven otherwise, trails or no trails — they hide in the mulch by day. Go out two hours after dark with a torch; you'll meet the perpetrators personally."],
             "reactions": {"helpful": ["maya_okafor"]}},
            {"author": "june_park", "age_hours": 18,
             "paragraphs": ["Sam's right. If the torch patrol comes up empty, look for earwigs — they do a raggedier, smaller-hole version of the same crime. But on hosta, bet slugs."]},
            {"author": "theo_brandt", "age_hours": 16,
             "paragraphs": ["Beer traps work but you have to commit to emptying them, which is a smell you don't forget. A copper tape ring around the pot cluster is lazier and pretty effective."]},
            {"author": "maya_okafor", "age_hours": 12,
             "paragraphs": ["Torch patrol report: SEVEN slugs, one personal-record specimen. I feel betrayed by how calm they were about being caught."],
             "reactions": {"like": ["sam_whitaker", "june_park", "lena_fischer", "priya_nair"]}},
            {"author": "lena_fischer", "age_hours": 10,
             "paragraphs": ["'One personal-record specimen' has me crying. Godspeed, hostas."]},
            {"author": "iris_delgado", "age_hours": 8,
             "paragraphs": ["Relocation two gardens away minimum, or they commute back. This is documented."]},
            {"author": "maya_okafor", "age_hours": 6,
             "paragraphs": ["They got a one-way trip to the park. Copper tape going on this weekend as border control."]},
            {"author": "marcus_webb", "age_hours": 4,
             "paragraphs": ["Reading this at midnight and now I want to go check my one outdoor pot with a torch."]},
            {"author": "sam_whitaker", "age_hours": 1,
             "paragraphs": ["Go. Report back. This board runs on torch patrols."]},
            {"author": "maya_okafor", "age_hours": 0.4,
             "paragraphs": ["Morning update: zero new holes. First clean night in two weeks."]},
        ],
    },
    {
        "board": "pests-diseases", "slug": "white-cotton-blobs-jade",
        "title": "Tiny white cotton blobs on jade stems",
        "author": "lena_fischer", "age_days": 7, "pinned": False,
        "opening": {"paragraphs": [
            "There are little white fuzzy blobs tucked into the joints of my jade plant, mostly where leaves meet stems. They wipe off but come back within days. Close-up attached — what am I fighting?",
        ], "image": "post-mealybugs.webp"},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 160,
             "paragraphs": ["Mealybugs — the cottony tufts in stem joints are textbook. The ones you wipe are the visible fraction; eggs and crawlers hide in every crevice, which is why they 'come back'.", "Protocol: cotton bud dipped in 70% isopropyl on every blob, repeat every 4–5 days for three weeks, and isolate the plant from its neighbors today."],
             "solution": True,
             "reactions": {"helpful": ["lena_fischer", "maya_okafor", "marcus_webb"], "thanks": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 150,
             "paragraphs": ["Quarantined and dabbed. It smells like a clinic in here, which feels thematically appropriate for this site."],
             "reactions": {"like": ["june_park", "iris_delgado"]}},
            {"author": "iris_delgado", "age_hours": 140,
             "paragraphs": ["The three-week commitment is the part people skip — one missed cycle and the survivors reboot the colony. Calendar reminders are your friend."]},
            {"author": "maya_okafor", "age_hours": 100,
             "paragraphs": ["Check the pot rim and the underside of the saucer too. I lost a round to mealies that were camping OUTSIDE the plant."]},
            {"author": "lena_fischer", "age_hours": 48,
             "paragraphs": ["Found two blobs under the rim. Maya, you just won me the war two weeks early."]},
            {"author": "june_park", "age_hours": 24,
             "paragraphs": ["Keep the isopropyl cycles going anyway — 'I see none' and 'there are none' are different claims. Accepting congratulations in week three."]},
            {"author": "lena_fischer", "age_hours": 12,
             "paragraphs": ["Understood, doctor. Marking your first reply as the solution so future jade owners find the protocol."]},
        ],
    },
    {
        "board": "pests-diseases", "slug": "brown-spots-yellow-rings-monstera",
        "title": "Brown spots with yellow rings spreading across my monstera",
        "author": "marcus_webb", "age_days": 3, "pinned": False,
        "opening": {"paragraphs": [
            "Started as one brown spot with a yellow halo on a middle leaf; a week later there are five spots across three leaves. The spots are dry in the center, almost papery. I mist most mornings because the flat is dry.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 68,
             "paragraphs": ["Dry papery centers with yellow halos spreading leaf-to-leaf reads as a fungal leaf spot, and 'I mist most mornings' is very likely the engine — spores need leaf wetness, and misting delivers it daily.", "Stop misting entirely, remove the worst-affected leaf with clean scissors, and give it more airflow. Humidity for the flat: pebble tray or a humidifier, never the spray bottle."],
             "reactions": {"helpful": ["marcus_webb", "lena_fischer", "priya_nair"]}},
            {"author": "marcus_webb", "age_hours": 60,
             "paragraphs": ["The misting was supposed to be the HELPFUL thing I did. Stopped as of now, one leaf removed."]},
            {"author": "sam_whitaker", "age_hours": 50,
             "paragraphs": ["Misting is the most oversold habit in houseplants — it raises humidity for about eight minutes and leaf-wetness hours for fungi. You're not the first it's betrayed."],
             "reactions": {"like": ["marcus_webb", "june_park", "maya_okafor"]}},
            {"author": "priya_nair", "age_hours": 30,
             "paragraphs": ["Watch the remaining spots' EDGES: if they stop growing you've won; if the halos keep widening in a week, come back and June will probably prescribe a copper fungicide."]},
            {"author": "marcus_webb", "age_hours": 10,
             "paragraphs": ["Marked the spot edges on the leaf with tiny tape arrows so I can tell if they grow. Science corner."],
             "reactions": {"like": ["june_park", "priya_nair"]}},
        ],
    },
    {
        "board": "garden-design", "slug": "balcony-jungle-v2",
        "title": "Balcony jungle v2 — before and after",
        "author": "maya_okafor", "age_days": 18, "pinned": False,
        "opening": {"paragraphs": [
            "Two years ago this was a concrete rectangle with two sad railing planters (photo one). Version 2 is done: trellis wall, tiered plant stand, and the string lights that finally made it a room (photo two, taken last week).",
            "Total plant count is 41. Ask me anything, including 'how do you water all that' — the answer is 'slowly, with coffee'.",
        ], "image": "post-balcony-before.webp"},
        "identification": None,
        "replies": [
            {"author": "maya_okafor", "age_hours": 430,
             "paragraphs": ["And the after:"], "image": "post-balcony-after.webp",
             "reactions": {"love": ["lena_fischer", "priya_nair", "marcus_webb", "iris_delgado"], "like": ["sam_whitaker"]}},
            {"author": "priya_nair", "age_hours": 420,
             "paragraphs": ["The trellis wall is genius — is the vine a star jasmine? How's it handling wind up there?"]},
            {"author": "maya_okafor", "age_hours": 410,
             "paragraphs": ["Star jasmine, yes. Wind was THE design constraint: everything above railing height is either tied in or heavy-potted. Learned that the expensive way in v1."]},
            {"author": "sam_whitaker", "age_hours": 380,
             "paragraphs": ["Proper planning. One suggestion for v3: a rain gauge. Balconies live in a rain shadow and people chronically overestimate what storms deliver back there."],
             "reactions": {"helpful": ["maya_okafor"]}},
            {"author": "theo_brandt", "age_hours": 350,
             "paragraphs": ["41 plants on what looks like 12 square meters is excellent density without reading as clutter. The tiering does the work."]},
            {"author": "lena_fischer", "age_hours": 300,
             "paragraphs": ["Saving both photos as my aspiration board. The lights genuinely make it."]},
            {"author": "marcus_webb", "age_hours": 200,
             "paragraphs": ["How much of the budget was pots? I've realized pots are where plant money actually goes."]},
            {"author": "maya_okafor", "age_hours": 150,
             "paragraphs": ["Roughly 40% pots, and that's WITH two years of thrifting. Nobody warns you about this."]},
            {"author": "iris_delgado", "age_hours": 90,
             "paragraphs": ["This is the best before/after this board has had. Pinning a link to it in my mental highlight reel."]},
        ],
    },
    {
        "board": "garden-design", "slug": "north-facing-bed-what-thrives",
        "title": "North-facing bed: what actually thrives?",
        "author": "theo_brandt", "age_days": 25, "pinned": False,
        "opening": {"paragraphs": [
            "Asking for collective experience over catalog promises: a 4-meter bed against a north wall, maybe two hours of oblique morning sun in summer, decent soil. What has ACTUALLY thrived for you in that situation — not survived, thrived?",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 580,
             "paragraphs": ["Twenty years with a bed like that: hostas (obviously), Japanese forest grass, astilbe if it stays moist, and hellebores that outperform everything February through April. Ferns for structure — Dryopteris shrugs off the dry-shade months."],
             "reactions": {"helpful": ["theo_brandt", "maya_okafor", "priya_nair"]}},
            {"author": "june_park", "age_hours": 560,
             "paragraphs": ["Adding brunnera 'Jack Frost' — silver leaves that genuinely glow in shade, and slugs like it less than hostas. Disease pressure in north beds is mildew late summer; space generously."]},
            {"author": "theo_brandt", "age_hours": 540,
             "paragraphs": ["Hellebores were on the maybe list — 'outperforms everything Feb–April' promotes them to anchors. Keep them coming."]},
            {"author": "maya_okafor", "age_hours": 500,
             "paragraphs": ["Not a bed, but my north balcony corner: fuchsias flowered for five straight months in almost no direct sun. If the bed gets any morning light they'd earn a spot."]},
            {"author": "iris_delgado", "age_hours": 420,
             "paragraphs": ["Seconding forest grass — it does the 'movement' job ornamental grasses do, in shade nothing else tolerates."]},
            {"author": "theo_brandt", "age_hours": 380,
             "paragraphs": ["Plan drafted: hellebore + fern anchors, forest grass rhythm, brunnera edging, astilbe where the downspout keeps it damp, one experimental fuchsia. Planting report in autumn. Thanks all."],
             "reactions": {"like": ["sam_whitaker", "june_park", "maya_okafor"]}},
        ],
    },
    {
        "board": "show-tell", "slug": "three-years-same-pothos",
        "title": "Three years of the same pothos, one photo per year",
        "author": "priya_nair", "age_days": 11, "pinned": False,
        "opening": {"paragraphs": [
            "Year one: a four-leaf cutting in a jam jar. Year two: a respectable pot on the bookshelf. Year three, photographed this morning: it has claimed the entire shelf run and is negotiating for the curtain rail.",
            "Same plant, same window, mostly the same neglect. Time is the best fertilizer.",
        ], "image": "post-pothos-years.webp"},
        "identification": None,
        "replies": [
            {"author": "lena_fischer", "age_hours": 250,
             "paragraphs": ["'Negotiating for the curtain rail' — and winning, by the look of it. This is beautiful."],
             "reactions": {"love": ["priya_nair"]}},
            {"author": "marcus_webb", "age_hours": 240,
             "paragraphs": ["The jam jar origin story gives me hope for my cutting graveyard."]},
            {"author": "maya_okafor", "age_hours": 230,
             "paragraphs": ["Yearly photos of the same plant is such a good idea. Starting this tradition tonight with the rubber plant."],
             "reactions": {"like": ["priya_nair", "sam_whitaker"]}},
            {"author": "iris_delgado", "age_hours": 210,
             "paragraphs": ["Threads like this are why Show & tell exists. Three-year update thread or we riot."]},
            {"author": "priya_nair", "age_hours": 190,
             "paragraphs": ["Deal. See you all in year four when it owns the ceiling."]},
            {"author": "sam_whitaker", "age_hours": 120,
             "paragraphs": ["Time IS the best fertilizer. I'm having that engraved on something."],
             "reactions": {"like": ["priya_nair", "lena_fischer", "june_park"]}},
            {"author": "theo_brandt", "age_hours": 40,
             "paragraphs": ["Respect for 'mostly the same neglect' — honest plant keeping. It clearly works."]},
            {"author": "priya_nair", "age_hours": 15,
             "paragraphs": ["The secret ingredient is benign inattention and a good window."]},
        ],
    },
    {
        "board": "show-tell", "slug": "rescue-orchid-first-bloom",
        "title": "First bloom on the orchid I rescued from the grocery store",
        "author": "lena_fischer", "age_days": 5, "pinned": False,
        "opening": {"paragraphs": [
            "Eighteen months ago this phalaenopsis was on the grocery store clearance rack: two yellow leaves, rotted roots, one euro. Today it opened its first flower on a brand-new spike.",
            "Photo from the kitchen windowsill this morning. I may have said 'good morning' to it out loud.",
        ], "image": "post-orchid-bloom.webp"},
        "identification": None,
        "replies": [
            {"author": "maya_okafor", "age_hours": 110,
             "paragraphs": ["EIGHTEEN MONTHS of patience. This is the most satisfying kind of post — congratulations to you both."],
             "reactions": {"love": ["lena_fischer", "priya_nair"]}},
            {"author": "sam_whitaker", "age_hours": 100,
             "paragraphs": ["Clearance-rack rescues that rebloom are the true flex on this board. What did the root recovery look like?"]},
            {"author": "lena_fischer", "age_hours": 95,
             "paragraphs": ["Cut everything mushy, sphagnum + a clear cup for four months until new roots showed, then bark mix. Mostly I just didn't give up."]},
            {"author": "june_park", "age_hours": 80,
             "paragraphs": ["Textbook rescue protocol, executed with patience. The clear-cup trick deserves more fame."],
             "reactions": {"helpful": ["lena_fischer", "marcus_webb"]}},
            {"author": "iris_delgado", "age_hours": 60,
             "paragraphs": ["From the clinic's perspective: patient admitted critical, discharged blooming. Exactly what this community is for."],
             "reactions": {"like": ["lena_fischer", "maya_okafor", "sam_whitaker"]}},
            {"author": "marcus_webb", "age_hours": 30,
             "paragraphs": ["Checking every clearance rack in town this weekend. You've created a monster."]},
            {"author": "lena_fischer", "age_hours": 4,
             "paragraphs": ["Go forth and rescue. Second flower bud is already swelling — updates as they open."]},
        ],
    },
    {
        "board": "show-tell", "slug": "bloom-watch-2026",
        "title": "Bloom watch 2026: what's flowering at your place this August?",
        "author": "iris_delgado", "age_days": 10, "pinned": True,
        "opening": {"paragraphs": [
            "It's August, which means the community bloom watch is ON. Every year we track what's flowering, fruiting, and quietly failing across everyone's windowsills, balconies, and beds — one thread, all month.",
            "The rules are simple: post what's blooming (photos loved, not required), say roughly where you're growing it, and if something SHOULD be blooming but isn't, post that too — someone here will know why.",
            "I'll start: the moss wall is not blooming because it is moss, and I've made peace with that.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "maya_okafor", "age_hours": 235,
             "paragraphs": ["Balcony report: star jasmine second flush, one defiant dahlia in a pot that's too small for it, and the string lights (perennial, evergreen, zero water)."],
             "reactions": {"like": ["iris_delgado", "lena_fischer"]}},
            {"author": "sam_whitaker", "age_hours": 220,
             "paragraphs": ["Greenhouse: tomatoes fruiting on schedule, and the hoyas chose THIS week to all open at once — twelve umbels across three plants. The smell at 9pm is a event."],
             "reactions": {"love": ["priya_nair", "maya_okafor"]}},
            {"author": "priya_nair", "age_hours": 200,
             "paragraphs": ["Kitchen lab: hoya cutting from Sam's advice thread has its FIRST peduncle. Eighteen months from cutting to countdown."]},
            {"author": "sam_whitaker", "age_hours": 195,
             "paragraphs": ["Do not move it now, Priya. Not one centimeter. Peduncles hold grudges."],
             "reactions": {"helpful": ["priya_nair"], "like": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 120,
             "paragraphs": ["My rescue orchid opened its first flower TODAY — full story in its own thread, but it counts for the watch. One euro plant, first bloom, eighteen months."],
             "reactions": {"love": ["iris_delgado", "maya_okafor"]}},
            {"author": "theo_brandt", "age_hours": 100,
             "paragraphs": ["Failing-quietly entry as requested: the courtyard hydrangea has produced exactly one (1) flower head. Suspect last winter's pruning enthusiasm. Accepting condolences and pruning-calendar corrections."]},
            {"author": "sam_whitaker", "age_hours": 90,
             "paragraphs": ["Theo — macrophylla blooms on old wood, so last summer's cuts took this year's flowers with them. Prune right after flowering, never in spring. Next August will forgive you."],
             "reactions": {"helpful": ["theo_brandt", "marcus_webb"]}},
            {"author": "marcus_webb", "age_hours": 70,
             "paragraphs": ["Nothing blooming at mine yet, but the purple velvet plant from my ID thread is growing like it's being paid. Does aggressive foliage count for the watch?"]},
            {"author": "iris_delgado", "age_hours": 65,
             "paragraphs": ["Foliage counts, Marcus. The watch honors all victories."],
             "reactions": {"like": ["marcus_webb", "lena_fischer"]}},
            {"author": "june_park", "age_hours": 20,
             "paragraphs": ["Pathologist's entry: the healthiest thing in my flat is a sweet potato that sprouted in the pantry and has been promoted to a vase. August delivers."],
             "reactions": {"love": ["iris_delgado", "priya_nair", "maya_okafor"]}},
            {"author": "iris_delgado", "age_hours": 1,
             "paragraphs": ["Week-two roundup: two first-ever blooms, one hoya event, one hydrangea diagnosis, one pantry promotion. Keep them coming — the watch runs all month."],
             "reactions": {"like": ["sam_whitaker", "lena_fischer"]}},
        ],
    },
]

# ---------------------------------------------------------------------------
# Shared guard helpers — single source for the demo-account shape, used by
# BOTH seed commands (seed_demo_content and apps.blog's seed_demo_blog).
# Duplicated guard blocks drift (spec §5 / kimi-challenge); keep it here.
# Django imports live inside the functions so importing the catalogue data
# stays settings-free.
# ---------------------------------------------------------------------------


def real_users_queryset():
    """Every account that is neither demo-shaped nor a superuser.

    Guard layer 2's census: any row here means a live community — the seeds
    abort unconditionally (no override flag, by design)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    demo_usernames = {u["username"] for u in USERS}
    return User.objects.exclude(
        username__in=demo_usernames,
        email__iendswith=f"@{DEMO_EMAIL_DOMAIN}",
    ).exclude(is_superuser=True)


def is_demo_account(user):
    """True when the account has the demo shape: unusable password AND the
    demo email domain. The census excuses superusers by design (the Railway
    admin must not block seeding), so this per-account check is what stops
    get_or_create from adopting a real account — superuser included — that
    happens to sit on a demo username."""
    return user.has_usable_password() is False and user.email.lower().endswith(
        f"@{DEMO_EMAIL_DOMAIN}".lower()
    )


def ensure_demo_user(spec, stdout=None):
    """Get-or-create ONE demo user (with ForumProfile fields) from a USERS
    spec. Never adopts or modifies a real account. Appointed trust survives
    signal recounts (signals.py takes max(current, earned))."""
    from django.contrib.auth import get_user_model
    from django.core.management.base import CommandError
    from wagtail_forum.models import ForumProfile

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=spec["username"],
        defaults={"email": f"{spec['username']}@{DEMO_EMAIL_DOMAIN}"},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
        profile = ForumProfile.for_user(user)
        profile.display_name = spec["display_name"]
        profile.title = spec["title"]
        profile.bio = spec["bio"]
        profile.trust_level = spec["trust_level"]
        profile.save(update_fields=["display_name", "title", "bio", "trust_level"])
        if stdout:
            stdout.write(f"Created demo user {spec['username']}.")
    elif not is_demo_account(user):
        raise CommandError(
            f"Refusing to seed demo user '{spec['username']}' "
            "— an account with that username already exists "
            "and is not a demo account (email ending in "
            f"@{DEMO_EMAIL_DOMAIN} with no usable password). "
            "This seed never adopts or modifies a real "
            "account, superuser or not."
        )
    return user
