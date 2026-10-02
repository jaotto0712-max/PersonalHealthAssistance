"""Fixed responses. The model is never called when an emergency is detected."""

DISCLAIMER = (
    "This assistant provides general health information only. It is not a substitute for "
    "professional medical advice, diagnosis, or treatment. In an emergency, call 911."
)

_CALL_911 = (
    "**This could be a medical emergency. Call 911 now** or go to the nearest emergency room. "
    "Please don't wait for an online answer."
)

EMERGENCY_MESSAGES: dict[str, str] = {
    "self_harm": (
        "I'm really glad you reached out. You don't have to go through this alone. "
        "**Please call or text 988** (Suicide & Crisis Lifeline) right now to talk with someone, "
        "any time of day or night. **If you are in immediate danger, call 911.**"
    ),
    "overdose": (
        "**If the person is unconscious, having trouble breathing, or having a seizure, call 911 "
        "now.** Otherwise call **Poison Control at 1-800-222-1222** right away, any time. "
        "Have the medicine bottle or product with you."
    ),
}


def emergency_message(category: str) -> str:
    return EMERGENCY_MESSAGES.get(category, _CALL_911)
