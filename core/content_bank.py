# -*- coding: utf-8 -*-
"""ContentBank — real, hand-written, fact-checked narration scripts.

WHY THIS EXISTS: as of 2026-07-05 the user has not yet added a working LLM
API key (AvalAI/GapGPT/Groq/Gemini are all unconfigured; OpenRouter hits
rate limits, DeepSeek has no balance -- see docs/LLM-PROVIDERS-2026.md).
Until a real key is added, core/script_writer.py's LLM path fails and the
pipeline used to fall back to a generic, honest-but-crude 5-line placeholder
template every single time.

The user explicitly asked the agent to personally do "the AI work" the
factory needs in the meantime. This module is that: every script below was
written by the agent (not an LLM call, no extra API cost) and every factual
claim was checked with live web research before being used -- see
docs/CONTENT-BANK.md for the sourcing notes per script. These are real
narration scripts, not placeholders.

STRUCTURE: each script follows the exact same research-backed engagement
structure ScriptWriter asks an LLM to use (see docs/YOUTUBE-GROWTH-AND-
ENGAGEMENT.md): a hook with no channel intro, a body with a narrative arc,
an early light subscribe mention tied to a concrete payoff, one specific
mid-video comment question, and a dual-purpose outro (one concrete subscribe
reason + a second, different comment question).

LOOKUP: keyed by (language, niche_key, exact topic string). The topic
strings used here are IDENTICAL to core/content_config.NICHES[niche_key]
["evergreen_topics"] -- NicheAnalyzer already falls back to picking one of
those exact strings whenever no live trending topic is found (or every
trending one was already covered per channel_memory -- see
core/niche_analyzer.py). That means a real, curated script gets used
automatically the moment that fallback triggers, with no extra plumbing.

The moment a real LLM key works, LLMRouter succeeds first (see
core/script_writer.py's `_llm_script` call, tried BEFORE this bank) and this
module is never even consulted for that video.
"""

CONTENT_BANK = {
    # ----------------------------------------------------------------- #
    # ENGLISH
    # ----------------------------------------------------------------- #
    "en": {
        "psychology": {
            "Why we procrastinate even when we know better": [
                {"text": "You know exactly what you should be doing right now. And yet, here you are.", "query": "person thinking"},
                {"text": "For decades, psychologists blamed procrastination on laziness or poor time management. New research says that's almost completely wrong.", "query": "clock ticking desk"},
                {"text": "Dr. Tim Pychyl, who has spent his career studying this exact behavior, found something surprising: procrastination isn't about your calendar. It's about your emotions.", "query": "person stressed desk"},
                {"text": "When a task makes you feel anxious, bored, or insecure, your brain does something ancient and automatic: it looks for anything else to make that feeling go away right now.", "query": "human brain"},
                {"text": "That's why scrolling your phone feels so much easier than opening that document. Your brain isn't being lazy. It's mood-repairing.", "query": "phone scrolling hand"},
                {"text": "Stick around, because the fix for this isn't what most productivity videos tell you -- and once you see it, you can't unsee it.", "query": "person thinking"},
                {"text": "Time management apps assume the problem is planning. But if the real problem is emotional, a better calendar won't save you.", "query": "journal writing"},
                {"text": "Researchers found that the single biggest lever is something called 'mood repair': learning to sit with the uncomfortable feeling for just a few minutes, without immediately escaping it.", "query": "meditation calm"},
                {"text": "Here's a strange trick that works: forgive yourself for procrastinating last time. Studies on college students found self-forgiveness, not guilt, was what predicted finishing the next task sooner. Have you ever actually forgiven yourself instead of beating yourself up? Tell me in the comments.", "query": "silhouette sunset"},
                {"text": "So next time you catch yourself avoiding something, try asking a different question. Not 'why am I so lazy,' but 'what feeling am I actually avoiding right now?'", "query": "walking alone nature"},
                {"text": "If this changed how you think about your own procrastination, subscribe -- every week we break down one more psychology finding that actually changes how you act, not just how you think. And tell me: what's the one task you've been avoiding the longest?", "query": "sunset silhouette"},
            ],
            "How your childhood shapes your adult relationships": [
                {"text": "The way you argue with your partner today may have been decided before you turned five.", "query": "close up eyes"},
                {"text": "A landmark study tracked more than a thousand people from infancy to their thirties, following every important relationship along the way.", "query": "journal writing"},
                {"text": "The single strongest predictor of secure, trusting adult relationships wasn't wealth, personality, or even how the parents got along with each other.", "query": "person thinking"},
                {"text": "It was simply the quality of the bond a child had with their primary caregiver -- mostly, in this study, the mother.", "query": "emotional portrait"},
                {"text": "People who felt close and had less conflict with their mother in childhood grew up to feel more secure in romantic relationships, friendships, and even at work.", "query": "walking alone nature"},
                {"text": "And here's the part almost nobody talks about -- stick with me, because attachment style isn't a life sentence.", "query": "silhouette sunset"},
                {"text": "Childhood friendships mattered too. Kids with strong, stable friendships built stronger romantic security later -- a completely separate pathway from parents.", "query": "therapy session"},
                {"text": "That means two very different childhoods can lead to the same secure adult: through a caregiver, or through a best friend who showed up every day.", "query": "meditation calm"},
                {"text": "Researchers call the insecure patterns 'anxious' and 'avoidant' -- and both can shift with a stable relationship later in life, even in adulthood. Which pattern do you recognize in yourself: needing constant reassurance, or pulling away when things get close?", "query": "close up eyes"},
                {"text": "Awareness alone doesn't fix everything, but knowing where a pattern came from is the first step to no longer being ruled by it.", "query": "human brain"},
                {"text": "Subscribe if you want more research-backed breakdowns like this one that actually explain your own behavior instead of just labeling it. And tell me -- what's one relationship pattern you've noticed repeats in your life?", "query": "sunset silhouette"},
            ],
        },
        "history_mystery": {
            "The unsolved mystery of the Mary Celeste": [
                {"text": "In 1872, a ship was found completely abandoned in the middle of the Atlantic -- cargo untouched, food still on the table, and not a single person on board.", "query": "old map"},
                {"text": "The Mary Celeste had left New York on November 7th, headed for Genoa, Italy, carrying ten people and seventeen hundred barrels of raw alcohol.", "query": "historic city"},
                {"text": "A month later, a British ship called the Dei Gratia spotted her drifting, sails partly set, completely alone.", "query": "old ship ocean"},
                {"text": "When they boarded, everything looked normal. The crew's belongings, valuables, even a sewing machine, were untouched. But the lifeboat was gone, and so was every person.", "query": "archive documents"},
                {"text": "No struggle. No blood. No note. Just an empty ship, seemingly abandoned in calm weather, in good working order.", "query": "old book pages"},
                {"text": "The official investigation found nothing -- and that's exactly what makes this case still debated today. Keep watching, because the leading theory is stranger than any legend.", "query": "castle aerial"},
                {"text": "The most credible modern theory involves the cargo itself: raw alcohol. If some barrels leaked, fumes could have built up below deck.", "query": "museum artifact"},
                {"text": "Captain Briggs, an experienced and cautious sailor, may have believed the ship was about to explode, and ordered everyone into the lifeboat as a precaution, tied to the ship by a rope, ready to be pulled back in once the danger passed.", "query": "statue monument"},
                {"text": "If that rope snapped, or a wave caught the lifeboat wrong, ten people could have been swept away in minutes, while the Mary Celeste sailed calmly on without them. What do you think really happened that day -- accident, panic, or something else entirely?", "query": "foggy forest night"},
                {"text": "We'll likely never know for certain. The Mary Celeste herself sailed for another thirteen years before being deliberately wrecked in an insurance scam -- one final strange twist in her story.", "query": "ancient ruins"},
                {"text": "If unsolved mysteries like this fascinate you, subscribe -- we dig into a new one every week, always based on real historical records, never speculation dressed up as fact. And let me know: which decades-old mystery should we cover next?", "query": "old map"},
            ],
            "Why the Library of Alexandria really burned": [
                {"text": "You've probably heard the Library of Alexandria burned in one dramatic fire. The real story is far messier -- and far more interesting.", "query": "ancient ruins"},
                {"text": "The library wasn't even a public library like we imagine today. It was a royal research institution, built to serve the Ptolemaic kings of Egypt and the scholars they funded.", "query": "old book pages"},
                {"text": "Its first serious blow came in 48 BCE, not from a mob or a conqueror's order, but as collateral damage -- a fire started during Julius Caesar's military campaign in the city spread to warehouses near the docks.", "query": "ancient civilization"},
                {"text": "Some ancient sources say that fire may have destroyed only stored scrolls awaiting shipment, not the main library building itself.", "query": "old map"},
                {"text": "The library, or what remained of it, kept functioning for centuries afterward -- scholars still worked there under later Roman rule.", "query": "historic city"},
                {"text": "Stick around, because the ending of this story isn't one single burning -- it's a slow fade that took over four hundred years.", "query": "museum artifact"},
                {"text": "In 272 CE, Emperor Aurelian's forces damaged the area again while putting down a revolt. By then, much of the collection had likely already decayed naturally -- papyrus scrolls only lasted a few decades before crumbling and needing to be recopied by hand.", "query": "archive documents"},
                {"text": "That means an army of scribes was constantly required just to keep existing knowledge from disappearing -- a maintenance problem, not just a destruction problem.", "query": "statue monument"},
                {"text": "By the time religious riots damaged pagan temples in the city in 391 CE, historians find no clear evidence that a great trove of scrolls still existed to burn. Which surprises you more: that it wasn't one dramatic fire, or that neglect may have destroyed more than any army did?", "query": "foggy forest night"},
                {"text": "The truth is less cinematic than the legend, but it teaches something modern too: knowledge doesn't just get destroyed. It also gets lost when nobody keeps copying it forward.", "query": "castle aerial"},
                {"text": "If you like history explained through what actually happened rather than the popular myth, subscribe -- that's exactly what this channel does every episode. And tell me which historical 'myth' you want fact-checked next.", "query": "ancient ruins"},
            ],
        },
        "true_crime": {
            "The cold case that was solved decades later by DNA": [
                {"text": "For over thirty years, one man committed at least twelve murders and dozens of assaults across California -- and vanished without a trace.", "query": "police tape night"},
                {"text": "Investigators called him the Golden State Killer. Between 1976 and 1986, he terrorized entire neighborhoods, and then the trail went completely cold.", "query": "detective office"},
                {"text": "For three decades, his DNA sat in evidence lockers, matching nothing in any criminal database. No name. No face. No suspect.", "query": "old case files"},
                {"text": "Then, in 2018, a retired investigator tried something no one had used on a case like this before: a public genealogy website.", "query": "magnifying glass evidence"},
                {"text": "Instead of searching police databases, they uploaded the killer's crime-scene DNA profile to GEDmatch, a site normal people use to find long-lost relatives.", "query": "close up eyes"},
                {"text": "What happened next changed how cold cases get solved forever -- keep watching, because the actual breakthrough is not what most true-crime shows tell you.", "query": "city noir night"},
                {"text": "The DNA didn't match the killer directly. It matched distant relatives who had nothing to do with the crimes -- but their family tree pointed investigators toward one branch, then one name.", "query": "rain window night"},
                {"text": "That name was Joseph DeAngelo, a former police officer living quietly in a Sacramento suburb. Investigators secretly collected his discarded DNA and compared it to the decades-old crime scene samples.", "query": "flashlight dark room"},
                {"text": "It was a match. Decades of running, ended by a relative's hobby website. Did you know public DNA-genealogy sites have solved dozens of cold cases like this one? Should there be limits on using them this way, or is catching killers worth it?", "query": "courtroom"},
                {"text": "DeAngelo pleaded guilty in 2020 to thirteen murders. The technique used to catch him has since been used to crack dozens of other cold cases across the country.", "query": "old case files"},
                {"text": "If cases like this fascinate you, subscribe -- every episode here is built from real reporting, not rumors. And tell me: which cold case should we investigate next?", "query": "detective office"},
            ],
            "The forgery that fooled the world's top experts": [
                {"text": "In 1945, Dutch police arrested a man for one of the worst crimes imaginable: selling a priceless national treasure to the Nazis.", "query": "old case files"},
                {"text": "The painting was supposedly a lost Vermeer, sold directly to Hermann Goering, Hitler's second-in-command. The charge was treason, punishable by death.", "query": "museum artifact"},
                {"text": "The accused, an obscure painter named Han van Meegeren, had one shocking way to save his own life: confess to an even bigger crime.", "query": "detective office"},
                {"text": "He claimed the 'Vermeer' wasn't a lost masterpiece at all. He'd painted it himself, along with several other 'Vermeers' hanging in respected museums.", "query": "old book pages"},
                {"text": "Nobody believed him. Art experts had already authenticated these paintings as genuine seventeenth-century masterworks.", "query": "magnifying glass evidence"},
                {"text": "So the court did something extraordinary to test his claim -- and it's one of the strangest trials in art history. Keep watching to see how it played out.", "query": "courtroom"},
                {"text": "Van Meegeren was given a canvas, paint, and brushes, and ordered to paint a brand new 'Vermeer' live in front of guards and witnesses.", "query": "close up eyes"},
                {"text": "He mixed his own pigments from scratch and baked the canvas to fake centuries of aging, the exact trick he'd used to fool museums for years.", "query": "old case files"},
                {"text": "When the painting was finished, it was unmistakably in Vermeer's style. The forger had been telling the truth all along. Do you think fooling the experts made him a criminal, or in a strange way, a genius?", "query": "museum artifact"},
                {"text": "He was convicted of forgery instead of treason, a far lighter sentence, and by some accounts was treated as a folk hero for conning a Nazi leader out of two million dollars in today's money.", "query": "statue monument"},
                {"text": "If true stories stranger than fiction are your thing, subscribe -- new case, every week. And tell me: which forgery or con should we cover next?", "query": "old case files"},
            ],
        },
        "luxury_lifestyle": {
            "Inside the world's most expensive private islands": [
                {"text": "Some private islands cost more per acre than an entire city block in Manhattan.", "query": "yacht ocean"},
                {"text": "Take Bell Island in the Bahamas: 349 acres, sold for about one hundred million dollars, nearly $300,000 for every single acre of sand and palm trees.", "query": "private jet"},
                {"text": "Compare that to Lanai, the Hawaiian island Larry Ellison bought almost entirely for himself: 90,000 acres for around 300 million dollars, roughly $3,300 an acre.", "query": "penthouse view"},
                {"text": "Same category of buyer, wildly different price per acre, because with private islands, you're not just paying for land. You're paying for proximity to everything else that makes it usable.", "query": "luxury car"},
                {"text": "Ellison didn't just buy Lanai as a trophy. He rebuilt its infrastructure entirely: solar farms, water conservation systems, organic farms supplying his own resorts.", "query": "city skyline night"},
                {"text": "And that's actually the real story behind billionaire islands -- it's rarely just a beach house. Stick around for the strangest one on this list.", "query": "fine dining"},
                {"text": "In St. Petersburg, Roman Abramovich transformed New Holland Island, once an 18th-century Russian naval shipyard, into a four-hundred-million-dollar cultural venue with art exhibitions and open-air concerts.", "query": "designer fashion"},
                {"text": "These purchases aren't really about escaping the world. They're about building a completely private version of it, on your own terms, answerable to nobody.", "query": "watch closeup"},
                {"text": "If money were genuinely no object, would you want an entire island to yourself, or does that sound more lonely than luxurious? Tell me honestly in the comments.", "query": "champagne pour"},
                {"text": "Because the running cost of these islands, staff, energy, upkeep, security, often rivals the original purchase price within just a few years.", "query": "yacht ocean"},
                {"text": "Subscribe for more inside looks at how the ultra-wealthy actually spend their money, not the fantasy version, the real numbers. And tell me: which billionaire purchase should we break down next?", "query": "private jet"},
            ],
            "How billionaires actually spend their mornings": [
                {"text": "Warren Buffett, one of the richest men alive, starts almost every single day the exact same unglamorous way: reading.", "query": "fine dining"},
                {"text": "Not headlines, not social media. Buffett reportedly spends up to eighty percent of his working day reading reports, filings, and books, with some estimates at 500 pages a day.", "query": "reading newspaper morning"},
                {"text": "A study tracking 36 self-made billionaires found a strikingly boring pattern: seventy-five percent of them wake up before 7 a.m., and several, including Tim Cook, are up before 5.", "query": "city skyline night"},
                {"text": "There's no private jet in this part of the story. It's discipline applied to the most unremarkable hours of the day, before anyone else is even awake to compete for their attention.", "query": "penthouse view"},
                {"text": "Richard Branson swims or kite-surfs most mornings before touching a single email. Mark Zuckerberg trains in combat sports. The common thread isn't the activity, it's that movement comes before screens.", "query": "luxury car"},
                {"text": "And there's one habit almost every single one of them shares that has nothing to do with money at all -- stick around for it.", "query": "watch closeup"},
                {"text": "It's planning. Elon Musk reportedly time-blocks his day in five-minute increments. Jeff Bezos refuses to schedule important meetings before 10 a.m., protecting his sharpest hours for deep thinking, not calls.", "query": "city skyline night"},
                {"text": "In other words, the actual luxury isn't a mansion or a jet. It's having enough control over your calendar to protect your best hours for what matters most.", "query": "champagne pour"},
                {"text": "If you could protect just one hour of your day completely from interruptions, what would you actually do with it? Tell me in the comments.", "query": "designer fashion"},
                {"text": "None of these routines are exotic or expensive. They're just consistent, every single day, for decades, which might be the least glamorous secret in all of luxury lifestyle content.", "query": "sunset silhouette"},
                {"text": "If you want more of the real habits behind extreme success, not just the highlight reel, subscribe. And tell me: whose morning routine surprised you the most?", "query": "fine dining"},
            ],
        },
        "finance": {
            "Why most lottery winners go broke within years": [
                {"text": "You've probably heard that seventy percent of lottery winners end up broke. Here's the twist: that statistic might be completely made up.", "query": "stock market chart"},
                {"text": "The number gets traced back to something called the National Endowment for Financial Education, except the organization itself has publicly said it never produced that research.", "query": "calculator desk"},
                {"text": "In 2026, journalists tracked 31 real Powerball winners who claimed jackpots over fifty million dollars, over an entire decade.", "query": "coins stack"},
                {"text": "The result contradicted the myth almost completely: most were still millionaires ten years later, quietly living normal lives, giving to charity, avoiding headlines.", "query": "bank building"},
                {"text": "So why does the 'broke lottery winner' story spread so easily? Because the rare disaster stories are far more interesting than the boring truth of someone quietly investing their winnings.", "query": "graph growth"},
                {"text": "But that doesn't mean windfalls are risk-free -- stick around, because the real danger isn't bad luck. It's a very specific, very human mistake.", "query": "handshake business"},
                {"text": "The winners who do struggle almost always share one thing: no professional financial plan before the money arrived, and no clear idea of what a 'safe' monthly spend actually looks like.", "query": "office skyscraper"},
                {"text": "A two-million-dollar win sounds unlimited until you do the math on what monthly income it can safely generate for the rest of your life, which is usually far less than people assume.", "query": "gold bars"},
                {"text": "The real lesson isn't about lottery luck at all, it's that any sudden windfall, an inheritance, a bonus, a business sale, needs a plan before it needs a purchase. Have you ever come into unexpected money? What did you do with it?", "query": "calculator desk"},
                {"text": "The wealthy families who keep their money for generations do exactly this: they treat windfalls as capital to protect, not income to spend.", "query": "city financial district"},
                {"text": "If you want more myth-busting on money, backed by actual data instead of internet folklore, subscribe. And tell me: which money 'fact' should we fact-check next?", "query": "stock market chart"},
            ],
            "The simple index fund strategy that beats most experts": [
                {"text": "Every year, thousands of professional fund managers are paid millions of dollars to beat the stock market. Most of them fail, consistently.", "query": "stock market chart"},
                {"text": "According to S&P's own research, over a fifteen-year period, somewhere between eighty and ninety-five percent of actively managed funds failed to beat a simple market index.", "query": "graph growth"},
                {"text": "Not most years. Most funds, over the long run, meaning even skilled professionals with research teams and inside access rarely beat the market consistently.", "query": "office skyscraper"},
                {"text": "The alternative is almost embarrassingly simple: an index fund. Instead of picking winning stocks, it just buys a small piece of every company in the market and holds it.", "query": "coins stack"},
                {"text": "No high fees for stock picking. No manager trying to time the market. Just broad ownership of the economy's overall growth.", "query": "calculator desk"},
                {"text": "Stick around, because the reason this actually works is more interesting than 'it's cheaper,' it's about a hidden cost most people never calculate.", "query": "handshake business"},
                {"text": "That hidden cost is fees compounding over decades. A fund charging just one percent more per year can quietly eat away a huge share of your total lifetime returns, often tens of thousands of dollars over a career of investing.", "query": "bank building"},
                {"text": "Vanguard, the largest index fund company in the world, now manages over five trillion dollars, precisely because more investors have noticed this math.", "query": "city financial district"},
                {"text": "This isn't a hot stock tip, it's closer to a maintenance-free strategy that rewards patience over decades, not excitement over weeks. Do you invest in index funds, individual stocks, or neither yet?", "query": "gold bars"},
                {"text": "None of this guarantees profit, markets can still fall for years at a time, but it removes one of the biggest risks: paying high fees for underperformance.", "query": "graph growth"},
                {"text": "If you want more real financial research broken down simply, subscribe, no hype, just data. And tell me: what money topic should we tackle next?", "query": "stock market chart"},
            ],
        },
        "space_science": {
            "What would actually happen if you fell into a black hole": [
                {"text": "If you fell toward a black hole feet-first, your feet would start moving faster than your head, and that's before things get truly strange.", "query": "galaxy stars"},
                {"text": "This effect is called spaghettification, and it's not science fiction. It's simple physics: gravity pulls harder on whatever part of you is closer to the black hole.", "query": "nebula space"},
                {"text": "For a small, stellar-mass black hole, you'd start feeling this stretching thousands of kilometers before you even reached the point of no return, the event horizon.", "query": "planet surface"},
                {"text": "For a supermassive black hole, like the one at the center of our galaxy, the math flips entirely: you could cross the event horizon without feeling anything unusual at all.", "query": "milky way night sky"},
                {"text": "That's because a bigger black hole has a much gentler gravity gradient near its edge, the danger zone is simply much further inside.", "query": "telescope observatory"},
                {"text": "Keep watching, because what happens to how you perceive time during this fall is even weirder than the stretching.", "query": "astronaut spacewalk"},
                {"text": "From the outside, someone watching you fall would never actually see you cross the event horizon. You'd appear to freeze and fade, redder and dimmer, forever approaching but never arriving.", "query": "aurora borealis"},
                {"text": "But from your own perspective, falling in, none of that delay exists. You'd cross the horizon in totally normal, finite time, you just wouldn't be able to signal anyone about it afterward.", "query": "solar system"},
                {"text": "Physicists still don't agree on what happens at the very center, the singularity, where our current laws of physics simply stop working. If you could survive the trip and report back, what do you think you'd find at the center?", "query": "rocket launch"},
                {"text": "What we do know for certain is this: nothing, not light, not matter, not information as we understand it, comes back out once it crosses that boundary.", "query": "galaxy stars"},
                {"text": "If mind-bending real science is your thing, subscribe, we break down one genuinely wild concept every week, always grounded in actual physics. And tell me: which cosmic mystery should we explore next?", "query": "nebula space"},
            ],
            "The strangest planets we've discovered so far": [
                {"text": "Somewhere out there is a planet where it rains liquid rubies and sapphires, and the forecast never changes.", "query": "planet surface"},
                {"text": "That planet is WASP-121b, eight hundred eighty light-years away. It's tidally locked, meaning one side always faces its star at over 2,800 degrees Celsius.", "query": "telescope observatory"},
                {"text": "Metals that would be solid rock on Earth vaporize on its scorching day-side, then drift to the cooler night-side and condense right back into solid crystals, falling as gem-like rain.", "query": "nebula space"},
                {"text": "Then there's 55 Cancri e, a planet so rich in carbon that scientists believe up to a third of its entire mass could be crystallized into diamond.", "query": "galaxy stars"},
                {"text": "Its surface temperature exceeds 2,700 degrees Celsius, exactly the punishing environment needed to compress carbon into diamond form at that kind of scale.", "query": "solar system"},
                {"text": "And the weirdest one on this list isn't scorching hot at all, stick around for the planet made of glass.", "query": "aurora borealis"},
                {"text": "HD 189733b is a deep blue gas giant where silicate particles are whipped through the atmosphere at seven thousand kilometers per hour, fast enough to shatter anything in their path.", "query": "milky way night sky"},
                {"text": "Those particles are essentially glass, meaning this planet experiences sideways storms of shattered glass shards moving faster than a rifle bullet.", "query": "rocket launch"},
                {"text": "Every one of these worlds was found using tiny dips in starlight or minuscule wobbles in a star's motion, we've never actually seen most of them directly. Which of these three would you least want to visit?", "query": "astronaut spacewalk"},
                {"text": "As telescopes get more powerful, we keep finding planets stranger than anything science fiction imagined first, reality just keeps winning.", "query": "planet surface"},
                {"text": "Subscribe if strange real science excites you, new discoveries broken down every week. And tell me: which planet should we cover in full detail next?", "query": "galaxy stars"},
            ],
        },
    },
    # ----------------------------------------------------------------- #
    # PERSIAN (فارسی)
    # ----------------------------------------------------------------- #
    "fa": {
        "psychology": {
            "Why we procrastinate even when we know better": [
                {"text": "دقیقاً می‌دونی الان باید چیکار کنی. با این حال همین‌جا نشستی و انجامش نمی‌دی.", "query": "person thinking"},
                {"text": "سال‌ها روانشناس‌ها فکر می‌کردن تعلل یعنی تنبلی یا بی‌نظمی توی مدیریت زمان. تحقیقات جدید می‌گه این تقریباً کاملاً اشتباهه.", "query": "clock ticking desk"},
                {"text": "دکتر تیم پیچیل که سال‌ها روی همین رفتار تحقیق کرده، به یه نتیجه‌ی عجیب رسید: تعلل ربطی به تقویم شما نداره، ربط مستقیم به احساسات شما داره.", "query": "person stressed desk"},
                {"text": "وقتی یه کار باعث اضطراب، خستگی یا احساس ناامنی توی شما می‌شه، مغزتون یه واکنش خیلی قدیمی و خودکار نشون می‌ده: دنبال هر چیزی می‌گرده که همین الان اون حس بد رو از بین ببره.", "query": "human brain"},
                {"text": "برای همینه که چک کردن گوشی خیلی راحت‌تر از باز کردن اون فایل کاریه. مغزتون تنبل نیست، داره حالتون رو تنظیم می‌کنه.", "query": "phone scrolling hand"},
                {"text": "تا آخر بمونید، چون راه‌حل این موضوع چیزی نیست که توی اکثر ویدیوهای انگیزشی می‌شنوید، و وقتی ببینیدش دیگه نمی‌تونید نادیده‌اش بگیرید.", "query": "person thinking"},
                {"text": "اپلیکیشن‌های مدیریت زمان فرض می‌کنن مشکل، برنامه‌ریزیه. ولی اگه مشکل واقعی احساسیه، یه تقویم بهتر نجاتتون نمی‌ده.", "query": "journal writing"},
                {"text": "محققا به یه راهکار به اسم «ترمیم حس» رسیدن: یاد بگیرید چند دقیقه با اون حس ناخوشایند بمونید، بدون اینکه فوراً ازش فرار کنید.", "query": "meditation calm"},
                {"text": "یه نکته‌ی عجیب: بخشیدن خودتون بابت تعلل دفعه‌ی قبل، باعث می‌شه دفعه‌ی بعد سریع‌تر کار رو شروع کنید. تحقیقات روی دانشجوها این رو نشون داد. شما تا حالا واقعاً خودتون رو بابت تعلل بخشیدید، یا همیشه سرزنش می‌کنید؟ تو کامنت‌ها بگید.", "query": "silhouette sunset"},
                {"text": "دفعه‌ی بعد که دیدید دارید یه کاری رو کنار می‌ذارید، به جای پرسیدن «چرا اینقدر تنبلم»، از خودتون بپرسید «الان واقعاً دارم از چه حسی فرار می‌کنم؟»", "query": "walking alone nature"},
                {"text": "اگه این ویدیو نگاهتون به تعلل خودتون رو عوض کرد، دنبال کنید، هر هفته یه یافته‌ی روانشناسی رو بررسی می‌کنیم که واقعاً رفتارتون رو عوض می‌کنه، نه فقط فکرتون رو. و بگید: کدوم کار رو بیشتر از همه به تعویق انداختید؟", "query": "sunset silhouette"},
            ],
        },
        "history_mystery": {
            "The unsolved mystery of the Mary Celeste": [
                {"text": "سال ۱۸۷۲ یه کشتی وسط اقیانوس اطلس پیدا شد، کاملاً رها شده؛ بار دست‌نخورده، غذا هنوز روی میز، ولی حتی یه نفر هم روش نبود.", "query": "old map"},
                {"text": "کشتی مری سلست هفتم نوامبر از نیویورک به مقصد جنووای ایتالیا حرکت کرده بود، با ده نفر سرنشین و هزار و هفتصد بشکه الکل خام.", "query": "historic city"},
                {"text": "یه ماه بعد، یه کشتی بریتانیایی به اسم دی‌گراسیا این کشتی رو دید که با بادبان نیمه‌باز، تنها روی آب می‌چرخه.", "query": "old ship ocean"},
                {"text": "وقتی سوارش شدن، همه‌چیز عادی به نظر می‌رسید. وسایل شخصی و حتی چرخ خیاطی سرجاش بود؛ ولی قایق نجات و همه‌ی سرنشین‌ها غیب شده بودن.", "query": "archive documents"},
                {"text": "هیچ نشونه‌ای از دعوا، خون، یا یادداشتی نبود. فقط یه کشتی خالی، توی هوای آروم، کاملاً سالم.", "query": "old book pages"},
                {"text": "تحقیقات رسمی چیزی پیدا نکرد، و دقیقاً همینه که این پرونده رو تا امروز زنده نگه داشته. تا آخر ویدیو بمونید، چون معتبرترین تئوری خیلی عجیب‌تر از هر افسانه‌ایه.", "query": "castle aerial"},
                {"text": "معتبرترین تئوری امروزی به خود محموله برمی‌گرده: الکل خام. اگه چندتا بشکه نشتی می‌کرد، بخارش می‌تونست زیر عرشه جمع بشه.", "query": "museum artifact"},
                {"text": "کاپیتان بریگز، یه ملوان باتجربه و محتاط، احتمالاً فکر کرده کشتی داره منفجر می‌شه و به همه دستور داده سوار قایق نجات بشن؛ با طنابی به کشتی وصل، برای برگشت بعد از رفع خطر.", "query": "statue monument"},
                {"text": "اگه اون طناب پاره می‌شد یا موج قایق رو اشتباه می‌گرفت، ده نفر می‌تونستن توی چند دقیقه گم بشن، درحالی که مری سلست بدون اون‌ها آروم به راهش ادامه می‌داد. شما فکر می‌کنید اون روز واقعاً چی اتفاق افتاد؟", "query": "foggy forest night"},
                {"text": "احتمالاً هیچ‌وقت با قطعیت نمی‌فهمیم. خود کشتی مری سلست سیزده سال دیگه هم دریانوردی کرد، تا اینکه عمداً توی یه کلاهبرداری بیمه غرق شد، یه چرخش عجیب دیگه توی داستانش.", "query": "ancient ruins"},
                {"text": "اگه عاشق معماهای حل‌نشده‌ی واقعی هستید، دنبال کنید، هر هفته یه پرونده‌ی جدید، همیشه بر اساس اسناد واقعی تاریخی. بگید کدوم راز چند دهه‌ای رو بعدی بررسی کنیم؟", "query": "old map"},
            ],
        },
        "true_crime": {
            "The cold case that was solved decades later by DNA": [
                {"text": "بیش از سی سال، یه مرد حداقل دوازده قتل و ده‌ها تجاوز توی کالیفرنیا مرتکب شد، و بدون هیچ ردی ناپدید شد.", "query": "police tape night"},
                {"text": "بهش می‌گفتن قاتل گلدن استیت. بین سال‌های ۱۹۷۶ تا ۱۹۸۶ کل محله‌ها رو به وحشت انداخت، بعد ردش کاملاً گم شد.", "query": "detective office"},
                {"text": "سه دهه، دی‌ان‌ای‌اش توی انبار مدارک بود، بدون تطابق با هیچ پایگاه داده‌ی جنایی. نه اسمی، نه چهره‌ای، نه مظنونی.", "query": "old case files"},
                {"text": "بعد، سال ۲۰۱۸، یه کارآگاه بازنشسته یه روش امتحان کرد که تا اون موقع برای همچین پرونده‌ای استفاده نشده بود: یه سایت رایگان شجره‌نامه.", "query": "magnifying glass evidence"},
                {"text": "به جای جستجو توی پایگاه‌های پلیس، پروفایل دی‌ان‌ای صحنه‌ی جرم رو توی سایتی به اسم جی‌ای‌دی‌مچ آپلود کردن، سایتی که مردم عادی برای پیدا کردن فامیل‌های دورشون استفاده می‌کنن.", "query": "close up eyes"},
                {"text": "چیزی که بعدش اتفاق افتاد، برای همیشه روش حل پرونده‌های سرد رو عوض کرد، تا آخر بمونید، چون نقطه‌ی عطف واقعی چیزی نیست که تو اکثر مستندهای جنایی می‌شنوید.", "query": "city noir night"},
                {"text": "دی‌ان‌ای مستقیم با خود قاتل تطابق نداشت. با فامیل‌های دورش تطابق داشت که هیچ ربطی به جنایت‌ها نداشتن، ولی شجره‌نامه‌شون کارآگاه‌ها رو به یه شاخه، و بعد یه اسم، رسوند.", "query": "rain window night"},
                {"text": "اون اسم جوزف دی‌آنجلو بود، یه افسر پلیس بازنشسته که آروم توی حومه‌ی ساکرامنتو زندگی می‌کرد. کارآگاه‌ها مخفیانه دی‌ان‌ای دورریخته‌اش رو جمع کردن و با نمونه‌های چند دهه قبل مقایسه کردن.", "query": "flashlight dark room"},
                {"text": "تطابق داشت. دهه‌ها فرار، با یه سایت سرگرمی یکی از فامیل‌ها تموم شد. می‌دونستید سایت‌های عمومی دی‌ان‌ای ده‌ها پرونده‌ی سرد دیگه رو هم حل کردن؟ فکر می‌کنید باید محدودیتی برای استفاده از این روش باشه، یا گرفتن قاتل‌ها ارزشش رو داره؟", "query": "courtroom"},
                {"text": "دی‌آنجلو سال ۲۰۲۰ به سیزده قتل اعتراف کرد. همون تکنیکی که اونو گرفت، بعدش برای حل ده‌ها پرونده‌ی سرد دیگه هم استفاده شد.", "query": "old case files"},
                {"text": "اگه این‌جور پرونده‌ها براتون جذابه، دنبال کنید، هر قسمت بر اساس گزارش‌های واقعیه، نه شایعه. بگید کدوم پرونده‌ی سرد رو بعدی بررسی کنیم؟", "query": "detective office"},
            ],
        },
        "luxury_lifestyle": {
            "Inside the world's most expensive private islands": [
                {"text": "بعضی جزیره‌های خصوصی، هر هکتارشون گرون‌تر از یه بلوک کامل توی منهتنه.", "query": "yacht ocean"},
                {"text": "مثلاً جزیره‌ی بل توی باهاما: ۳۴۹ هکتار، حدود صد میلیون دلار فروخته شده، یعنی نزدیک به سیصد هزار دلار برای هر هکتار شن و نخل.", "query": "private jet"},
                {"text": "در مقابلش، جزیره‌ی لاناییِ هاوایی که لری الیسون تقریباً کاملاً برای خودش خرید: نود هزار هکتار با حدود سیصد میلیون دلار، یعنی هر هکتار فقط سه هزار و سیصد دلار.", "query": "penthouse view"},
                {"text": "همون سطح از خریدار، ولی قیمت‌های کاملاً متفاوت برای هر هکتار، چون توی جزیره‌های خصوصی فقط زمین نمی‌خرید؛ نزدیکی به همه‌چیز دیگه رو می‌خرید.", "query": "luxury car"},
                {"text": "الیسون فقط لاناایی رو به عنوان یه غنیمت نخرید. کل زیرساختش رو از نو ساخت، مزارع خورشیدی، سیستم‌های صرفه‌جویی آب، مزارع ارگانیک برای هتل‌های خودش.", "query": "city skyline night"},
                {"text": "و این دقیقاً داستان واقعیِ پشت جزیره‌های میلیاردرهاست، به‌ندرت فقط یه خونه‌ی ساحلیه. تا آخر بمونید برای عجیب‌ترین موردی که تو این لیست هست.", "query": "fine dining"},
                {"text": "توی سن‌پترزبورگ، رومن آبراموویچ جزیره‌ی نیوهلند رو، که یه زمانی یه کارخانه‌ی کشتی‌سازی نظامی قرن هجدهمی بود، به یه مرکز فرهنگی چهارصد میلیون دلاری تبدیل کرد، با نمایشگاه‌های هنری و کنسرت‌های روباز.", "query": "designer fashion"},
                {"text": "این خریدها واقعاً فرار از دنیا نیستن. ساختن یه نسخه‌ی کاملاً خصوصی از دنیا، با شرایط خودتون، بدون پاسخگویی به کسیه.", "query": "watch closeup"},
                {"text": "اگه پول واقعاً مشکلی نبود، دوست داشتید یه جزیره‌ی کامل فقط برای خودتون داشته باشید، یا این حس تنهایی بیشتر از لاکچری بودن داره؟ صادقانه تو کامنت‌ها بگید.", "query": "champagne pour"},
                {"text": "چون هزینه‌ی نگهداری این جزیره‌ها، کارکنان، انرژی، نگهداری، امنیت، معمولاً توی چند سال اول با قیمت خرید اولیه برابری می‌کنه.", "query": "yacht ocean"},
                {"text": "دنبال کنید برای نگاه‌های بیشتر به نحوه‌ی واقعیِ خرج کردن ثروتمندهای دنیا، نه نسخه‌ی خیالیش، بلکه اعداد واقعی. بگید کدوم خرید میلیاردری رو بعدی بررسی کنیم؟", "query": "private jet"},
            ],
        },
        "finance": {
            "Why most lottery winners go broke within years": [
                {"text": "احتمالاً شنیدید که هفتاد درصد برنده‌های لاتاری آخرش ورشکست می‌شن. نکته‌ی جالب اینه: این آمار احتمالاً از اصل ساختگیه.", "query": "stock market chart"},
                {"text": "این عدد رو به یه سازمان به اسم بنیاد ملی آموزش مالی نسبت می‌دن، ولی خود اون سازمان رسماً اعلام کرده هیچ‌وقت همچین تحقیقی انجام نداده.", "query": "calculator desk"},
                {"text": "سال ۲۰۲۶ خبرنگارها ۳۱ نفر از برنده‌های واقعی پاوربال رو که بیش از پنجاه میلیون دلار برده بودن، برای ده سال دنبال کردن.", "query": "coins stack"},
                {"text": "نتیجه تقریباً کاملاً برخلاف این افسانه بود: بیشترشون بعد از ده سال هنوز میلیونر بودن، زندگی عادی داشتن، به خیریه کمک می‌کردن، از تیتر خبرها دور می‌موندن.", "query": "bank building"},
                {"text": "پس چرا داستان «برنده‌ی ورشکسته‌ی لاتاری» اینقدر راحت پخش می‌شه؟ چون داستان‌های نادر و فاجعه‌بار خیلی جذاب‌تر از حقیقت خسته‌کننده‌ی سرمایه‌گذاری آرومن.", "query": "graph growth"},
                {"text": "ولی این یعنی پول ناگهانی هیچ خطری نداره؛ تا آخر بمونید، چون خطر واقعی یه اشتباه خیلی مشخص و انسانیه.", "query": "handshake business"},
                {"text": "برنده‌هایی که واقعاً دچار مشکل می‌شن، تقریباً همیشه یه چیز مشترک دارن: هیچ برنامه‌ی مالی حرفه‌ای قبل از رسیدن پول نداشتن و نمی‌دونستن یه خرج ماهانه‌ی «امن» واقعاً چقدره.", "query": "office skyscraper"},
                {"text": "برد دو میلیون دلاری شاید نامحدود به نظر برسه، تا وقتی حساب کنید این پول چقدر درآمد ماهانه‌ی امن برای بقیه‌ی عمر ایجاد می‌کنه، که معمولاً خیلی کمتر از تصور مردمه.", "query": "gold bars"},
                {"text": "درس واقعی اصلاً ربطی به شانس لاتاری نداره؛ هر پول ناگهانی، ارثیه، پاداش، فروش یه کسب‌وکار، قبل از خرج شدن به یه برنامه نیاز داره. شما تا حالا پول غیرمنتظره‌ای بهتون رسیده؟ باهاش چیکار کردید؟", "query": "calculator desk"},
                {"text": "خانواده‌های ثروتمندی که پولشون رو نسل به نسل حفظ می‌کنن، دقیقاً همین کارو می‌کنن: پول ناگهانی رو سرمایه‌ای برای حفاظت می‌بینن، نه درآمدی برای خرج کردن.", "query": "city financial district"},
                {"text": "اگه دوست دارید باورهای غلط مالی رو با داده‌ی واقعی بررسی کنیم نه شایعه‌های اینترنتی، دنبال کنید. بگید کدوم «حقیقت» مالی رو بعدی بررسی کنیم؟", "query": "stock market chart"},
            ],
        },
        "space_science": {
            "What would actually happen if you fell into a black hole": [
                {"text": "اگه با پا جلو به سمت یه سیاهچاله سقوط کنید، پاهاتون سریع‌تر از سرتون حرکت می‌کنن، و این فقط شروع ماجراست.", "query": "galaxy stars"},
                {"text": "به این پدیده «اسپاگتی‌شدن» می‌گن، و اصلاً تخیلی نیست. فیزیک ساده‌ست: گرانش روی هر بخشی از بدنتون که به سیاهچاله نزدیک‌تره، قوی‌تر عمل می‌کنه.", "query": "nebula space"},
                {"text": "برای یه سیاهچاله‌ی کوچیک، این کشیده‌شدن رو هزاران کیلومتر قبل از رسیدن به نقطه‌ی بی‌بازگشت، یعنی افق رویداد، حس می‌کنید.", "query": "planet surface"},
                {"text": "ولی برای یه سیاهچاله‌ی ابرپرجرم، مثل اونی که وسط کهکشان ماست، ماجرا برعکس می‌شه: می‌تونید از افق رویداد رد بشید بدون اینکه هیچ حس غیرعادی‌ای داشته باشید.", "query": "milky way night sky"},
                {"text": "چون یه سیاهچاله‌ی بزرگ‌تر، شیب گرانشی خیلی ملایم‌تری نزدیک لبه‌اش داره، منطقه‌ی خطرناک خیلی عمیق‌تر توی سیاهچاله‌ست.", "query": "telescope observatory"},
                {"text": "تا آخر بمونید، چون اتفاقی که برای درک شما از زمان توی این سقوط میفته، حتی از کشیده‌شدن هم عجیب‌تره.", "query": "astronaut spacewalk"},
                {"text": "کسی که از بیرون شما رو در حال سقوط ببینه، هیچ‌وقت واقعاً نمی‌بینه که از افق رویداد رد بشید. به نظر میاد یخ می‌زنید و کم‌رنگ می‌شید، برای همیشه در حال نزدیک‌شدن ولی هیچ‌وقت نرسیدن.", "query": "aurora borealis"},
                {"text": "ولی از دید خودتون، هیچ‌کدوم از این تأخیر وجود نداره. توی یه زمان کاملاً عادی و محدود از افق رد می‌شید، فقط دیگه نمی‌تونید به کسی خبر بدید.", "query": "solar system"},
                {"text": "فیزیکدان‌ها هنوز روی اینکه دقیقاً وسط سیاهچاله، یعنی تکینگی، چه خبره توافق ندارن؛ چون قوانین فیزیک ما اونجا کار نمی‌کنن. اگه می‌تونستید زنده بمونید و گزارش بدید، فکر می‌کنید وسطش چی پیدا می‌کردید؟", "query": "rocket launch"},
                {"text": "چیزی که با قطعیت می‌دونیم اینه: هیچی، نه نور، نه ماده، نه اطلاعات به شکلی که ما می‌شناسیم، بعد از رد شدن از اون مرز، دوباره بیرون نمیاد.", "query": "galaxy stars"},
                {"text": "اگه علم واقعی و ذهن‌درگیرکن دوست دارید، دنبال کنید، هر هفته یه مفهوم عجیب رو بر اساس فیزیک واقعی بررسی می‌کنیم. بگید کدوم راز کیهانی رو بعدی بررسی کنیم؟", "query": "nebula space"},
            ],
        },
    },
}


def get_script(niche_key: str, language: str, topic: str) -> list:
    """Exact-match lookup. Returns [] if no curated script exists for this
    (language, niche_key, topic) combination -- the caller (ScriptWriter)
    falls through to the generic offline template in that case."""
    return list(CONTENT_BANK.get(language, {}).get(niche_key, {}).get(topic, []))


def has_script(niche_key: str, language: str, topic: str) -> bool:
    return bool(CONTENT_BANK.get(language, {}).get(niche_key, {}).get(topic))


def available_topics(niche_key: str, language: str) -> list:
    """Topics with a real, curated, fact-checked script for this niche and
    language -- used by NicheAnalyzer to prefer these over other evergreen
    topics when it has to fall back to the evergreen list (still a real
    evergreen topic either way; this only affects which ONE gets picked)."""
    return list(CONTENT_BANK.get(language, {}).get(niche_key, {}).keys())
