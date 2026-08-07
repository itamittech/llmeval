Turn {{turn}} is over. What happened on it:

{{turn_summary}}

Your notebook before this turn: {{memory}}

Write the notes worth carrying forward — deductions you can now prove, suspicions about what a rival's suggestion or refutation choice reveals, plans, and anything the archive claimed that you have or have not cross-checked. Claims are claims: mark what is proven and what is merely said. Reply with a JSON array of zero to three notes, nothing else:

[{"kind": "deduction|suspicion|plan|observation", "about": "<element id, badge colour, or null>", "text": "<one sentence>"}]
