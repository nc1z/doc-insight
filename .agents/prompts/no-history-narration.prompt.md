# No history narration

When writing or editing documentation, the file describes the current state only. A reader who never saw the chat, the previous version, or the instructions behind the edit should find nothing that refers to them. Git holds the history.

## Do not write

- **Versioning**: "v2", "updated", "revised", "new:", "(changed)", "previously", "now", "no longer", "as of this change", "originally".
- **Strikethroughs** or crossed-out alternatives (`~~old~~ new`). Delete the old text.
- **Change notes**: "Edit:", "Update:", "Note: this section was rewritten", changelog-style lists of what moved.
- **Justification for the edit**: why the text changed, what was wrong before, or who asked for it. Keep a rationale only if a reader of the current doc needs it to understand or apply the content.
- **Chat leaks**: "as discussed", "per your request", "as you mentioned", "you asked", "the user wants", "as requested above".
- **Instruction leaks**: restating the prompt or constraints given to you ("keep this concise", "don't mention X", "do not state that…"), or meta-commentary about the document ("this section explains…" when the heading already does).
- **Hedged corrections**: "actually", "to clarify", "correction:".

## Do

- Rewrite affected sentences so they read as if they had always been that way.
- When removing content, remove it fully; do not leave a stub saying it was removed.
- When replacing an approach, describe only the current one. Mention the alternative only if readers would otherwise ask why it was not used, and phrase it as a present-tense trade-off, not as history.
- Keep the existing structure, tone, and level of detail of the file unless the task is to change them.

## Before finishing

Re-read every changed section and search it for the words listed above. Remove any that refer to the editing process rather than the subject.
