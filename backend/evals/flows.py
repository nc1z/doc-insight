"""Write the demo flows in samples/flows/.

Each flow is a folder to drop into the upload page in one go.

- happy-path/: four documents on one theme that should all analyse cleanly. One of
  them carries its crucial figures in an image only.
- failure-path/: documents on a different theme, one of which is cut off mid-file and
  is rejected at upload.

Everything here is invented for testing. Companies are real names, but none of the
figures, forecasts, dates, or people are real.
"""

from pathlib import Path

from evals.builder import render_pages

_NOTICE = "Illustrative document for software testing. Every figure here is invented."

# --- happy path: AI and the stock market -------------------------------------------------

_NVIDIA = [
    (
        "Cedar Ridge Capital. Equity note. NVIDIA, ticker NVDA US Equity. Stability review. "
        "18 November 2026. Author: Priya Shah. Rating: Overweight. Price target $240, last "
        "price $198. The desk's view is that NVIDIA's earnings are more stable than its share "
        "price suggests. We estimate FY27 data-center revenue of $210 billion, and a gross "
        "margin of 74 percent. Four hyperscale buyers placed most of the orders, and their "
        "published capital budgets for 2027 are higher, not lower, than for 2026. "
        "Demand is visible two to three quarters out."
    ),
    (
        "Supply and margins. Advanced packaging capacity was the limit in 2025 and is no "
        "longer the limit now. High-bandwidth memory is still tight, and its price is the "
        "main threat to a 74 percent gross margin. We model a range of 73 to 75 percent. "
        "Inventory is 95 days, up from 80 a year ago, which the desk reads as a deliberate "
        "build ahead of the next platform and not as unsold stock. The four largest buyers "
        "were 52 percent of data-center revenue. A cut at any one of them moves the year. "
        "Free cash flow is on track for $120 billion."
    ),
    (
        "What would change the view. First, custom chips from the large buyers. They are "
        "real, but the desk finds they take training share slowly and leave inference "
        "growing for everyone. Second, export limits on China, which are now about 4 percent "
        "of revenue and no longer a swing factor. Third, power. A data hall without a grid "
        "connection does not buy chips, and some campuses are waiting on utilities. "
        "A guide below $200 billion, or a margin below 72 percent, would put the $240 "
        "target under review. " + _NOTICE
    ),
]

_ANTHROPIC = [
    (
        "Helios Research. Private markets note. Anthropic IPO watch. 17 November 2026. "
        "Analyst: Daniel Okonkwo. Press reports say Anthropic has hired banks for a listing "
        "in the first quarter of 2027. We think a valuation near $380 billion is the "
        "working target, and that the company would raise about $25 billion. Annualised "
        "revenue is reported near $38 billion, mostly from business customers who pay by "
        "usage. At that valuation the shares would trade at ten times run-rate revenue."
    ),
    (
        "Structure and risks. The company is a public benefit corporation, and a Long-Term "
        "Benefit Trust elects some of the board. Investors will price that governance in "
        "both directions. Two cloud partners hold large stakes, and lock-up terms for them "
        "will decide how much stock is free to trade on day one. Compute commitments are "
        "the main cost risk: multi-year contracts are signed before the revenue is. "
        "The next thing to watch is a confidential filing, which would tell us the timing "
        "is real. We would not chase the stock on day one. " + _NOTICE
    ),
]

_COMPETITORS = [
    (
        "Cedar Ridge Capital. Sector note. AI model competitors. 19 November 2026. "
        "Author: Priya Shah. OpenAI remains the largest by users and by revenue, with "
        "annualised revenue near $52 billion, most of it from consumer subscriptions. It "
        "has committed to far more computing than it can pay for today, and it needs "
        "new funding or a listing to carry it. We do not expect an OpenAI listing before "
        "2028."
    ),
    (
        "The rest of the field. Google bundles its models into search, cloud, and office "
        "tools, and wins deals on distribution rather than on benchmark scores. Meta and "
        "several smaller labs release open-weight models, which push the price per million "
        "tokens down by about 40 percent a year. That hurts every lab that sells on "
        "price, and helps the chip makers, because cheaper tokens mean more use. "
        "xAI and Mistral are credible but small in business sales."
    ),
    (
        "Where the money is. The figure on this page splits enterprise spend on model "
        "access in the third quarter of 2026 by lab. The desk's reading is that the "
        "lead is narrower than most investors assume, and that one lab is gaining on the "
        "leader. The words on this page do not give the shares. They are on the figure. "
        "We would not read a consumer user count as a guide to business revenue. " + _NOTICE
    ),
]

_WRAP = (
    "Helios Research. Market wrap. 20 November 2026. Analyst: Daniel Okonkwo. The "
    "semiconductor index rose 2.1 percent this week and the broad market was flat. "
    "Consensus FY27 data-center revenue for NVIDIA is $195 billion, which is below the "
    "$210 billion some desks use, and the shares are trading near $198. Positioning in "
    "AI names is crowded, and any weak order data would hit them hard. Anthropic has not "
    "filed. We do not expect a listing before the second half of 2027. OpenAI is "
    "private and has no listing date. The Federal Reserve meets on 9 December and the "
    "market prices a 60 percent chance of a cut. " + _NOTICE
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
    (happy / "anthropic-ipo-watch.pdf").write_bytes(
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
                        "title": "Enterprise spend on model access, Q3 2026",
                        "note": "Share of enterprise spend by lab. Desk estimate.",
                        "parts": [
                            {
                                "label": "OpenAI",
                                "share": 0.38,
                                "value": "38%",
                                "color": "#1f4e79",
                            },
                            {
                                "label": "Anthropic",
                                "share": 0.31,
                                "value": "31%",
                                "color": "#4f81bd",
                            },
                            {
                                "label": "Google",
                                "share": 0.21,
                                "value": "21%",
                                "color": "#8fafc4",
                            },
                            {
                                "label": "All others",
                                "share": 0.10,
                                "value": "10%",
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
