# Extraction prompt (v2)

You read one Ontario Court of Appeal decision and return JSON matching the schema below.
Use only the text provided. Never guess; omit a field you cannot support.
KNOWN FACTS in the user message (case_id, title, decision_date) are exact: copy them.

## Fields

- `court`: the court that issued this decision.
- `judges`: every judge on the panel, surname only, as in the header.
- `lawyers`: each lawyer named, with `side` = appellant, respondent or other.
- `parties`: each party with `role` and `kind`.
- `statute_provisions`: statutes and rules relied on, e.g. "Criminal Code s. 151".
- `offences`, `issues`: the charges (if criminal) and the legal questions.
- `principles`: legal principles or tests the Court applies.
- `citations`: every case cited. `case_id` is the neutral citation, e.g. "2015 ONCA 733";
  skip cases without one. `treatment` is exactly one of followed, distinguished, applied,
  considered, overruled, cited. `para` is the paragraph number if given.
- `outcome`: the disposition of THIS appeal (allowed, dismissed, allowed in part), exactly one
  value from the schema.
- `remedies`: what this Court ordered as a result, from the schema list, for example a
  sentence increased or reduced, a new trial ordered, acquittals set aside, matter remitted.
  Rules:
  - Empty when the appeal is dismissed. A costs order is never a remedy.
  - `sentence_increased` when the Court raises the sentence (usually on a Crown appeal);
    `sentence_reduced` when it lowers it. Compare the sentence below with the one the Court
    imposes and pick the right direction.
  - Acquittals set aside: use `acquittal_set_aside` and, if a new trial follows,
    also `new_trial_ordered`.
  - `order_varied`, `order_set_aside`, `remitted` are for civil or tribunal orders.
  - Use only values from the schema; one appeal can have several.

## stages (most important)

Reconstruct the case as a lawyer would have seen it before this Court decided. Each stage is
CUMULATIVE: repeat the earlier facts and add the new ones.

- `facts`: the events behind the case, with names, dates, offences or claims.
- `procedural_history`: facts plus every earlier proceeding (charges, trial, motion, tribunal).
- `lower_court_decision`: plus what the lower court or tribunal decided and why, with any
  sentence or order.
- `grounds_of_appeal`: plus who appealed and the arguments of each side.

Rules for `known_so_far`:
- 3 to 6 sentences, concrete: names, dates, amounts, sections, sentences imposed.
- It must NEVER say what the Court of Appeal decided or reasoned, and never use hindsight
  ("the appeal was dismissed", "the court found", "a new trial was ordered"). Lower-court
  decisions are fine, because they happened before.
- Include a stage only if the decision gives enough to describe it; omit the others.

Rules for `next_steps`: the single next real event after that stage (for example "The Crown
appealed the sentence"). For `grounds_of_appeal` it is the Court of Appeal's decision, stated
briefly. No filler such as "the court will review".
