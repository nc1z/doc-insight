# Samples

Original demo documents for a fictional hedge-fund desk, Cedar Ridge Capital, looking at the fictional company Northline Semiconductor (NTLN). They were written for this project and are released as CC0. None of the prices, filings, or people are real. They are separate from the eval fixtures in `backend/evals/fixtures.json`, which are generated and not committed.

The packet mixes short terminal-style notes with a few longer memos. Two sources disagree, so a consolidated report has to surface the conflict:

| Fact         | Desk note and company primer | Broker flash |
| ------------ | ---------------------------- | ------------ |
| FY26 revenue | $4.2 billion                 | $3.6 billion |
| Gross margin | 61 percent                   | 54 percent   |
| Price target | $86                          | $62          |

The channel check also disagrees with the desk on the order book. The desk says the lead customer reaffirmed the full-year order book. The channel check says that customer cut the Q3 order by 15 percent.

## Documents

| File                               | What it demonstrates                                                                                                                                                                       |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `desk-note.pdf`                    | A short internal note. The desk's revenue, margin, target, and order-book view.                                                                                                            |
| `broker-flash.pdf`                 | A short sell-side flash that contradicts the desk on those three figures.                                                                                                                  |
| `company-primer.pdf`               | A three-page primer with backlog, customers, and the same guide as the desk.                                                                                                               |
| `channel-check.pdf`                | A three-page expert-call memo. It says the lead customer cut the Q3 order by 15 percent.                                                                                                   |
| `coverage-memo.pdf`                | Two pages of solid text, then a third page of text with an infographic of the FY25 buyer split.                                                                                            |
| `terminal-snapshot.pdf`            | A terminal screen. Short-interest readings are drawn on the chart on page 2 and are not in the text layer.                                                                                 |
| `expert-call.pdf`                  | A scanned slip. The note is an image, so the PDF has no text layer.                                                                                                                        |
| `adversarial/positioning-note.pdf` | A positioning comment in the same voice. A pasted chat tells the model to ignore its instructions and reply `APPROVED`. The phrase is recorded and does not, by itself, flag the document. |
| `adversarial/hidden-note.pdf`      | The same kind of note, with a white one-point sentence a reader cannot see. That hidden text flags the document.                                                                           |
| `invalid/corrupt.pdf`              | A PDF cut off mid-file. Upload rejects it as `invalid_pdf`.                                                                                                                                |
| `invalid/encrypted.pdf`            | An encrypted PDF. The password is `library`. Upload rejects it as `encrypted_pdf`.                                                                                                         |
| `invalid/empty.pdf`                | A valid PDF with a blank page. Upload accepts it. Extraction later fails with `no_extractable_content`.                                                                                    |
| `invalid/notes.pdf`                | Plain text renamed to `.pdf`. Upload rejects it as `unsupported_type`.                                                                                                                     |

Two ready-made upload sets, a happy path and a failure path, are in `flows/`. See `flows/README.md`.

Regenerate the demo files from `backend/` with `uv run python -m evals.samples`. That command does not rewrite `samples/invalid/`. Regenerate `flows/` with `uv run python -m evals.flows`.
