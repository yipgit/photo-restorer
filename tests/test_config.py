from photo_restorer.core.config import load_preset

def test_load_family_preset():
    cfg = load_preset("family_photo_default")
    assert cfg["name"] == "family_photo_default"
    assert cfg["repair"]["face_restore"]["model"] == "codeformer"
