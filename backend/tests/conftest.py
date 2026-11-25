"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def no_real_models_for_question_solving(monkeypatch):
    """'solve question N' may ask the LLM to read a worksheet and fall back to Grounding DINO.
    Tests must never call a real provider or load the detector, so both are off unless a
    test replaces them itself."""
    from app.services import question_solver
    monkeypatch.setattr(question_solver, "_llm_locate", lambda blocks, number: None)
    monkeypatch.setattr(question_solver, "_system_with_dino",
                        lambda candidate: (None, "Grounding DINO is disabled in tests"))
