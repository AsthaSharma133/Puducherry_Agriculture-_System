"""Crop-name canonicalization (deterministic dictionary).

The Season & Crop Report prints the same crop under different labels across tables and
years ("Plantain" vs "Banana", "Sesamum" vs "Gingelly", "Pulsus" typo, "Cholam and other
millets" from 2023-24). Header text extracted from the PDF also carries noise from the
table title and unit notes. We tokenise the label and match keyword rules in order.

If no rule matches, `canonical_crop` returns None: the caller logs an `unmapped_header`
issue with needs_llm_review=1. That is the LLM boundary: the dictionary is deterministic;
only unmatched labels are candidates for the (QLoRA) LLM extractor in Sprint 3.
"""
from __future__ import annotations

import re

# Title / unit words that leak into header text and must be ignored.
NOISE = {"region", "regionwise", "wise", "area", "under", "all", "crops", "in", "puducherry",
         "u", "t", "of", "principal", "each", "rate", "yield", "out", "turn", "hectares",
         "metrictonnes", "metric", "tonnes", "kgs", "hectare", "contd", "iv", "a", "b", "v",
         "the", "etc"}

# (required keywords, canonical name, is_aggregate). First match wins; order matters.
TOTAL_RULES = [
    ({"grand"}, "Gross cropped area (all crops)"),
    ({"grains"}, "Total foodgrains"),
    ({"cereals"}, "Total cereals"),
    ({"pulses"}, "Total pulses"),
    ({"fruits"}, "Total fruits"),
    ({"vegetables"}, "Total vegetables"),
    ({"spices"}, "Total condiments & spices"),
    ({"condiments"}, "Total condiments & spices"),
    ({"non", "food"}, "Total non-food crops"),
    ({"oilseeds"}, "Total oilseeds"),
    ({"oil", "seeds"}, "Total oilseeds"),
    ({"food"}, "Total food crops"),
]

CROP_RULES = [
    ({"paddy"}, "Paddy"), ({"rice"}, "Paddy"),
    ({"ragi"}, "Ragi"), ({"cumbu"}, "Cumbu"),
    ({"cholam", "millets"}, "Cholam & other millets"),
    ({"cholam"}, "Cholam"),
    ({"millets"}, "Other millets (Thenai)"),
    ({"red", "gram"}, "Red gram"), ({"redgram"}, "Red gram"),
    ({"black", "gram"}, "Black gram"), ({"blackgram"}, "Black gram"),
    ({"green", "gram"}, "Green gram"), ({"greengram"}, "Green gram"),
    ({"other", "pulses"}, "Other pulses"),
    ({"sugarcane"}, "Sugarcane"),
    ({"plantain"}, "Banana/Plantain"), ({"banana"}, "Banana/Plantain"),
    ({"mangoes"}, "Mango"), ({"mango"}, "Mango"),
    ({"guava"}, "Guava"), ({"citrus"}, "Citrus"), ({"jackfruit"}, "Jackfruit"),
    ({"pappaya"}, "Other fruits (incl. papaya)"), ({"papaya"}, "Other fruits (incl. papaya)"),
    ({"water", "melon"}, "Watermelon"), ({"watermelon"}, "Watermelon"),
    ({"sweet", "potatoes"}, "Sweet potato"),
    ({"palmyrah"}, "Palmyrah"),
    ({"cashewnut"}, "Cashewnut"), ({"cashew"}, "Cashewnut"),
    ({"tapioca"}, "Tapioca"), ({"onion"}, "Onion"), ({"brinjal"}, "Brinjal"),
    ({"tomato"}, "Tomato"), ({"yam"}, "Yam (Karunai)"),
    ({"lady", "finger"}, "Ladies finger (Bhindi)"), ({"ladys", "finger"}, "Ladies finger (Bhindi)"),
    ({"cucumber"}, "Cucumber"), ({"pumpkin"}, "Pumpkin"),
    ({"guard"}, "Other gourds"), ({"gourd"}, "Other gourds"),
    ({"other", "veg"}, "Other vegetables"), ({"other", "vegetables"}, "Other vegetables"),
    ({"betelnuts"}, "Arecanut (betel nut)"), ({"arecanut"}, "Arecanut (betel nut)"),
    ({"betel"}, "Arecanut (betel nut)"),
    ({"chillies"}, "Chillies"), ({"coriander"}, "Coriander"), ({"pepper"}, "Pepper"),
    ({"tamarind"}, "Tamarind"), ({"turmeric"}, "Turmeric"), ({"ginger"}, "Ginger"),
    ({"garlic"}, "Garlic"),
    ({"cotton"}, "Cotton"), ({"groundnut"}, "Groundnut"), ({"ground", "nut"}, "Groundnut"),
    ({"sesamum"}, "Sesamum (gingelly)"), ({"gingelly"}, "Sesamum (gingelly)"),
    ({"coconut"}, "Coconut"),
    ({"other", "oilseeds"}, "Other oilseeds"), ({"other", "oil", "seeds"}, "Other oilseeds"),
    ({"fodder"}, "Fodder crops"), ({"flower"}, "Flower crops"),
    ({"green", "manure"}, "Green manure"), ({"casuarina"}, "Casuarina"),
    ({"betalvines"}, "Betel vines"), ({"betel", "vines"}, "Betel vines"),
    ({"bamboos"}, "Bamboo"), ({"bamboo"}, "Bamboo"), ({"eucalyptus"}, "Eucalyptus"),
    ({"medicinal"}, "Medicinal plants (other)"),
    ({"other", "non", "food"}, "Other non-food crops"),
    ({"other", "food"}, "Other food crops"),
    ({"other", "fruits"}, "Other fruits (incl. papaya)"),
    ({"fresh", "fruits"}, "Fresh fruits"), ({"dry", "fruits"}, "Dry fruits"),
]

# Land-use summary columns of Table IV-A (cols 63-67); checked after crop rules.
SUMMARY_RULES = [
    ({"net", "cropped"}, "Net area sown"),
    ({"more", "once"}, "Area sown more than once"),
    ({"non", "food"}, "Gross cropped area: non-food crops"),
    ({"food"}, "Gross cropped area: food crops"),
]

SEASON_TOKENS = {"i": "I", "ii": "II", "iii": "III", "total": "All", "average": "All"}


def tokens(label: str) -> list[str]:
    t = label.lower().replace("pulsus", "pulses").replace("lady's", "ladys")
    return [w for w in re.findall(r"[a-z]+", t) if w not in NOISE]


def season_only(label: str) -> str | None:
    """'I', 'II Crop', 'Total', 'Average' (paddy sub-columns) -> season code, else None."""
    toks = [w for w in re.findall(r"[a-z]+", label.lower()) if w not in NOISE and w != "crop"]
    if toks and all(w in SEASON_TOKENS for w in toks):
        return SEASON_TOKENS[toks[-1]]
    return None


def canonical_crop(label: str) -> tuple[str, bool] | None:
    """Return (canonical crop name, is_aggregate) or None if no rule matches."""
    toks = set(tokens(label))
    if not toks:
        return None
    if "total" in toks and not ({"paddy", "rice"} & toks):
        for req, name in TOTAL_RULES:
            if req <= toks:
                return name, True
    for req, name in CROP_RULES:
        if req <= toks:
            return name, False
    for req, name in SUMMARY_RULES:
        if req <= toks:
            return name, True
    return None


def product_form(crop: str, label: str, table: str) -> str | None:
    lab = label.lower()
    if crop == "Paddy" and table in ("V-A", "V-B"):
        return "rice (milled)"
    if crop == "Cotton" and "kapas" in lab:
        return "kapas"
    if crop == "Groundnut" and "kern" in lab:
        return "kernels"
    if crop == "Coconut":
        return "nuts"
    return None
