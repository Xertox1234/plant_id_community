"""Care-guide topics for ``manage.py generate_care_drafts`` (todo 445).

About 50 common houseplant care questions: general care, problems, pests
(cultural and mechanical control only) and per-plant guides. Todo 330's
hard-blocked classes are left out entirely: ingestion, toxicity, edibility or
medicinal use, and pesticide or chemical dosing. The command also screens
every topic and every generated paragraph with its ``is_blocked`` (the RAG
guardrail plus a named-treatment screen), so this list cannot drift into
those classes.

Each entry is ``(slug, title, focus)``. The slug is the draft page's slug and
makes a re-run skip what already exists.
"""

CARE_TOPICS: list[tuple[str, str, str]] = [
    # --- Watering --------------------------------------------------------
    (
        "how-often-to-water-houseplants",
        "How Often Should You Water Houseplants?",
        "checking soil moisture instead of following a fixed schedule, and how "
        "pot, light and season change the interval",
    ),
    (
        "signs-of-overwatering",
        "Signs You Are Overwatering a Houseplant",
        "the symptoms of too much water and how to let a plant recover",
    ),
    (
        "signs-of-underwatering",
        "Signs You Are Underwatering a Houseplant",
        "the symptoms of a dry plant and how to rehydrate compacted, dry soil",
    ),
    (
        "bottom-watering-houseplants",
        "Bottom Watering: When and How to Do It",
        "how bottom watering works, which plants like it, and flushing the "
        "soil from the top now and then",
    ),
    (
        "tap-water-rain-water-houseplants",
        "Tap Water, Filtered Water or Rain Water?",
        "which water to use for houseplants, letting tap water stand, and "
        "plants that are sensitive to hard water",
    ),
    (
        "self-watering-pots",
        "Do Self-Watering Pots Work?",
        "how wicking and reservoir pots work, which plants suit them, and how to avoid soggy soil",
    ),
    # --- Light and environment --------------------------------------------
    (
        "bright-indirect-light-explained",
        "What Does Bright Indirect Light Mean?",
        "reading window direction and distance, and how to tell whether a plant gets enough light",
    ),
    (
        "low-light-houseplants",
        "Houseplants That Cope With Low Light",
        "which common houseplants tolerate low light and how their care changes",
    ),
    (
        "grow-lights-for-houseplants",
        "Grow Lights for Houseplants: The Basics",
        "choosing a grow light, how far to place it, and how many hours to run it",
    ),
    (
        "raising-humidity-for-houseplants",
        "How to Raise Humidity for Houseplants",
        "grouping plants, pebble trays and humidifiers, and which plants "
        "actually need higher humidity",
    ),
    (
        "temperature-and-drafts",
        "Temperature, Drafts and Houseplants",
        "comfortable temperature ranges and keeping plants away from drafts, "
        "radiators and cold glass",
    ),
    (
        "acclimating-new-houseplants",
        "Helping a New Houseplant Settle In",
        "what to expect in the first weeks and how to avoid shocking a new plant",
    ),
    (
        "quarantine-new-houseplants",
        "Why You Should Quarantine New Houseplants",
        "keeping new plants apart for a few weeks and what to inspect for",
    ),
    # --- Soil, pots and repotting ----------------------------------------
    (
        "choosing-a-pot-with-drainage",
        "Choosing the Right Pot for a Houseplant",
        "drainage holes, pot material and choosing the right size",
    ),
    (
        "potting-mix-basics",
        "Potting Mix Basics for Houseplants",
        "what goes into a potting mix, chunky mixes for aroids, and gritty mixes for succulents",
    ),
    (
        "when-to-repot-a-houseplant",
        "When Does a Houseplant Need Repotting?",
        "the signs that a plant has outgrown its pot and the best time of year to repot",
    ),
    (
        "how-to-repot-a-houseplant",
        "How to Repot a Houseplant Step by Step",
        "a step-by-step repotting guide, loosening roots, and aftercare",
    ),
    (
        "repotting-shock",
        "Repotting Shock: Causes and Recovery",
        "why plants droop after repotting and how to help them recover",
    ),
    # --- Feeding and grooming --------------------------------------------
    (
        "fertilizing-houseplants-basics",
        "Fertilizing Houseplants: The Basics",
        "when houseplants need feeding, reading N-P-K numbers, and why less is "
        "often better; follow the product label for amounts",
    ),
    (
        "cleaning-houseplant-leaves",
        "How to Clean Houseplant Leaves",
        "dusting and wiping leaves with plain water, and why clean leaves matter",
    ),
    (
        "pruning-houseplants",
        "Pruning Houseplants for Shape and Health",
        "where to cut, removing dead growth, and encouraging bushier plants",
    ),
    # --- Propagation -----------------------------------------------------
    (
        "propagating-stem-cuttings-in-water",
        "Propagating Stem Cuttings in Water",
        "taking a cutting with a node, rooting it in water, and moving it to soil",
    ),
    (
        "propagating-cuttings-in-soil",
        "Propagating Cuttings Directly in Soil",
        "rooting cuttings in a light mix and keeping them evenly moist",
    ),
    (
        "dividing-houseplants",
        "Dividing Houseplants to Make More Plants",
        "which plants can be divided and how to split a root ball",
    ),
    # --- Problems --------------------------------------------------------
    (
        "yellow-leaves-causes",
        "Why Are My Houseplant's Leaves Turning Yellow?",
        "the common causes of yellow leaves and how to tell them apart",
    ),
    (
        "brown-leaf-tips",
        "Brown Leaf Tips on Houseplants",
        "dry air, uneven watering and salt build-up, and how to fix each",
    ),
    (
        "drooping-houseplant",
        "Why Is My Houseplant Drooping?",
        "thirst, overwatering, temperature and root problems as causes of drooping",
    ),
    (
        "leaf-drop-after-moving",
        "Leaf Drop After Moving a Houseplant",
        "why plants drop leaves after a move and how to help them adjust",
    ),
    (
        "leggy-houseplants",
        "Leggy Houseplants and How to Fix Them",
        "why plants stretch toward light and how to encourage compact growth",
    ),
    (
        "root-rot",
        "Root Rot: How to Spot It and Save the Plant",
        "recognizing root rot, trimming damaged roots, and repotting into fresh mix",
    ),
    (
        "winter-houseplant-care",
        "Caring for Houseplants in Winter",
        "slower growth, less water, shorter days and dry indoor air",
    ),
    (
        "summer-houseplant-care",
        "Caring for Houseplants in Summer",
        "heat, stronger light, more frequent watering, and moving plants outdoors",
    ),
    (
        "houseplant-care-while-on-vacation",
        "Keeping Houseplants Alive While You Travel",
        "watering before you leave, grouping plants, and simple wicking setups",
    ),
    # --- Pests (cultural and mechanical control only) --------------------
    (
        "fungus-gnats",
        "Fungus Gnats: Why They Appear and How to Reduce Them",
        "letting the topsoil dry, yellow sticky traps, and watering habits; "
        "name no pest-control products",
    ),
    (
        "spider-mites",
        "Spider Mites on Houseplants",
        "spotting webbing and stippling, isolating the plant, rinsing leaves "
        "and raising humidity; name no pest-control products",
    ),
    (
        "mealybugs",
        "Mealybugs on Houseplants",
        "recognizing mealybugs, isolating the plant, and removing them by "
        "hand; name no pest-control products",
    ),
    (
        "scale-insects",
        "Scale Insects on Houseplants",
        "recognizing scale, isolating the plant, and scraping it off by hand; "
        "name no pest-control products",
    ),
    # --- Plant guides ----------------------------------------------------
    (
        "pothos-care-guide",
        "Pothos Care Guide",
        "light, watering, trailing and propagation for pothos",
    ),
    (
        "snake-plant-care-guide",
        "Snake Plant Care Guide",
        "light, sparse watering and repotting for snake plants",
    ),
    (
        "monstera-care-guide",
        "Monstera Deliciosa Care Guide",
        "light, watering, support poles and aerial roots for monstera",
    ),
    (
        "zz-plant-care-guide",
        "ZZ Plant Care Guide",
        "low light tolerance, rhizomes and infrequent watering for ZZ plants",
    ),
    (
        "peace-lily-care-guide",
        "Peace Lily Care Guide",
        "watering cues, light and encouraging blooms for peace lilies",
    ),
    (
        "spider-plant-care-guide",
        "Spider Plant Care Guide",
        "light, watering, brown tips and propagating plantlets for spider plants",
    ),
    (
        "fiddle-leaf-fig-care-guide",
        "Fiddle Leaf Fig Care Guide",
        "bright light, consistent watering and avoiding leaf drop for fiddle leaf figs",
    ),
    (
        "rubber-plant-care-guide",
        "Rubber Plant Care Guide",
        "light, watering and pruning for rubber plants",
    ),
    (
        "heartleaf-philodendron-care-guide",
        "Heartleaf Philodendron Care Guide",
        "light, watering and trailing growth for heartleaf philodendron",
    ),
    (
        "calathea-care-guide",
        "Calathea Care Guide",
        "humidity, water quality and curling leaves for calatheas",
    ),
    (
        "phalaenopsis-orchid-care-guide",
        "Phalaenopsis Orchid Care Guide",
        "bark media, watering and reblooming for moth orchids",
    ),
    (
        "succulent-care-guide",
        "Indoor Succulent Care Guide",
        "bright light, gritty soil and soak-and-dry watering for succulents",
    ),
    (
        "jade-plant-care-guide",
        "Jade Plant Care Guide",
        "light, watering and shaping for jade plants",
    ),
    (
        "boston-fern-care-guide",
        "Boston Fern Care Guide",
        "humidity, even moisture and shedding for Boston ferns",
    ),
    (
        "chinese-evergreen-care-guide",
        "Chinese Evergreen Care Guide",
        "low light, watering and temperature for aglaonema",
    ),
    (
        "hoya-care-guide",
        "Hoya Care Guide",
        "light, drying out between waterings and encouraging blooms for hoyas",
    ),
]

CARE_GUIDE_TAG = "care-guide"
