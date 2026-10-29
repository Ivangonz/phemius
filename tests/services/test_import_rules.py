import pytest
from pydantic import ValidationError

from phemius.config import load_config
from phemius.services.import_rules import ImportRules, effective_rules, merge_rules


def test_rules_left_unset_follow_the_global_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_WATCH_ON_CHANGE", "regenerate")
    monkeypatch.setenv("PHEMIUS_SKIP_NOT_RECOMMENDED", "false")

    rules = effective_rules(ImportRules(), load_config())

    assert rules.auto_audio is True
    assert rules.keep_versions is True
    assert rules.regenerate_on_change is True
    assert rules.skip_not_recommended is False
    assert ".md" in rules.file_types and ".pdf" in rules.file_types


def test_source_rules_win_over_the_global_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SKIP_NOT_RECOMMENDED", "true")
    overrides = ImportRules(
        auto_audio=False,
        skip_not_recommended=False,
        keep_versions=False,
        regenerate_on_change=True,
        file_types=[".md"],
    )

    rules = effective_rules(overrides, load_config())

    assert (
        rules.auto_audio,
        rules.skip_not_recommended,
        rules.keep_versions,
        rules.regenerate_on_change,
        rules.file_types,
    ) == (False, False, False, True, [".md"])


def test_file_types_are_normalized() -> None:
    rules = ImportRules(file_types=["MD", ".pdf", "md"])

    assert rules.file_types == [".md", ".pdf"]


@pytest.mark.parametrize("file_types", [[], [".exe"]])
def test_unsupported_or_empty_file_types_are_rejected(file_types: list[str]) -> None:
    with pytest.raises(ValidationError):
        ImportRules(file_types=file_types)


def test_merging_sets_sent_rules_and_null_returns_one_to_the_global_setting() -> None:
    saved = ImportRules(auto_audio=False, keep_versions=False)
    change = ImportRules.model_validate({"keep_versions": None, "file_types": [".md"]})

    merged = merge_rules(saved, change)

    assert merged == ImportRules(auto_audio=False, file_types=[".md"])
