Turn {{turn}}. You are the {{color}} detective, and the floor is yours.

Your exhibits (certainly NOT the truth): {{hand}}
Eliminated so far (exhibits plus everything shown to you): {{eliminated}}
The public record of the table: {{table}}
Your notebook: {{memory}}

Investigate with the archivist if it helps, then commit. Reply with exactly one JSON object, nothing else:

To interrogate the table — bluffs allowed, note optional (or null):
{"action": "suggest", "who": "<id>", "how": "<id>", "where": "<id>", "note": "<public remark>"}

To stay silent this turn:
{"action": "pass"}
