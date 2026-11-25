"""Chatbot adaptation of ReAct's action–observation pattern.

Uses an injected model adapter instead of the original GPT-3 call.
Canvas actions execute in the browser; their results are supplied
in context["history"] before selecting the next action.

This is an adaptation, not execution of the original notebook.
"""


def next_action(context, decide):
    decision = decide(context)

    if not isinstance(decision, dict):
        raise ValueError("Agent decision must be a JSON object.")

    action_type = decision.get("type")

    if action_type == "write_math":
        expression = decision.get("expression")

        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("Math expression is missing.")

        return {
            "type": "write_math",
            "expression": expression.strip(),
        }

    if action_type == "finish":
        message = decision.get("message")

        if not isinstance(message, str) or not message.strip():
            raise ValueError("Completion message is missing.")

        return {
            "type": "finish",
            "message": message.strip(),
        }

    raise ValueError(f"Unsupported agent action: {action_type}")