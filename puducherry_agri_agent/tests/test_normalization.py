"""LGD and alias normalisation tests (deterministic rules in src/normalizer/lgd.py)."""
import pytest

from src.normalizer.lgd import AliasResolver, alias_key, region_for


@pytest.fixture(scope="module")
def resolver():
    """One AliasResolver built from data/aliases.csv."""
    return AliasResolver()


@pytest.mark.parametrize("spelling", ["Pondicherry", "Pondy", "PONDICHERRY", "Puducherry", "PY"])
def test_puducherry_spellings(resolver, spelling):
    """Old and short spellings map to Puducherry, LGD district 600."""
    hit = resolver.resolve(spelling, "region")
    assert hit["canonical"] == "Puducherry" and hit["lgd_district_code"] == 600


def test_karaikal_district(resolver):
    """KKL / Karikal -> Karaikal, LGD district 598."""
    assert resolver.resolve("KKL")["lgd_district_code"] == 598
    assert resolver.resolve("Karikal")["canonical"] == "Karaikal"


def test_mahe_and_yanam_are_subdistricts_of_600(resolver):
    """Mahe (5913) and Yanam (5908) are sub-districts of district 600, not districts."""
    mahe = resolver.resolve("Mahé")
    yanam = resolver.resolve("Yanam")
    assert (mahe["lgd_district_code"], mahe["lgd_subdistrict_code"]) == (600, 5913)
    assert (yanam["lgd_district_code"], yanam["lgd_subdistrict_code"]) == (600, 5908)
    assert region_for(600, 5913) == "Mahe" and region_for(600, 5908) == "Yanam"


def test_unknown_place_is_not_guessed(resolver):
    """A name outside Puducherry returns None (the agent then logs unknown_region)."""
    assert resolver.resolve("Chennai") is None


def test_alias_key_strips_accents_and_case():
    """Lookup keys are casefolded with accents and punctuation removed."""
    assert alias_key("Mahé") == alias_key("MAHE") == "mahe"


def test_lgd_two_districts_four_regions(conn):
    """LGD lists 2 districts while the reports use 4 regions (key project finding)."""
    n_dist = conn.execute("SELECT COUNT(*) FROM lgd_locations WHERE entity_type='district'").fetchone()[0]
    n_reg = conn.execute("SELECT COUNT(*) FROM lgd_locations WHERE entity_type='region'").fetchone()[0]
    assert (n_dist, n_reg) == (2, 4)


def test_db_rows_use_canonical_regions(conn):
    """crop_statistics and coop_societies only contain canonical region names."""
    allowed = {"Puducherry", "Karaikal", "Mahe", "Yanam", "UT"}
    for table in ("crop_statistics", "coop_societies"):
        regions = {r[0] for r in conn.execute(f"SELECT DISTINCT region FROM {table}")}
        assert regions <= allowed
