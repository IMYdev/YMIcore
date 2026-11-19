import pytest
from core.storage import add_warn, warn_counts, clear_warns


def test_warn_basic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    # Add a warn
    result = add_warn(-123, 456, "Test reason", 999)
    
    # Check it's stored
    counts = warn_counts(-123)
    assert str(456) in counts
    assert counts[str(456)]["count"] == 1
    assert counts[str(456)]["latest"]["reason"] == "Test reason"
    assert counts[str(456)]["latest"]["by"] == 999
    
    # Add another warn
    result2 = add_warn(-123, 456, "Second reason", 999)
    counts2 = warn_counts(-123)
    assert counts2[str(456)]["count"] == 2
    assert counts2[str(456)]["latest"]["reason"] == "Second reason"
    
    # Clear warns for this user
    cleared = clear_warns(-123, 456)
    
    # After clearing, the user key should be gone (file is empty)
    # So warn_counts returns an empty dict
    assert cleared == {}


def test_warn_limit_enforcement(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    # Add 5 warns (max per user)
    for i in range(5):
        add_warn(-124, 789, f"Reason {i}", 999)
    
    counts = warn_counts(-124)
    assert counts[str(789)]["count"] == 5
    assert counts[str(789)]["latest"]["reason"] == "Reason 4"
    
    # Try to add a 6th warn - should be kept at 5
    add_warn(-124, 789, "Should not appear", 999)
    counts_after = warn_counts(-124)
    assert counts_after[str(789)]["count"] == 5
    # The oldest should be dropped
    assert counts_after[str(789)]["latest"]["reason"] == "Should not appear"


def test_clear_all_warns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    # Add warns for multiple users
    add_warn(-125, 111, "User 1 warn", 999)
    add_warn(-125, 222, "User 2 warn", 999)
    
    # Clear all warns
    result = clear_warns(-125)
    
    # After clearing all, warn_counts should return empty dict
    # (because the file is deleted)
    counts = warn_counts(-125)
    assert isinstance(counts, dict)
    assert len(counts) == 0