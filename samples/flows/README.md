# Demo flows

Two folders to drop into the upload page in one go. Every figure is invented for testing. The companies are real names, but none of the forecasts, valuations, dates, or people are real.

Regenerate from `backend/` with `uv run python -m evals.flows`.

## happy-path/

Theme: AI and the stock market, November 2026. All four files upload and analyse cleanly.

| File                           | Pages | What it covers                                                                                                                       |
| ------------------------------ | ----- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `nvidia-stability-outlook.pdf` | 3     | Why the desk thinks NVIDIA's earnings are stable. Estimates FY27 data-center revenue of $210 billion.                                |
| `anthropic-ipo-watch.pdf`      | 2     | Reported IPO plans: a listing in the first quarter of 2027, a valuation near $380 billion.                                           |
| `ai-competitor-landscape.pdf`  | 3     | OpenAI, Google, and open-weight labs. **Page 3 carries an image**: the Q3 2026 enterprise spend split by lab. No text states shares. |
| `market-wrap.pdf`              | 1     | A one-page weekly wrap. Gives consensus FY27 data-center revenue for NVIDIA as $195 billion.                                         |

Things a consolidated report should surface:

| Topic                           | Source A                                                     | Source B                                                                |
| ------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------- |
| NVIDIA FY27 data-center revenue | `nvidia-stability-outlook.pdf`: $210 billion                 | `market-wrap.pdf`: consensus $195 billion                               |
| Anthropic listing timing        | `anthropic-ipo-watch.pdf`: first quarter of 2027             | `market-wrap.pdf`: not before the second half of 2027                   |
| Enterprise spend by lab         | Only in the image on page 3 of `ai-competitor-landscape.pdf` | The text says the lead is narrow and one lab is gaining, without shares |

**Image test.** Page 3 of `ai-competitor-landscape.pdf` has text above the image, so the file analyses today, but the text layer never states the shares (OpenAI 38 percent, Anthropic 31 percent, Google 21 percent, all others 10 percent). Until image reading is built, a report cannot know them. Once it is, check that the report gives those four numbers. The extractor marks that page as having an image.

## failure-path/

Theme: Singapore housing news. Unrelated to the happy path, so the consolidated report has nothing to link between the two flows if you mix them.

| File                          | Pages   | What happens                                                                                                                       |
| ----------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `hdb-resale-prices.pdf`       | 2       | Analyses cleanly.                                                                                                                  |
| `bto-launch.pdf`              | 1       | Analyses cleanly.                                                                                                                  |
| `condo-rentals.pdf`           | 1       | Analyses cleanly.                                                                                                                  |
| `cooling-measures-review.pdf` | corrupt | Cut off mid-file. Upload rejects it as `invalid_pdf` ("The PDF is corrupt or cannot be parsed.") and the job waits for a decision. |

Upload all four. The job stops at the decision step with three files accepted and one rejected. Try each choice: continue without the rejected file, re-upload a replacement, or cancel.

A valid PDF cannot fail on its own today. A blank or scanned page extracts as empty text and is not rejected. A file that fails during processing needs a worker-side hook, as in `backend/bruno/processing-failure/`.
