"""Write the demo flows in samples/flows/.

Each flow is a folder to drop into the upload page in one go.

- happy-path/: four documents on one theme (AI and the stock market, November 2026)
  that should all analyse cleanly. One of them carries its crucial figures in an
  image only. The facts come from public reporting, and each document names its
  sources. Write only what a named source says.
- failure-path/: documents on a different theme, one of which is cut off mid-file and
  is rejected at upload. Everything in these is invented.
"""

from pathlib import Path

from evals.builder import render_pages

_NOTICE = "Illustrative document for software testing. Every figure here is invented."
_SAMPLE = (
    "Sample document for software testing, compiled from the public reporting named here. "
    "Check the sources before relying on any figure. Not investment advice."
)

# --- happy path: AI and the stock market, November 2026 ---------------------------------

_NVIDIA = [
    (
        "NVIDIA stability check. Compiled 20 November 2026 from public reporting. "
        "Results. NVIDIA reported third-quarter fiscal 2027 results on 17 November, for "
        "the quarter that ended 25 October. Revenue was $115.8 billion, up 103 percent "
        "from a year earlier and up 20 percent on the previous quarter. Data Center "
        "revenue was $107.6 billion, up 110 percent from a year earlier. Within Data "
        "Center, hyperscale customers contributed $60.1 billion and the AI clouds, "
        "industrial and enterprise group $47.5 billion. GAAP gross margin was 74.8 "
        "percent. Vera Rubin NVL72 racks began shipping, and on the earnings call the "
        "interim CEO said the platform made nearly $20 billion of revenue in its first "
        "quarter of production shipments."
    ),
    (
        "Outlook. For the fourth quarter, which has an extra week, NVIDIA guided revenue "
        "to $130.0 billion, plus or minus 3 percent, with gross margin of 71.0 to 72.0 "
        "percent. The outlook assumes no Data Center compute revenue from China. On the "
        "call the interim CEO said fiscal 2028 revenue should grow about 75 percent, up "
        "from a prior 70 percent, and that the fourth quarter should be the low point "
        "for gross margin before it recovers to 72 to 73 percent in fiscal 2028. "
        "Leadership. On 12 November NVIDIA announced that Jensen Huang had resigned as "
        "president, chief executive and director, effective immediately. Chief financial "
        "officer Colette Kress is interim CEO and stays CFO, and Harvey Jones was named "
        "the company's first chair of the board. The board is searching for a permanent "
        "CEO and will consider internal and external candidates. The announcement gave "
        "no reason. Press reports linked the resignation to allegations about his "
        "personal conduct and to questions about China-related exposure. The board has "
        "said it has no reason to believe national security was compromised."
    ),
    (
        "Concentration and demand. Hyperscale customers were about 56 percent of Data "
        "Center revenue in the quarter ($60.1 billion of $107.6 billion). The interim CEO "
        "said she expects the major frontier labs to contribute about 15 percent of Data "
        "Center revenue this year, and that cloud industry backlog is $2.5 trillion, up "
        "from $2 trillion three months earlier. Policy. NVIDIA shipped $2.4 billion of "
        "Data Center Hopper products to China in the quarter, and its guidance includes "
        "none. This week the U.S. Commerce Department tightened rules meant to stop China "
        "reaching U.S.-made chips remotely through other countries, and NVIDIA said it is "
        "still studying them. Governance. WIRED reports that NVIDIA and its former CEO "
        "face several shareholder lawsuits over statements about his dealings. Reading. "
        "Operating results are strong, and guidance is above the $125.1 billion analyst "
        "average (LSEG, via CNBC). The open questions are governance, the search for a "
        "CEO, export rules, and how customers pay for their spending. Sources: NVIDIA "
        "press releases of 12 and 17 November 2026, NVIDIA CFO commentary (SEC filing), "
        "NVIDIA Q3 FY27 earnings call transcript, CNBC, Al Jazeera, WIRED. " + _SAMPLE
    ),
]

_ANTHROPIC = [
    (
        "Anthropic IPO debrief. Compiled 19 November 2026 from public reporting. Terms. "
        "On 18 November Anthropic priced its initial public offering at $83.00 a share, "
        "above the $70 to $78 range it had marketed. It sold 980 million Class A shares, "
        "about 19 percent more than the 825 million first planned. Of these, 956,351,354 "
        "were sold by Anthropic and 23,648,646 by selling stockholders. The offering "
        "raised $81.3 billion, the largest IPO on record, ahead of SpaceX's debut in "
        "June. A separate $26 billion private placement of non-voting shares brings the "
        "total raised to $107.3 billion. The deal values Anthropic at about $1.5 "
        "trillion fully diluted, or about $1.1 trillion before options and other "
        "securities. The shares trade on the Nasdaq under the symbol ANT."
    ),
    (
        "First day and financials. ANT opened at $111.50 on 19 November, reached a high "
        "of $115.10 and closed at $97.17, up 17 percent on the offer price, for a fully "
        "diluted market value of about $1.8 trillion (CNBC). The Nasdaq fell 2.2 percent "
        "that day. Figures from the filing, as reported by Reuters: revenue was $17 "
        "billion in the third quarter and $33.24 billion for the first nine months of "
        "2026, against $2.55 billion a year earlier. Usage-based revenue was $26.3 "
        "billion, 79 percent of the nine-month total, and subscriptions $6.9 billion. "
        "Anthropic spent nearly $9 billion on computing capacity and infrastructure in "
        "the first half of 2026, nearly four times the year before. It reported an "
        "operating loss of $567 million for the latest quarter, against operating income "
        "of $974 million in the one before. The net loss was $23.3 billion, down from "
        "$66.3 billion, including non-operating items on bonds that convert into its "
        "shares. Reuters notes that Anthropic faces questions about its outlook and its "
        "ability to sustain rapid growth as competition intensifies. Sources: Anthropic "
        "press release of 18 November 2026, Reuters, NPR, CNBC, AP, The Financial "
        "Express. " + _SAMPLE
    ),
]

_COMPETITORS = [
    (
        "AI model competitors. Compiled 20 November 2026 from public reporting. OpenAI. "
        "OpenAI raised $122 billion in March at a valuation of $852 billion. On 6 "
        "November Bloomberg reported a new round at a $1.25 trillion valuation that had "
        "raised another $11 billion, with talks to lift the total to $20 billion. OpenAI "
        "had first hoped to raise up to $30 billion at $1.4 trillion, before tech stocks "
        "fell (The Verge). OpenAI has pitched investors on annualised revenue of $50 "
        "billion after launching GPT-6 Astra, and expects $70 billion by the end of 2026 "
        "(Reuters, 19 October). The Information reports $10 billion of sales in the "
        "third quarter, against $17 billion for Anthropic. OpenAI has not published "
        "financial statements. It filed confidentially for an IPO but is reported to "
        "have deferred it to next year, and Sam Altman has said it will not rush before "
        "it can make more confident claims about safety."
    ),
    (
        "Google and the rest. The Menlo Ventures report State of Enterprise AI, "
        "published on 3 November, found that Google fell furthest in enterprise API "
        "spending this year. Its Gemini 3 Pro put it at the frontier in November 2025, "
        "but Menlo says Google has not matched the flagship models from Anthropic and "
        "OpenAI since, and its spend now leans toward cheaper Flash models. Anthropic "
        "widened its lead on the strength of its Opus models, which are strong at "
        "long-horizon tasks and coding. OpenAI also gained, helped by its GPT-5.6 models "
        "in July and GPT-6 in September. Near-frontier models, xAI's Grok 4.7 and "
        "open-source models such as Moonshot's Kimi K3, DeepSeek's V4 and Z AI's "
        "GLM-5.3, approach frontier performance at a fraction of the price, but together "
        "they hold a small share of spend. Menlo expects the concentration among the "
        "labs to ease as capabilities mature and application companies take them to "
        "new markets."
    ),
    (
        "Where the money is. Menlo surveyed nearly 400 U.S. enterprise decision-makers "
        "between 8 and 26 September 2026 and estimated each lab's share of enterprise "
        "spending on LLM APIs. The figure below shows the split. The words on this page "
        "do not give the shares. They are on the figure. Menlo's reading is that the "
        "market is increasingly a two-horse race, and that model capability, not price, "
        "is the deciding factor. Sources: Menlo Ventures, 2026: The State of Enterprise "
        "AI (3 November 2026), The Verge, Reuters, The Information, The Financial "
        "Express. " + _SAMPLE
    ),
]

_WRAP = (
    "Market wrap. Week to 20 November 2026, compiled 21 November from public "
    "reporting. US stocks had their worst week in years. The Nasdaq Composite lost "
    "about 10 percent, its largest one-week drop in more than six years, and closed "
    "Friday at 22,617.73. The S&P 500 fell 8.6 percent to 6,910.39 and is 10 percent "
    "below its record close, in correction territory. The Dow lost 8 percent, its "
    "worst week since March 2020. Chip stocks led the fall. NVIDIA lost 14 percent on "
    "Friday and 23 percent on the week, after Reuters reported that the SEC is "
    "exploring possible accounting issues at the company. AMD and Micron each fell "
    "about 13 to 14 percent on Friday. Anthropic fell 8.5 percent on Friday, after its "
    "17 percent gain on debut. Anthropic closed its IPO on 20 November. With the "
    "underwriters' option exercised in full, the offering raised about $93.5 billion "
    "gross, and about $119.5 billion with the private placement. OpenAI's latest "
    "private-market valuation is $1.27 trillion, according to Nasdaq Private Market. "
    "The Federal Reserve meets on 8 and 9 December. Futures priced roughly a 91 to 94 "
    "percent chance of a quarter-point rate hike, not a cut. Sources: CNBC, Yonhap "
    "Infomax, Anthropic press release of 20 November 2026, Yahoo Finance. " + _SAMPLE
)

# --- failure path: Singapore housing -----------------------------------------------------

_HDB = [
    (
        "Harbourview Property Brief. HDB resale market. 14 November 2026. Resale flat "
        "prices rose 1.3 percent in the third quarter of 2026, the slowest rise in six "
        "quarters, according to the quarterly index. The median four-room flat sold for "
        "$640,000 and the median five-room flat for $760,000. About 6,400 resale flats "
        "changed hands in the quarter, down from 7,100 a year earlier."
    ),
    (
        "Why growth is slowing. Agents say higher cash proceeds from sellers have run "
        "ahead of buyers' budgets, and more buyers are waiting for new flats under the "
        "Build-To-Order scheme instead. Mortgage rates near 3.2 percent have also held "
        "back upgraders. Million-dollar resale flats were 38 of the 6,400 deals, the same "
        "count as the previous quarter. Mature estates still lead the price gains. " + _NOTICE
    ),
]

_BTO = (
    "Harbourview Property Brief. Build-To-Order launch. 18 November 2026. The "
    "November launch offers 4,800 flats across four estates, with a wait of about "
    "three years. Applications for the Tampines launch ran at four times the supply of "
    "four-room flats, down from five times in the last round. Prices for a four-room flat "
    "start at $410,000 in non-mature estates. The government says it will keep launches "
    "at a similar size next year. " + _NOTICE
)

_CONDO = (
    "Harbourview Property Brief. Private condominium rentals. 16 November 2026. Condo "
    "rents rose 0.8 percent in October, after a flat September. The median rent for a "
    "two-bedroom unit in the central region is $5,200 a month. Landlords report more "
    "enquiries from families than from expatriate singles. Vacancy is 5.9 percent, near "
    "its five-year average, and about 14,000 new private homes are due to be completed "
    "next year. " + _NOTICE
)

_COOLING = [
    (
        "Harbourview Property Brief. Review of the cooling measures. 20 November 2026. "
        "The government has kept the additional buyer's stamp duty and the loan limits "
        "unchanged since the last review. Analysts expect no change before the budget. "
        "The seller's stamp duty still applies to homes sold within three years of "
        "purchase."
    ),
    (
        "What buyers should watch. A change in the loan-to-value cap would move the "
        "most active segment first, which is upgraders buying a private home while "
        "selling a flat. " + _NOTICE
    ),
]

_KEEP_FRACTION = 0.5


def write_flows(root: Path) -> None:
    happy = root / "happy-path"
    failure = root / "failure-path"
    happy.mkdir(parents=True, exist_ok=True)
    failure.mkdir(parents=True, exist_ok=True)

    (happy / "nvidia-stability-outlook.pdf").write_bytes(
        render_pages([{"text": page} for page in _NVIDIA])
    )
    (happy / "anthropic-ipo-debrief.pdf").write_bytes(
        render_pages([{"text": page} for page in _ANTHROPIC])
    )
    (happy / "ai-competitor-landscape.pdf").write_bytes(
        render_pages(
            [
                {"text": _COMPETITORS[0]},
                {"text": _COMPETITORS[1]},
                {
                    "text": _COMPETITORS[2],
                    "infographic": {
                        "title": "Enterprise LLM API spend by lab, 2026",
                        "note": "Share of spend. Source: Menlo Ventures survey, September 2026.",
                        "parts": [
                            {
                                "label": "Anthropic",
                                "share": 0.55,
                                "value": "55%",
                                "color": "#1f4e79",
                            },
                            {
                                "label": "OpenAI",
                                "share": 0.31,
                                "value": "31%",
                                "color": "#4f81bd",
                            },
                            {
                                "label": "Google",
                                "share": 0.09,
                                "value": "9%",
                                "color": "#8fafc4",
                            },
                            {
                                "label": "All others",
                                "share": 0.05,
                                "value": "5%",
                                "color": "#c5d5e0",
                            },
                        ],
                    },
                },
            ]
        )
    )
    (happy / "market-wrap.pdf").write_bytes(render_pages([{"text": _WRAP}]))

    (failure / "hdb-resale-prices.pdf").write_bytes(render_pages([{"text": page} for page in _HDB]))
    (failure / "bto-launch.pdf").write_bytes(render_pages([{"text": _BTO}]))
    (failure / "condo-rentals.pdf").write_bytes(render_pages([{"text": _CONDO}]))
    # Cut off mid-file, so upload rejects it as an invalid PDF.
    whole = render_pages([{"text": page} for page in _COOLING])
    (failure / "cooling-measures-review.pdf").write_bytes(
        whole[: max(1, int(len(whole) * _KEEP_FRACTION))]
    )


def main() -> None:
    write_flows(Path(__file__).resolve().parents[2] / "samples" / "flows")


if __name__ == "__main__":
    main()
