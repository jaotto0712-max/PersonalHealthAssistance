import pytest

from pha.safety.emergency import detect_emergency
from pha.safety.messages import emergency_message

POSITIVES = [
    ("I have crushing chest pain and my left arm is numb", "cardiac"),
    ("my chest hurts and I'm sweating", "cardiac"),
    ("there's a lot of pressure in my chest right now", "cardiac"),
    ("I think I am having a heart attack", "cardiac"),
    ("my dad is having a heart attack what do I do", "cardiac"),
    ("I can't breathe", "breathing"),
    ("my son is having trouble breathing", "breathing"),
    ("sudden shortness of breath while resting", "breathing"),
    ("she is gasping for air", "breathing"),
    ("his lips are turning blue", "breathing"),
    ("my mom's face is drooping on one side", "stroke"),
    ("he has slurred speech all of a sudden", "stroke"),
    ("I think I'm having a stroke", "stroke"),
    ("suddenly numb on my right side", "stroke"),
    ("worst headache of my life came on suddenly", "stroke"),
    ("I cut my hand and the bleeding won't stop", "bleeding"),
    ("heavy bleeding after surgery", "bleeding"),
    ("I've been coughing up blood", "bleeding"),
    ("my throat is closing after eating peanuts", "anaphylaxis"),
    ("tongue swelling after a bee sting", "anaphylaxis"),
    ("I think this is anaphylaxis", "anaphylaxis"),
    ("I took too many of my sleeping pills", "overdose"),
    ("my toddler swallowed a whole bottle of vitamins", "overdose"),
    ("I think I overdosed", "overdose"),
    ("my kid drank bleach", "overdose"),
    ("my wife is having a seizure", "seizure"),
    ("he keeps seizing and won't stop", "seizure"),
    ("my grandfather collapsed and is unresponsive", "unconscious"),
    ("she passed out and won't wake up", "unconscious"),
    ("I want to end my life", "self_harm"),
    ("I've been thinking about suicide", "self_harm"),
    ("i want to kill myself", "self_harm"),
    ("sometimes I want to die", "self_harm"),
    ("I've been self-harming again", "self_harm"),
    ("I don't want to be alive anymore", "self_harm"),
    ("everyone would be better off dead without me", "self_harm"),
    ("no fever but chest pain since this morning", "cardiac"),  # negation in another clause
    ("I don't want to kill myself but I think about it", "self_harm"),  # never negated
]

NEGATIVES = [
    "I had no chest pain during my stress test, what does the report mean?",
    "patient denies chest pain or shortness of breath",
    "what are the signs of a stroke?",
    "what are the symptoms of a heart attack in women?",
    "how do I know if someone is having an allergic reaction?",
    "what is a normal LDL cholesterol level?",
    "I got poison ivy on my arm",
    "can you explain my A1C result?",
    "how much ibuprofen is safe to take per day?",
    "what are common side effects of metformin?",
    "I never had trouble breathing before this cold",
    "what is the difference between type 1 and type 2 diabetes",
    "how can I lower my blood pressure naturally?",
    "is it normal to feel tired after a flu shot?",
    "my report says no evidence of heavy bleeding",
    "tips for running a marathon",
]


@pytest.mark.parametrize(("message", "category"), POSITIVES)
def test_detects_emergencies(message, category):
    match = detect_emergency(message)
    assert match is not None, message
    assert match.category == category


@pytest.mark.parametrize("message", NEGATIVES)
def test_ignores_non_emergencies(message):
    assert detect_emergency(message) is None


def test_known_false_positive_bare_symptom_mention():
    # Accepted trade-off (design.md): rules favor recall, so a bare symptom phrase triggers the
    # urgent-care message even in an informational question. The UI banner still allows retrying.
    assert detect_emergency("what does shortness of breath on my visit summary mean?") is not None


def test_corpus_size_meets_task_minimums():
    assert len(POSITIVES) >= 30 and len(NEGATIVES) >= 15
    assert len({c for _, c in POSITIVES}) == 9


def test_messages_route_to_the_right_help():
    assert "911" in emergency_message("cardiac")
    assert "988" in emergency_message("self_harm") and "911" in emergency_message("self_harm")
    assert "1-800-222-1222" in emergency_message("overdose")
