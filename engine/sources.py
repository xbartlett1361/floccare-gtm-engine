"""SOURCE: pull clinics, decision-makers and neighborhood language data with no manual list-building.

Three free, public, authoritative sources:
  1. CMS Doctors & Clinicians file (data.cms.gov, dataset mj5m-pzi6): every Medicare-enrolled
     clinician with specialty, group practice, group size, practice address and phone.
  2. NPPES NPI Registry (npiregistry.cms.hhs.gov): each organization's *authorized official*,
     with name and title. For small practices that is usually the owner or the practice manager.
  3. Census ACS 2020-24 table C16002 via Census Reporter: household language and
     limited-English-speaking households by ZIP.

`--live` mode calls the APIs directly. Offline mode reads the cached pulls in data/raw (made
on 2026-11-23 with exactly these queries) so the pipeline runs anywhere, including CI.
"""
from __future__ import annotations

import io
import json
from urllib.parse import urlencode

import pandas as pd

from .util import DATA

CMS_DATASET = "https://data.cms.gov/provider-data/api/1/datastore/query/mj5m-pzi6/0"
NPPES_API = "https://npiregistry.cms.hhs.gov/api/"
CENSUS_REPORTER = "https://api.censusreporter.org/1.0/data/show/latest"

CMS_FIELDS = ["org_pac_id", "facility_name", "num_org_mem", "provider_first_name", "provider_last_name",
              "cred", "grd_yr", "adr_ln_1", "adr_ln_2", "citytown", "zip_code", "telephone_number"]
RENAME = {"Facility Name": "facility_name", "Provider First Name": "first", "Provider Last Name": "last",
          "Cred": "cred", "Grd_yr": "grd_yr", "City/Town": "city", "ZIP Code": "zip9",
          "Telephone Number": "phone_raw", "provider_first_name": "first", "provider_last_name": "last",
          "citytown": "city", "zip_code": "zip9", "telephone_number": "phone_raw"}


# ------------------------------------------------------------------ CMS
def cms_query_url(specialty: str, zip_lo: str, zip_hi: str, exclude_orgs: list[str] | None = None) -> str:
    params = {"format": "csv", "schema": "false", "limit": 1500}
    for i, f in enumerate(CMS_FIELDS):
        params[f"properties[{i}]"] = f
    params.update({
        "conditions[0][property]": "pri_spec", "conditions[0][value]": specialty, "conditions[0][operator]": "=",
        "conditions[1][property]": "zip_code", "conditions[1][value][0]": zip_lo,
        "conditions[1][value][1]": zip_hi, "conditions[1][operator]": "between",
    })
    if exclude_orgs:
        params["conditions[2][property]"] = "org_pac_id"
        params["conditions[2][operator]"] = "not in"
        for i, o in enumerate(exclude_orgs):
            params[f"conditions[2][value][{i}]"] = o
    return f"{CMS_DATASET}?{urlencode(params)}"


def fetch_cms_live(cfg: dict, exclude_orgs: list[str]) -> pd.DataFrame:
    import requests
    frames = []
    for lo, hi in cfg["campaign"]["zip_ranges"]:
        url = cms_query_url(cfg["campaign"]["cms_specialty_filter"], lo, hi, exclude_orgs)
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        frames.append(pd.read_csv(io.StringIO(r.text), dtype=str))
    return _clean_cms(pd.concat(frames, ignore_index=True))


def load_cms_cached() -> pd.DataFrame:
    frames = [pd.read_csv(DATA / "raw" / f, dtype=str) for f in
              ("cms_dac_cardiology_manhattan_bronx_si.csv", "cms_dac_cardiology_brooklyn_queens.csv")]
    return _clean_cms(pd.concat(frames, ignore_index=True))


def _clean_cms(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=RENAME).fillna("")
    for c in ["org_pac_id", "facility_name", "num_org_mem", "first", "last", "cred", "grd_yr",
              "adr_ln_1", "adr_ln_2", "city", "zip9", "phone_raw"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str).str.strip()
    df["zip5"] = df["zip9"].str[:5]
    return df


def load_universe_counts() -> dict:
    with open(DATA / "raw" / "cms_dac_universe.json", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- NPPES
def nppes_query_url(taxonomy: str, city: str, skip: int = 0) -> str:
    return NPPES_API + "?" + urlencode({"version": "2.1", "enumeration_type": "NPI-2",
                                        "taxonomy_description": taxonomy, "city": city,
                                        "state": "NY", "limit": 200, "skip": skip})


def fetch_nppes_live(cfg: dict, cities: list[str]) -> pd.DataFrame:
    import requests
    rows = []
    for city in cities:
        for skip in (0, 200, 400, 600, 800, 1000):
            r = requests.get(nppes_query_url(cfg["campaign"]["nppes_taxonomy_filter"], city, skip), timeout=60)
            res = r.json().get("results", [])
            for x in res:
                b = x.get("basic", {})
                rows.append({"organization_name": b.get("organization_name", ""), "npi": x.get("number", ""),
                             "ao_first": b.get("authorized_official_first_name", ""),
                             "ao_last": b.get("authorized_official_last_name", ""),
                             "ao_title": b.get("authorized_official_title_or_position", ""),
                             "query_city": city})
            if len(res) < 200:
                break
    return pd.DataFrame(rows)


def load_nppes_cached() -> pd.DataFrame:
    return pd.read_csv(DATA / "raw" / "nppes_cardiology_org_officials.csv", sep="|", dtype=str).fillna("")


# ----------------------------------------------------------------- Census
def fetch_acs_live(zips: list[str]) -> pd.DataFrame:
    import requests
    rows = []
    for i in range(0, len(zips), 60):
        geo = ",".join(f"86000US{z}" for z in zips[i:i + 60])
        data = requests.get(f"{CENSUS_REPORTER}?table_ids=C16002&geo_ids={geo}", timeout=60).json()["data"]
        for gid, t in data.items():
            e = t["C16002"]["estimate"]
            rows.append({"geo": gid[-5:], "households": e["C16002001"], "english_only": e["C16002002"],
                         "spanish": e["C16002003"], "spanish_lep": e["C16002004"],
                         "indo_euro": e["C16002006"], "indo_euro_lep": e["C16002007"],
                         "asian_pi": e["C16002009"], "asian_pi_lep": e["C16002010"],
                         "other": e["C16002012"], "other_lep": e["C16002013"]})
    return pd.DataFrame(rows)


def load_acs_cached() -> pd.DataFrame:
    return pd.read_csv(DATA / "raw" / "acs2024_c16002_household_language_nyc.csv", dtype={"geo": str})
