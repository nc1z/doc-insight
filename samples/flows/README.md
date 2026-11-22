# Demo flows

Two folders to drop into the upload page in one go.

Regenerate from `backend/` with `uv run python -m evals.flows`.

## happy-path/

Theme: AI and the stock market, November 2026. All four files upload and analyse cleanly.

The facts come from public reporting between 12 and 21 November 2026, and each document names its sources on its last page. They are samples for software testing, not investment advice, so check the sources before relying on a figure. The documents are plain compilations. They have no author, firm, rating, or price target.

| File                           | Pages | What it covers                                                                                                                                                   |
| ------------------------------ | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nvidia-stability-outlook.pdf` | 3     | NVIDIA's Q3 FY27 results, fourth-quarter guidance, the 12 November CEO resignation, customer concentration, China, and export rules.                             |
| `anthropic-ipo-debrief.pdf`    | 2     | Anthropic's IPO as of 19 November: pricing, size, valuation, first-day trading, and the filing's financials.                                                     |
| `ai-competitor-landscape.pdf`  | 3     | OpenAI's funding and revenue, Google and the open-weight labs. **Page 3 carries an image**: each lab's share of enterprise LLM API spend. No text states shares. |
| `market-wrap.pdf`              | 1     | The week to 20 November: the sell-off, the SEC report on NVIDIA, the close of the Anthropic IPO, an OpenAI valuation, and the Fed.                               |

Things a consolidated report should surface:

| Topic                      | Source A                                                                                           | Source B                                                                                           |
| -------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Anthropic IPO proceeds     | `anthropic-ipo-debrief.pdf`: $81.3 billion at pricing, $107.3 billion with the private placement   | `market-wrap.pdf`: about $93.5 billion once the underwriters' option closed, $119.5 billion in all |
| OpenAI's current valuation | `ai-competitor-landscape.pdf`: $1.25 trillion (Bloomberg, 6 November), after $852 billion in March | `market-wrap.pdf`: $1.27 trillion (Nasdaq Private Market)                                          |
| Enterprise spend by lab    | Only in the image on page 3 of `ai-competitor-landscape.pdf`                                       | The text says who leads and who fell furthest, without shares                                      |

The two money figures differ because the sources date from different days or count different things, so a report should keep both numbers and say where each comes from.

**Image test.** Page 3 of `ai-competitor-landscape.pdf` has text above the image, so the file analyses with or without image reading, but the text layer never states the shares (Anthropic 55 percent, OpenAI 31 percent, Google 9 percent, all others 5 percent). With image reading on, check that the report gives those four numbers. The extractor marks that page as having an image.

### Sources

- Anthropic: [prices IPO](https://www.anthropic.com/news/anthropic-prices-initial-public-offering) (18 Nov) and [closes IPO](https://www.anthropic.com/news/ipo-close) (20 Nov); [Reuters](https://www.investing.com/news/stock-market-news/anthropic-prices-blockbuster-ipo-at-83-a-share-source-says-5037110); [NPR](https://www.npr.org/2026/11/18/nx-s1-6046212/anthropic-record-ipo-price); [CNBC](https://www.cnbc.com/2026/11/19/anthropic-ipo-ant-live-updates.html); [The Financial Express](https://www.financialexpress.com/market/global-markets/anthropic-vs-openai-revenue-valuation-losses-and-the-battle-for-ai-dominance/4386030/).
- NVIDIA: [Q3 FY27 results](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Third-Quarter-Fiscal-2027/default.aspx) (17 Nov); [CFO commentary](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000088/q3fy27cfocommentary.htm); [earnings call transcript](https://exa.ai/library/markets/stocks/NVDA/earnings/FY2027/Q3/transcript); [CEO transition](https://nvidianews.nvidia.com/news/nvidia-announces-ceo-transition) (12 Nov); [Al Jazeera](https://www.aljazeera.com/news/2026/11/12/why-did-nvidia-ceo-jensen-huang-resign-and-who-is-colette-kress); [WIRED](https://www.wired.com/story/jensen-huangs-lying-alarmed-nvidia-board-ahead-of-his-resignation/).
- Competitors: [Menlo Ventures, State of Enterprise AI](https://menlovc.com/wp-content/uploads/2026/11/menlo_ventures_enterprise_ai_report-2026-110326.pdf) (3 Nov); [The Verge](https://www.theverge.com/ai-artificial-intelligence/1029380/openai-1-25-trillion-investment-valuation) (6 Nov); [Reuters](https://www.reuters.com/5f374b32b07b/world/openai-seeks-accelerate-fundraising-ahead-anthropic-ipo-sources-say-2026-10-19/) (19 Oct); [Yahoo Finance](https://finance.yahoo.com/technology/ai/articles/anthropic-public-openai-ready-075701016.html) (20 Nov).
- Markets: [CNBC, 20 Nov](https://www.cnbc.com/2026/11/19/stock-market-today-live-updates.html); [CNBC, what caused the sell-off](https://www.cnbc.com/2026/11/20/sp-500-correction-market-sell-off.html); [Yonhap Infomax](https://en.infomaxai.com/news/articleView.html?idxno=149595).

## failure-path/

Theme: Singapore housing news. Every figure in these four files is invented, and each says so on its last page. They are unrelated to the happy path, so the consolidated report has nothing to link between the two flows if you mix them.

| File                          | Pages   | What happens                                                                                                                       |
| ----------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `hdb-resale-prices.pdf`       | 2       | Analyses cleanly.                                                                                                                  |
| `bto-launch.pdf`              | 1       | Analyses cleanly.                                                                                                                  |
| `condo-rentals.pdf`           | 1       | Analyses cleanly.                                                                                                                  |
| `cooling-measures-review.pdf` | corrupt | Cut off mid-file. Upload rejects it as `invalid_pdf` ("The PDF is corrupt or cannot be parsed.") and the job waits for a decision. |

Upload all four. The job stops at the decision step with three files accepted and one rejected. Try each choice: continue without the rejected file, re-upload a replacement, or cancel.

A valid PDF cannot fail on its own today. A blank or scanned page extracts as empty text and is not rejected. A file that fails during processing needs a worker-side hook, as in `backend/bruno/processing-failure/`.
