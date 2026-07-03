# Annotation Guidelines - GroundCite-PTEN

These guidelines define how to annotate RAG answers for evidence grounding at claim and span level.

## Scope

The task measures groundedness, not global truth. A claim is `supported` if it is justified by the provided context, even when the context itself would be false in the real world.

Allowed claim labels:

- `supported`
- `unsupported`
- `contradicted`

`abstain_needed` is a sample/failure-type metadata value. It is not a claim label unless a future schema explicitly adds it.

## Claim Decomposition

Split the answer into atomic factual claims. A claim should contain one checkable proposition.

Example:

- Answer: "Brazil won the 2002 World Cup with goals by Ronaldo."
- Claim 1: "Brazil won the 2002 World Cup."
- Claim 2: "Ronaldo scored goals for Brazil in the 2002 World Cup."

For compound claims, annotate each factual part separately when possible. If a compound sentence cannot be split cleanly, label by the least-supported factual component and note the ambiguity.

## Labels

### supported

Use `supported` when the context directly states the claim or supports it through a simple, low-risk inference.

Simple paraphrases are allowed. Expanding a well-known acronym is allowed when the context makes the acronym clear.

### unsupported

Use `unsupported` when the claim adds information not present in the context and the context does not explicitly refute it.

Examples:

- adding a date not present in the context;
- adding a location not present in the context;
- making a causal explanation not present in the context;
- over-answering beyond the retrieved evidence.

### contradicted

Use `contradicted` when the claim directly conflicts with the context.

Contradictions include incompatible numbers, dates, entities, locations, negations, or relations.

If the context is ambiguous and does not directly refute the claim, prefer `unsupported`.

## Evidence Spans

For `supported` and `contradicted` claims, provide evidence spans whenever possible.

Rules:

- Use character offsets `[start, end)` with zero-based indexing.
- The span should be the shortest context text that supports or refutes the claim.
- Do not include leading or trailing whitespace.
- Multiple spans are allowed only when the claim requires multiple context fragments.

For `unsupported` claims, mark unsupported answer spans when the unsupported content is localized in the answer.

## Ambiguity

If a claim could reasonably be read in two ways:

1. Prefer the interpretation most directly tied to the user question and answer wording.
2. Use `unsupported` when the context does not settle the ambiguity.
3. Add a note explaining the decision.

## Conflicting Sources

If contexts disagree:

- A response that reports the disagreement neutrally can be `supported` when it accurately describes both sides.
- A response that chooses one side without disclosing a relevant conflict should be marked as risky and may be `contradicted` under the CSA protocol.
- A response can prefer the newer or authoritative source only if the context provides that temporal or authority signal.

## PT-BR Considerations

Annotators should pay special attention to:

- pronoun resolution and ellipsis;
- double negation;
- gender/number agreement that changes referents;
- false cognates and literal EN-to-PT transfer;
- regional or institutional acronyms;
- decimal and date formats.

Double negation should be interpreted by meaning, not by surface word overlap.

## Human Review Protocol

For the PT-BR audit packet:

1. Annotate without using the seed label when feasible.
2. Use only `supported`, `unsupported`, or `contradicted`.
3. Record uncertainty or adjudication notes in `notes`.
4. Run `python experiments/scripts/compute_human_agreement.py`.
5. Describe seed-vs-review as second-pass agreement unless two independent human annotators are documented.

## Reporting Boundary

Do not claim "human-validated PT-BR gold" unless the reported subset has documented review coverage, agreement results, and either adjudication or an explicit limitation.
