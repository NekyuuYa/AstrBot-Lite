import copy
import modulefinder

from astrbot.core.aar.legacy_adapter import PersonaProxy


class DummyPromptManager:
    def __init__(self) -> None:
        self.module_ref = modulefinder


def test_persona_proxy_deepcopy_keeps_prompt_manager_reference() -> None:
    prompt_manager = DummyPromptManager()
    original = PersonaProxy(
        {
            "prompt": "base prompt",
            "name": "default",
            "begin_dialogs": [],
            "mood_imitation_dialogs": [],
            "custom_error_message": None,
            "_begin_dialogs_processed": [],
            "_mood_imitation_dialogs_processed": "",
        },
        prompt_manager=prompt_manager,
    )

    copied = copy.deepcopy(original)

    assert isinstance(copied, PersonaProxy)
    assert copied is not original
    assert copied["prompt"] == original["prompt"]
    assert copied._prompt_manager is prompt_manager
    assert copied._prompt_manager is original._prompt_manager
    assert copied._original_prompt == original._original_prompt
