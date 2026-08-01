from __future__ import annotations

import math
import re
from io import BytesIO
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "test_date": ["test_date", "date", "testing_date", "test date", "test", "tested_on"],
    "specified_strength": ["specified_strength", "f_c", "fc", "f'c", "grade_strength", "specified strength"],
}

A2_CONSTANTS = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}

IS456_ASSUMED_SD = {
    10: 3.5, 15: 3.5, 20: 4.0, 25: 4.0, 30: 5.0, 35: 5.0,
    40: 5.0, 45: 5.0, 50: 5.0, 55: 5.0, 60: 5.0, 65: 5.0,
}


def is456_assumed_sd(fck: float) -> float:
    if fck is None or pd.isna(fck):
        return np.nan
    grade = int(round(float(fck)))
    if grade <= 15:
        return 3.5
    if grade <= 25:
        return 4.0
    return 5.0


def _a2_for_n(n: float) -> float:
    try:
        key = int(round(float(n)))
    except (TypeError, ValueError):
        return np.nan
    return A2_CONSTANTS.get(key, np.nan)


OPTIONAL_COLUMNS = {
    "cube_1": ["cube_1", "cube1", "cube 1", "cube_a", "strength_1"],
    "cube_2": ["cube_2", "cube2", "cube 2", "cube_b", "strength_2"],
    "cube_3": ["cube_3", "cube3", "cube 3", "cube_c", "strength_3"],
    "test_average": ["test_average", "average_strength", "avg_strength", "test avg", "strength"],
    "supplier": ["supplier", "vendor", "plant", "source", "source_of_concrete"],
    "mix_id": ["mix_id", "mix", "mix design", "mix_design", "mix id"],
    "grade": ["grade", "concrete_grade", "strength_grade"],
    "structure": ["structure", "element", "location", "member", "pour_detail"],
}


def _normalise(name: str) -> str:
    return str(name).strip().lower().replace("-", "_").replace(" ", "_")


def map_columns(columns: Iterable[str]) -> Dict[str, str]:
    normalised = {_normalise(col): col for col in columns}
    mapping: Dict[str, str] = {}
    aliases = {**REQUIRED_COLUMNS, **OPTIONAL_COLUMNS}
    for canonical, choices in aliases.items():
        for choice in choices:
            key = _normalise(choice)
            if key in normalised:
                mapping[canonical] = normalised[key]
                break
    return mapping


def validate_columns(df: pd.DataFrame) -> Tuple[bool, List[str], Dict[str, str]]:
    mapping = map_columns(df.columns)
    missing = [name for name in REQUIRED_COLUMNS if name not in mapping]
    has_average = "test_average" in mapping
    cube_cols = [col for col in ["cube_1", "cube_2", "cube_3"] if col in mapping]
    if not has_average and len(cube_cols) < 2:
        missing.append("test_average or at least two cube strength columns")
    return len(missing) == 0, missing, mapping


def read_excel_input(excel_file) -> Tuple[pd.DataFrame, str]:
    """Read Excel from local path or Streamlit UploadedFile.

    Hugging Face Spaces passes uploaded files as in-memory objects. Reading the
    same object multiple times can fail if the pointer has moved, so we buffer
    the bytes once and create fresh BytesIO streams for each pandas read.
    """
    file_name = getattr(excel_file, "name", str(excel_file)).lower()
    engine = "xlrd" if file_name.endswith(".xls") else "openpyxl"

    if hasattr(excel_file, "getvalue"):
        excel_bytes = excel_file.getvalue()
    elif hasattr(excel_file, "read"):
        excel_file.seek(0)
        excel_bytes = excel_file.read()
    else:
        with open(excel_file, "rb") as handle:
            excel_bytes = handle.read()

    try:
        workbook = pd.ExcelFile(BytesIO(excel_bytes), engine=engine)
    except ImportError as exc:
        if engine == "xlrd":
            raise ImportError("Reading .xls files requires the xlrd package. Add xlrd to requirements.txt and rebuild the Space.") from exc
        raise

    parsed_sheets = []
    imported_names = []
    first_normal = None
    first_sheet = workbook.sheet_names[0]
    for sheet_name in workbook.sheet_names:
        raw = pd.read_excel(BytesIO(excel_bytes), sheet_name=sheet_name, header=None, engine=engine)
        normal = pd.read_excel(BytesIO(excel_bytes), sheet_name=sheet_name, engine=engine)
        if first_normal is None:
            first_normal = normal

        # SQC summary sheets must be detected before cube-set parsers. In this
        # format every compressive-strength row is an analysed sample, so 36
        # valid strength rows remain 36 tests rather than one averaged 3-cube set.
        sqc = normalise_sqc_strength_table(raw, sheet_name)
        if not sqc.empty:
            parsed_sheets.append(sqc)
            imported_names.append(sheet_name)
            continue

        # Detect cube-row logs before generic validation. In this layout, the
        # STRENGTH column is an individual cube value and the next unnamed
        # column is the test average, so rows must be grouped into tests first.
        tabular = normalise_tabular_cube_table(normal, sheet_name)
        if not tabular.empty:
            parsed_sheets.append(tabular)
            imported_names.append(sheet_name)
            continue

        valid, _, _ = validate_columns(normal)
        specified_from_sheet = _extract_grade_strength(sheet_name, raw)
        if valid or (not pd.isna(specified_from_sheet) and _normal_table_has_strength_and_date(normal)):
            normal = normal.copy()
            if "specified_strength" not in map_columns(normal.columns):
                normal["specified_strength"] = specified_from_sheet
            if "grade" not in map_columns(normal.columns):
                normal["grade"] = f"M{specified_from_sheet:g}"
            parsed_sheets.append(normal)
            imported_names.append(sheet_name)
            continue

        if _looks_like_cube_log(raw):
            parsed = normalise_cube_log(raw, sheet_name)
            if not parsed.empty:
                parsed_sheets.append(parsed)
                imported_names.append(sheet_name)

    if parsed_sheets:
        combined = pd.concat(parsed_sheets, ignore_index=True, sort=False)
        if len(imported_names) == 1:
            return combined, f"Cube strength data imported from sheet '{imported_names[0]}'."
        return combined, f"Cube strength data imported from {len(imported_names)} sheets: {', '.join(imported_names)}."

    return first_normal, f"Imported sheet '{first_sheet}'."


def _find_column(columns: Iterable[str], *needles: str) -> str | None:
    for col in columns:
        key = _normalise(col)
        if all(needle in key for needle in needles):
            return col
    return None


def _normal_table_has_strength_and_date(df: pd.DataFrame) -> bool:
    mapping = map_columns(df.columns)
    if "test_date" in mapping and "test_average" in mapping:
        return True
    has_date = _find_column(df.columns, "test") is not None or _find_column(df.columns, "date") is not None
    has_strength = any(_normalise(col) == "strength" for col in df.columns) or _find_column(df.columns, "strength") is not None
    return bool(has_date and has_strength)


def normalise_tabular_cube_table(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """Parse compact cube tables where each test occupies multiple cube rows.

    Example headers: CUBE ID, Specified strength, Cast date, Site, Age, Test,
    Maxi. Load (kN), STRENGTH, and an adjacent average-strength column.
    """
    if df.empty:
        return pd.DataFrame()

    specified_col = _find_column(df.columns, "specified", "strength")
    age_col = _find_column(df.columns, "age")
    test_col = _find_column(df.columns, "test")
    strength_col = next((col for col in df.columns if _normalise(col) == "strength"), None)
    load_col = _find_column(df.columns, "load")
    specified_from_name = _extract_grade_strength(sheet_name, pd.DataFrame())
    if (not specified_col and pd.isna(specified_from_name)) or not age_col or not test_col or (not strength_col and not load_col):
        return pd.DataFrame()

    cast_col = _find_column(df.columns, "cast", "date")
    site_col = _find_column(df.columns, "site")
    cube_id_col = _find_column(df.columns, "cube", "id")
    remarks_col = _find_column(df.columns, "remarks")
    cube_area_mm2 = 150 * 150
    load_to_mpa = 1000 / cube_area_mm2

    ages = pd.to_numeric(df[age_col], errors="coerce")
    test_dates = pd.to_datetime(df[test_col], errors="coerce")
    start_indexes = [idx for idx in df.index if pd.notna(ages.loc[idx]) and pd.notna(test_dates.loc[idx])]
    records = []
    current_site = "Not specified"

    for position, start_idx in enumerate(start_indexes):
        row = df.loc[start_idx]
        if site_col and pd.notna(row.get(site_col)):
            current_site = str(row.get(site_col)).strip()
        age = pd.to_numeric(row.get(age_col), errors="coerce")
        if pd.isna(age) or int(age) != 28:
            continue

        end_idx = start_indexes[position + 1] if position + 1 < len(start_indexes) else len(df)
        sample_block = df.loc[start_idx:end_idx - 1]
        if strength_col:
            strengths = pd.to_numeric(sample_block[strength_col], errors="coerce").dropna().astype(float).tolist()
        else:
            loads = pd.to_numeric(sample_block[load_col], errors="coerce").dropna()
            strengths = (loads * load_to_mpa).astype(float).tolist()
        # Ignore pending/unentered tests commonly stored as zero-strength rows.
        strengths = [value for value in strengths if value > 0]
        if not strengths:
            continue

        specified_value = pd.to_numeric(row.get(specified_col), errors="coerce") if specified_col else np.nan
        if pd.isna(specified_value):
            specified_value = specified_from_name
        if pd.isna(specified_value):
            continue

        test_date = pd.to_datetime(row.get(test_col), errors="coerce")
        cast_date = pd.to_datetime(row.get(cast_col), errors="coerce") if cast_col else pd.NaT
        record = {
            "test_date": test_date,
            "cast_date": cast_date,
            "specified_strength": float(specified_value),
            "test_average": float(np.mean(strengths)),
            "sample_count": len(strengths),
            "supplier": current_site if current_site else "Not specified",
            "mix_id": f"M{float(specified_value):g}",
            "grade": f"M{float(specified_value):g}",
            "structure": sheet_name,
            "age_days": age,
            "serial_no": row.get(cube_id_col) if cube_id_col else None,
            "remarks": row.get(remarks_col) if remarks_col else None,
        }
        for sample_no, strength in enumerate(strengths, start=1):
            record[f"cube_{sample_no}"] = strength
        records.append(record)

    return pd.DataFrame(records)


def _looks_like_cube_log(raw: pd.DataFrame) -> bool:
    text = " ".join(raw.head(8).astype(str).fillna("").values.ravel()).lower()
    return "cube compressive strength log" in text or ("strength" in text and "avg" in text and "test" in text)


def _clean_cell_text(value) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _parse_grade_value(value) -> float:
    text = str(value)
    match = re.search(r"M\s*[-_ ]?\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.notna(numeric) and 5 <= float(numeric) <= 100:
        return float(numeric)
    return np.nan


def _extract_sqc_grade(sheet_name: str, raw: pd.DataFrame) -> float:
    # User-specified SQC format keeps concrete grade in Excel cell G4.
    if raw.shape[0] >= 4 and raw.shape[1] >= 7:
        grade = _parse_grade_value(raw.iat[3, 6])
        if pd.notna(grade):
            return grade
    return _extract_grade_strength(sheet_name, raw)


def _find_sqc_header_row(raw: pd.DataFrame) -> int | None:
    scan_rows = min(len(raw), 60)
    for idx in range(scan_rows):
        row_text = " ".join(_clean_cell_text(value) for value in raw.iloc[idx].tolist())
        if "compress" in row_text and "strength" in row_text and (
            "moving" in row_text or "ucl" in row_text or "lcl" in row_text
        ):
            return idx
    return None


def _header_text(raw: pd.DataFrame, header_row: int, col: int) -> str:
    parts = []
    for row_idx in range(max(0, header_row - 1), min(len(raw), header_row + 3)):
        if col < raw.shape[1]:
            text = _clean_cell_text(raw.iat[row_idx, col])
            if text and text != "nan":
                parts.append(text)
    return " ".join(parts)


def _find_sqc_column(
    raw: pd.DataFrame,
    header_row: int,
    include: tuple[str, ...],
    exclude: tuple[str, ...] = (),
) -> int | None:
    for col in range(raw.shape[1]):
        text = _header_text(raw, header_row, col)
        if all(word in text for word in include) and not any(word in text for word in exclude):
            return col
    return None


def _date_like_count(series: pd.Series) -> int:
    parsed = pd.to_datetime(series, errors="coerce")
    return int(parsed.notna().sum())


def _find_sqc_date_column(raw: pd.DataFrame, header_row: int, strength_col: int) -> int | None:
    labelled = _find_sqc_column(raw, header_row, ("date",))
    if labelled is not None:
        return labelled
    data_start = header_row + 1
    best_col = None
    best_count = 0
    search_limit = strength_col if strength_col is not None and strength_col > 0 else raw.shape[1]
    for col in range(search_limit):
        count = _date_like_count(raw.iloc[data_start:, col])
        if count > best_count:
            best_col = col
            best_count = count
    return best_col if best_count >= 2 else None


def normalise_sqc_strength_table(raw: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """Parse legacy SQC sheets with grade in G4 and 28-day date derivation.

    The sheet records one compressive-strength value per row, commonly in
    kg/cm2, and may provide a 4-result moving average. The dashboard converts
    strengths to MPa, derives test date as available date + 28 days, and keeps
    the supplied 4-test moving average as a reference column.
    """
    if raw.empty:
        return pd.DataFrame()

    header_row = _find_sqc_header_row(raw)
    specified = _extract_sqc_grade(sheet_name, raw)
    if header_row is None or pd.isna(specified):
        return pd.DataFrame()

    moving_col = _find_sqc_column(raw, header_row, ("moving", "average"))
    strength_col = _find_sqc_column(raw, header_row, ("compress", "strength"), ("moving", "average"))
    if strength_col is None:
        strength_col = _find_sqc_column(raw, header_row, ("strength",), ("moving", "average"))
    if strength_col is None:
        return pd.DataFrame()

    date_col = _find_sqc_date_column(raw, header_row, strength_col)
    if date_col is None:
        return pd.DataFrame()

    lcl_col = _find_sqc_column(raw, header_row, ("lcl",))
    ucl_col = _find_sqc_column(raw, header_row, ("ucl",))
    sl_no_col = _find_sqc_column(raw, header_row, ("sl",))
    supplier_col = _find_sqc_column(raw, header_row, ("supplier",)) or _find_sqc_column(raw, header_row, ("source",))
    structure_col = (
        _find_sqc_column(raw, header_row, ("structure",))
        or _find_sqc_column(raw, header_row, ("location",))
        or _find_sqc_column(raw, header_row, ("site",))
    )

    body = raw.iloc[header_row + 1:].copy().reset_index(drop=True)
    strengths_raw = pd.to_numeric(body.iloc[:, strength_col], errors="coerce")
    nonzero_strengths = strengths_raw.dropna()
    if nonzero_strengths.empty:
        return pd.DataFrame()

    # Legacy SQC sheets normally store strength in kg/cm2. The source workbook
    # uses the civil-site convention MPa = kg/cm2 / 10, e.g. LCL 203.9 -> 20.39
    # and UCL 311.7 -> 31.17. Keep that convention for display and capability.
    convert_strength = float(nonzero_strengths.median()) > 100
    factor = 0.1 if convert_strength else 1.0

    records = []
    current_available_date = pd.NaT
    for idx, row in body.iterrows():
        row_date = pd.to_datetime(row.iloc[date_col], errors="coerce")
        if pd.notna(row_date):
            current_available_date = row_date

        sl_no = pd.to_numeric(row.iloc[sl_no_col], errors="coerce") if sl_no_col is not None else idx + 1
        strength_value = pd.to_numeric(row.iloc[strength_col], errors="coerce")
        if pd.isna(sl_no) or pd.isna(strength_value) or float(strength_value) <= 0:
            continue

        # In this SQC format the date is commonly entered only on the first
        # cube row of a set. Blank date rows below it are the same sample date,
        # so forward-fill the last valid date before adding 28 days.
        available_date = current_available_date
        if pd.isna(available_date):
            continue
        test_date = available_date + pd.Timedelta(days=28)

        moving_avg_4 = np.nan
        if moving_col is not None:
            moving_raw = pd.to_numeric(row.iloc[moving_col], errors="coerce")
            if pd.notna(moving_raw):
                moving_avg_4 = float(moving_raw) * factor

        lcl_value = np.nan
        if lcl_col is not None:
            lcl_raw = pd.to_numeric(row.iloc[lcl_col], errors="coerce")
            if pd.notna(lcl_raw):
                lcl_value = float(lcl_raw) * factor

        ucl_value = np.nan
        if ucl_col is not None:
            ucl_raw = pd.to_numeric(row.iloc[ucl_col], errors="coerce")
            if pd.notna(ucl_raw):
                ucl_value = float(ucl_raw) * factor

        supplier = (
            str(row.iloc[supplier_col]).strip()
            if supplier_col is not None and pd.notna(row.iloc[supplier_col])
            else "Not specified"
        )
        structure = (
            str(row.iloc[structure_col]).strip()
            if structure_col is not None and pd.notna(row.iloc[structure_col])
            else sheet_name
        )

        records.append(
            {
                "test_date": test_date,
                "cast_date": available_date,
                "specified_strength": float(specified),
                "test_average": float(strength_value) * factor,
                "cube_1": float(strength_value) * factor,
                "sample_count": 1,
                "supplier": supplier,
                "mix_id": f"M{float(specified):g}",
                "grade": f"M{float(specified):g}",
                "structure": structure,
                "age_days": 28,
                "serial_no": int(sl_no) if pd.notna(sl_no) else idx + 1,
                "moving_avg_4_source": moving_avg_4,
                "source_lcl": lcl_value,
                "source_ucl": ucl_value,
                "source_format": "SQC G4 grade / date + 28 days",
                "source_strength_unit": "kg/cm2" if convert_strength else "MPa",
            }
        )

    if not records:
        return pd.DataFrame()
    parsed = pd.DataFrame(records)
    parsed["moving_avg_4_calculated"] = parsed["test_average"].rolling(window=4).mean()
    return parsed


def _extract_grade_strength(sheet_name: str, raw: pd.DataFrame) -> float:
    candidates = [sheet_name] + [str(value) for value in raw.head(10).values.ravel() if pd.notna(value)]
    for candidate in candidates:
        match = re.search(r"\bM\s*[-_ ]?\s*(\d+(?:\.\d+)?)\b", candidate, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return np.nan


def normalise_cube_log(raw: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    specified = _extract_grade_strength(sheet_name, raw)
    header_row = _find_header_row(raw)
    data_start = header_row + 2 if header_row is not None else 4
    body = raw.iloc[data_start:].copy().reset_index(drop=True)

    # Cube strength in MPa = load in kN * 1000 / loaded area in mm2.
    # The workbook values match 150 mm cubes: 512 kN / 22.5 = 22.76 MPa.
    cube_area_mm2 = 150 * 150
    load_to_mpa = 1000 / cube_area_mm2

    age_series = pd.to_numeric(body.iloc[:, 9], errors="coerce")
    avg_series = pd.to_numeric(body.iloc[:, 15], errors="coerce")
    test_date_series = pd.to_datetime(body.iloc[:, 10], errors="coerce")
    start_indexes = [
        idx for idx in body.index
        if pd.notna(avg_series.iloc[idx]) and pd.notna(age_series.iloc[idx]) and pd.notna(test_date_series.iloc[idx])
    ]

    records = []
    current_serial = None
    current_cast_date = pd.NaT
    current_pour_detail = "Not specified"
    current_source = "Not specified"

    for position, start_idx in enumerate(start_indexes):
        row = body.iloc[start_idx]
        serial = row.get(0)
        cast_date = row.get(4)
        pour_detail = row.get(6)
        source = row.get(16)
        if pd.notna(serial):
            current_serial = serial
        if pd.notna(cast_date):
            current_cast_date = cast_date
        if pd.notna(pour_detail):
            current_pour_detail = str(pour_detail).strip()
        if pd.notna(source):
            current_source = str(source).strip()

        age = pd.to_numeric(row.get(9), errors="coerce")
        if pd.isna(age) or int(age) != 28:
            continue

        end_idx = start_indexes[position + 1] if position + 1 < len(start_indexes) else len(body)
        sample_block = body.iloc[start_idx:end_idx]
        max_loads = pd.to_numeric(sample_block.iloc[:, 13], errors="coerce").dropna()
        if max_loads.empty:
            continue

        strengths = (max_loads * load_to_mpa).astype(float).tolist()
        test_average = float(np.mean(strengths))
        test_date = pd.to_datetime(row.get(10), errors="coerce")
        cast_date_value = pd.to_datetime(current_cast_date, errors="coerce")
        if pd.notna(test_date) and test_date.year < 2000 and pd.notna(cast_date_value):
            test_date = cast_date_value + pd.Timedelta(days=int(age))
        if pd.isna(test_date):
            continue

        record = {
            "test_date": test_date,
            "cast_date": cast_date_value,
            "specified_strength": specified,
            "test_average": test_average,
            "sample_count": len(strengths),
            "supplier": current_source if current_source else "Not specified",
            "mix_id": f"M{specified:g}" if not pd.isna(specified) else "Not specified",
            "grade": f"M{specified:g}" if not pd.isna(specified) else "Not specified",
            "structure": current_pour_detail if current_pour_detail else "Not specified",
            "age_days": age,
            "serial_no": current_serial,
            "remarks": row.get(17),
        }
        for sample_no, strength in enumerate(strengths, start=1):
            record[f"cube_{sample_no}"] = strength
        records.append(record)

    return pd.DataFrame(records)

def _find_header_row(raw: pd.DataFrame) -> int | None:
    for idx in range(min(12, len(raw))):
        row_text = " ".join(str(value).lower() for value in raw.iloc[idx].tolist())
        if "s. no" in row_text and "strength" in row_text:
            return idx
    return None


def prepare_data(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    data = pd.DataFrame()
    data["test_date"] = pd.to_datetime(df[mapping["test_date"]], errors="coerce")
    data["specified_strength"] = pd.to_numeric(df[mapping["specified_strength"]], errors="coerce")

    for key in ["supplier", "mix_id", "grade", "structure"]:
        data[key] = df[mapping[key]].astype(str).str.strip() if key in mapping else "Not specified"

    for extra in [
        "cast_date", "age_days", "serial_no", "remarks", "sample_count",
        "moving_avg_4_source", "moving_avg_4_calculated", "source_lcl",
        "source_ucl", "source_format", "source_strength_unit",
    ]:
        if extra in df.columns:
            data[extra] = df[extra]

    cube_cols = []
    generated_cube_cols = [col for col in df.columns if str(col).startswith("cube_")]
    for key in sorted(generated_cube_cols, key=lambda value: int(str(value).split("_")[1]) if str(value).split("_")[1].isdigit() else 999):
        data[key] = pd.to_numeric(df[key], errors="coerce")
        cube_cols.append(key)
    if not cube_cols:
        for key in ["cube_1", "cube_2", "cube_3"]:
            if key in mapping:
                data[key] = pd.to_numeric(df[mapping[key]], errors="coerce")
                cube_cols.append(key)

    if "test_average" in mapping:
        data["test_average"] = pd.to_numeric(df[mapping["test_average"]], errors="coerce")
    else:
        data["test_average"] = data[cube_cols].mean(axis=1)

    if cube_cols:
        cube_values = data[cube_cols].apply(pd.to_numeric, errors="coerce")
        data["subgroup_range"] = cube_values.max(axis=1) - cube_values.min(axis=1)
        data["subgroup_size"] = cube_values.notna().sum(axis=1)
    elif "sample_count" in data.columns:
        data["subgroup_range"] = np.nan
        data["subgroup_size"] = pd.to_numeric(data["sample_count"], errors="coerce")
    else:
        data["subgroup_range"] = np.nan
        data["subgroup_size"] = np.nan

    data = data.dropna(subset=["test_date", "specified_strength", "test_average"]).copy()
    data = data.sort_values("test_date").reset_index(drop=True)
    data["test_no"] = np.arange(1, len(data) + 1)
    return data


def aci_compliance(data: pd.DataFrame) -> pd.DataFrame:
    """Evaluate acceptance using IS 456 grade-wise concrete criteria.

    IS 456 acceptance is based on characteristic strength fck, assumed standard
    deviation from the concrete grade, target mean strength fck + 1.65*s, and
    the acceptance condition for four consecutive results: mean >= max(fck +
    0.825*s, fck + 3). Individual test results are checked against fck - 3.
    The historical 3-test moving average column is retained only as a reference.
    """
    result = data.copy()
    result["moving_avg_3"] = result["test_average"].rolling(window=3).mean()
    result["moving_avg_4"] = result["test_average"].rolling(window=4).mean()
    result["is456_assumed_sd"] = result["specified_strength"].apply(is456_assumed_sd)
    result["is456_target_mean_strength"] = result["specified_strength"] + 1.65 * result["is456_assumed_sd"]
    result["is456_required_4_avg"] = np.maximum(
        result["specified_strength"] + 0.825 * result["is456_assumed_sd"],
        result["specified_strength"] + 3.0,
    )
    result["four_test_avg_ok"] = result["moving_avg_4"].isna() | (
        result["moving_avg_4"] >= result["is456_required_4_avg"]
    )
    result["minimum_allowed_test_avg"] = result["specified_strength"] - 3.0
    result["single_test_ok"] = result["test_average"] >= result["minimum_allowed_test_avg"]
    result["is456_compliant"] = result["four_test_avg_ok"] & result["single_test_ok"]
    result["aci_compliant"] = result["is456_compliant"]
    return result


def six_sigma_metrics(data: pd.DataFrame, usl: float | None = None) -> Dict[str, float]:
    values = data["test_average"].dropna()
    target = float(data["specified_strength"].median()) if len(data) else np.nan
    mean = float(values.mean()) if len(values) else np.nan
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    cv = float(std / mean * 100) if mean else np.nan
    lsl = target
    usl_value = float(usl) if usl is not None and not pd.isna(usl) and float(usl) > lsl else np.nan

    x_min = float(values.min()) if len(values) else np.nan
    x_max = float(values.max()) if len(values) else np.nan
    x_range = float(x_max - x_min) if not np.isnan(x_min) and not np.isnan(x_max) else np.nan
    deviations = values - mean if len(values) and not np.isnan(mean) else pd.Series(dtype=float)
    squared_deviation_sum = float((deviations ** 2).sum()) if len(deviations) else np.nan

    # SQC reference-sheet control limit formula supplied by the user:
    # j = standard deviation = sqrt(sum((X - Xbar)^2) / (n - 1))
    # r = (Xbar - Xmin) / j
    # LCL = Xbar - r*j ; UCL = Xbar + r*j
    # Example in SQC source units: 203.9 and 311.7 kg/cm2 display as
    # 20.39 and 31.17 MPa/N-mm2 after the /10 SQC conversion during import.
    tolerance_r = float((mean - x_min) / std) if std and not np.isnan(mean) and not np.isnan(x_min) else np.nan
    sqc_lcl = float(mean - tolerance_r * std) if std and not np.isnan(tolerance_r) else np.nan
    sqc_ucl = float(mean + tolerance_r * std) if std and not np.isnan(tolerance_r) else np.nan

    source_lcl = pd.to_numeric(data.get("source_lcl", pd.Series(dtype=float)), errors="coerce").dropna()
    source_ucl = pd.to_numeric(data.get("source_ucl", pd.Series(dtype=float)), errors="coerce").dropna()
    if len(source_lcl) and len(source_ucl):
        sqc_lcl = float(source_lcl.median())
        sqc_ucl = float(source_ucl.median())
        tolerance_r = float((sqc_ucl - mean) / std) if std and not np.isnan(mean) else tolerance_r

    ranges = pd.to_numeric(data.get("subgroup_range", pd.Series(dtype=float)), errors="coerce").dropna()
    sizes = pd.to_numeric(data.get("subgroup_size", pd.Series(dtype=float)), errors="coerce").dropna()
    subgroup_n = float(sizes.mode().iloc[0]) if len(sizes.mode()) else np.nan
    rbar = float(ranges.mean()) if len(ranges) else np.nan
    a2 = _a2_for_n(subgroup_n)

    # Regular Six Sigma/capability formula basis:
    # LSL is the grade characteristic strength fck. SQC LCL/UCL remain control
    # chart limits; UCL is used as USL only when a validated upper limit exists.
    calculated_lsl = lsl
    calculated_usl = usl_value if not np.isnan(usl_value) else sqc_ucl
    zbench = float((mean - lsl) / std) if std and not np.isnan(mean) and not np.isnan(lsl) else np.nan
    cpu = float((calculated_usl - mean) / (3 * std)) if std and not np.isnan(calculated_usl) and not np.isnan(mean) else np.nan
    cpl = float((mean - calculated_lsl) / (3 * std)) if std and not np.isnan(calculated_lsl) and not np.isnan(mean) else np.nan
    cp = float((calculated_usl - calculated_lsl) / (6 * std)) if std and not np.isnan(calculated_usl) and not np.isnan(calculated_lsl) and calculated_usl > calculated_lsl else np.nan
    cpk = float(min(cpu, cpl)) if not np.isnan(cpu) and not np.isnan(cpl) else np.nan
    pp = cp
    ppu = cpu
    ppl = cpl
    ppk_lower = cpl
    ppk = cpk
    cpm = np.nan
    target_mean_series = pd.to_numeric(data.get("is456_target_mean_strength", pd.Series(dtype=float)), errors="coerce").dropna()
    process_target = float(target_mean_series.median()) if len(target_mean_series) else (calculated_usl + calculated_lsl) / 2 if not np.isnan(calculated_usl) and not np.isnan(calculated_lsl) else np.nan
    if std and not np.isnan(calculated_usl) and not np.isnan(calculated_lsl) and not np.isnan(mean) and not np.isnan(process_target):
        cpm = float((calculated_usl - calculated_lsl) / (6 * math.sqrt(std ** 2 + (mean - process_target) ** 2)))
    cr = float(1 / cp) if not np.isnan(cp) and cp else np.nan
    z_target_delta = float((mean - lsl) / std) if std and not np.isnan(mean) and not np.isnan(lsl) else np.nan
    skewness = float(values.skew()) if len(values) > 2 else np.nan
    sigma_level = min(zbench, 6.0) if not np.isnan(zbench) else np.nan
    total_units = int(len(values))
    total_defects = int((values < lsl).sum()) if len(values) else 0
    opportunities_per_unit = 1
    dpu = float(total_defects / total_units) if total_units else np.nan
    dpo = float(total_defects / (total_units * opportunities_per_unit)) if total_units else np.nan
    dpmo = float(dpo * 1_000_000) if not np.isnan(dpo) else np.nan
    yield_percent = float((1 - dpo) * 100) if not np.isnan(dpo) else np.nan
    defects = float(dpo * 100) if not np.isnan(dpo) else np.nan
    ppm = dpmo
    expected_ppm_st = float(_normal_upper_tail(zbench) * 1_000_000) if not np.isnan(zbench) else np.nan
    expected_ppm_lt = float(_normal_upper_tail(zbench - 1.5) * 1_000_000) if not np.isnan(zbench) else np.nan
    reference_dpmo, reference_yield = sigma_reference_metrics(sigma_level)
    return {
        "mean": mean,
        "std_dev": std,
        "coefficient_of_variation": cv,
        "cp": cp,
        "cpk": cpk,
        "cpu": cpu,
        "cpl": cpl,
        "cpm": cpm,
        "cr": cr,
        "z_target_delta": z_target_delta,
        "pp": pp,
        "ppk": ppk,
        "ppk_lower": ppk_lower,
        "ppu": ppu,
        "ppl": ppl,
        "usl": calculated_usl,
        "calculated_usl": calculated_usl,
        "calculated_lsl": calculated_lsl,
        "process_target": process_target,
        "sigma_level": sigma_level,
        "zbench": zbench,
        "skewness": skewness,
        "defect_percentage": defects,
        "total_units": total_units,
        "total_defects": total_defects,
        "opportunities_per_unit": opportunities_per_unit,
        "dpu": dpu,
        "dpo": dpo,
        "dpmo": dpmo,
        "yield_percent": yield_percent,
        "reference_dpmo": reference_dpmo,
        "reference_yield_percent": reference_yield,
        "ppm": ppm,
        "expected_ppm_st": expected_ppm_st,
        "expected_ppm_lt": expected_ppm_lt,
        "lsl": lsl,
        "ucl": sqc_ucl,
        "lcl": sqc_lcl,
        "xbarbar": mean,
        "x_min": x_min,
        "x_max": x_max,
        "range": x_range,
        "deviation_sum_squares": squared_deviation_sum,
        "tolerance_r": tolerance_r,
        "j_std_dev": std,
        "variation_percent": cv,
        "rbar": rbar,
        "a2": a2,
        "subgroup_n": subgroup_n,
        "control_sigma": float((sqc_ucl - mean) / 3) if not np.isnan(sqc_ucl) and not np.isnan(mean) else np.nan,
        "upper_warning_limit": float(mean + 2 * ((sqc_ucl - mean) / 3)) if not np.isnan(sqc_ucl) and not np.isnan(mean) else np.nan,
        "lower_warning_limit": float(mean - 2 * ((sqc_ucl - mean) / 3)) if not np.isnan(sqc_ucl) and not np.isnan(mean) else np.nan,
        "upper_action_limit": sqc_ucl,
        "lower_action_limit": sqc_lcl,
        "control_chart_method": "SQC r*j" if not np.isnan(sqc_ucl) else "Unavailable",
    }



def _normal_cdf(z: float) -> float:
    if z is None or pd.isna(z):
        return np.nan
    return 0.5 * (1 + math.erf(float(z) / math.sqrt(2)))


def _normal_upper_tail(z: float) -> float:
    if z is None or pd.isna(z):
        return np.nan
    return 1 - _normal_cdf(z)


SIGMA_REFERENCE = {
    2: (308_770.0, 69.10),
    3: (66_811.0, 93.33),
    4: (6_210.0, 99.38),
    5: (233.0, 99.97),
    6: (3.4, 99.99),
}


def sigma_reference_metrics(sigma_level: float) -> tuple[float, float]:
    if sigma_level is None or pd.isna(sigma_level):
        return np.nan, np.nan
    sigma = max(2, min(6, int(round(float(sigma_level)))))
    return SIGMA_REFERENCE[sigma]


def _capability_class(value: float) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    rounded = round(float(value), 2)
    if rounded < 1.00:
        return "Critical"
    if rounded == 1.00:
        return "Moderate Risk"
    if rounded >= 1.33:
        return "Excellent"
    return "Good"


def capability_metrics_table(metrics: Dict[str, float]) -> pd.DataFrame:
    def val(name: str) -> float:
        return metrics.get(name, np.nan)

    def status(metric: str, value: float) -> str:
        if value is None or pd.isna(value):
            return "N/A"
        if metric in {"Cp", "Cpk", "CpU", "CpL", "Cpm", "Pp", "Ppk", "PpU", "PpL"}:
            return _capability_class(value)
        if metric == "Cr":
            if value <= 0.75:
                return "Good"
            if value <= 1.00:
                return "Monitor"
            return "Review"
        if metric in {"ZTarget/DeltaZ", "Z Bench", "Sigma"}:
            if value >= 4.50:
                return "Excellent"
            if value >= 3.00:
                return "Good"
            if value >= 2.00:
                return "Monitor"
            return "Critical"
        if metric == "% Defects":
            return "Good" if value == 0 else "Review"
        if metric == "PPM":
            return "Good" if value == 0 else "Review"
        if metric == "Skewness":
            return "Good" if abs(value) <= 0.5 else "Monitor" if abs(value) <= 1.0 else "Review"
        return "Information"

    def interpretation(metric: str, value: float) -> str:
        st = status(metric, value)
        if metric in {"Cp", "Cpk", "Pp", "Ppk"}:
            if st == "Excellent":
                return "Capability is excellent: value is 1.33 or higher."
            if st == "Good":
                return "Capability is good: value is above 1.00 and below 1.33."
            if st == "Moderate Risk":
                return "Capability is at the minimum boundary: displayed value is 1.00 and needs close monitoring."
            return "Critical capability below 1.00; process spread is high and needs immediate improvement."
        if metric in {"CpU", "PpU"}:
            return "Upper-side margin to calculated UCL/USL. Low value means high-side results are close to the upper limit."
        if metric in {"CpL", "PpL"}:
            return "Lower-side margin from calculated LCL. Low value means low-side results are close to the lower limit."
        if metric == "Cpm":
            return "Capability adjusted for deviation from target midpoint."
        if metric == "Cr":
            return "Capability ratio. Values above 1.00 indicate process spread exceeds the calculated tolerance band."
        if metric in {"ZTarget/DeltaZ", "Z Bench", "Sigma"}:
            return "Sigma rating: >=4.50 Excellent, >=3.00 Good, 2.00-2.99 Monitor, <2.00 Critical. Higher sigma means stronger margin above specified strength."
        if metric == "DPU":
            return "Defects per unit = total defective 28-day tests divided by total analysed tests."
        if metric == "DPO":
            return "Defects per opportunity = defects divided by units and opportunities per unit."
        if metric == "DPMO":
            return "Defects per million opportunities = DPO multiplied by 1,000,000."
        if metric == "Yield":
            return "Yield = 1 - DPO, expressed as a percentage."
        if metric == "Reference DPMO":
            return "Standard Six Sigma reference DPMO for the rounded reported sigma level."
        if metric == "Reference Yield":
            return "Standard Six Sigma reference yield for the rounded reported sigma level."
        if metric == "% Defects":
            return "Observed percentage of tests below specified strength."
        if metric == "PPM":
            return "Observed defects per million based on below-specification tests."
        if metric == "Exp PPM ST":
            return "Expected short-term defects per million from Zbench."
        if metric == "Exp PPM LT":
            return "Expected long-term defects per million after 1.5 sigma shift assumption."
        if metric == "Skewness":
            return "Distribution asymmetry. Negative skew indicates a longer low-strength tail."
        if metric == "Stdev":
            return "Overall process variation; lower standard deviation improves capability."
        if metric == "Range":
            return "Total spread between maximum and minimum test averages."
        return "Descriptive statistic used for capability and SQC interpretation."

    rows = [
        ("Cp", val("cp"), "(USL - LSL) / (6*Stdev); LSL = grade fck"),
        ("Cpk", val("cpk"), "min(CpU, CpL) using regular capability limits"),
        ("CpU", val("cpu"), "Upper capability = (USL - mean) / (3*Stdev)"),
        ("CpL", val("cpl"), "Lower capability = (mean - LSL) / (3*Stdev)"),
        ("Cpm", val("cpm"), "Taguchi capability around target"),
        ("Cr", val("cr"), "Capability ratio = 1/Cp"),
        ("ZTarget/DeltaZ", val("z_target_delta"), "Distance from target in standard deviations"),
        ("Pp", val("pp"), "Process performance = (USL - LSL) / (6*overall Stdev)"),
        ("Ppk", val("ppk"), "min(PpU, PpL) using regular performance limits"),
        ("PpU", val("ppu"), "Upper performance = (calculated UCL - mean) / (3*overall Stdev)"),
        ("PpL", val("ppl"), "Lower performance = (mean - LSL) / (3*overall Stdev)"),
        ("Skewness", val("skewness"), "Distribution skewness"),
        ("Stdev", val("std_dev"), "Sample standard deviation"),
        ("Min", val("x_min"), "Minimum test average"),
        ("Max", val("x_max"), "Maximum test average"),
        ("Range", val("range"), "Max - Min"),
        ("Z Bench", val("zbench"), "Lower-side Z = (mean - specified strength) / Stdev"),
        ("DPU", val("dpu"), "Defects / Total units"),
        ("DPO", val("dpo"), "Defects / (Units * Opportunities per unit)"),
        ("DPMO", val("dpmo"), "DPO * 1,000,000"),
        ("Yield", val("yield_percent"), "1 - DPO, expressed as percent"),
        ("Reference DPMO", val("reference_dpmo"), "Standard Six Sigma DPMO reference for rounded sigma level"),
        ("Reference Yield", val("reference_yield_percent"), "Standard Six Sigma yield reference for rounded sigma level"),
        ("% Defects", val("defect_percentage"), "Observed percent below specified strength"),
        ("PPM", val("ppm"), "Observed defects per million"),
        ("Exp PPM ST", val("expected_ppm_st"), "Expected short-term PPM from Zbench"),
        ("Exp PPM LT", val("expected_ppm_lt"), "Expected long-term PPM using 1.5 sigma shift"),
        ("Sigma", val("sigma_level"), "Reported Six Sigma level capped at 6.00 sigma"),
    ]
    output = []
    for metric, value, formula in rows:
        output.append({
            "Metric": metric,
            "Value": value,
            "Status": status(metric, value),
            "Interpretation": interpretation(metric, value),
            "Formula / Note": formula,
        })
    return pd.DataFrame(output)

def _metric_status(value: float, good: float, monitor: float, higher_is_better: bool = True) -> str:
    if value is None or pd.isna(value):
        return "Monitor"
    if higher_is_better:
        if value >= good:
            return "Good"
        if value >= monitor:
            return "Monitor"
        return "Critical"
    if value <= good:
        return "Good"
    if value <= monitor:
        return "Monitor"
    return "Critical"


def _sigma_status(value: float) -> str:
    if value is None or pd.isna(value):
        return "Monitor"
    if value >= 4.50:
        return "Excellent"
    if value >= 3.00:
        return "Good"
    if value >= 2.00:
        return "Monitor"
    return "Critical"

def risk_intelligence_table(data: pd.DataFrame, metrics: Dict[str, float], risk: Tuple[str, str], compliance_score: float) -> pd.DataFrame:
    non_compliant = int((~data["aci_compliant"]).sum()) if len(data) else 0
    warning_breaches = int(data.get("warning_limit_breach", pd.Series(dtype=bool)).sum()) if len(data) else 0
    action_breaches = int(data.get("action_limit_breach", pd.Series(dtype=bool)).sum()) if len(data) else 0
    outliers = int(data.get("outlier", pd.Series(dtype=bool)).sum()) if len(data) else 0

    cv = metrics.get("coefficient_of_variation", np.nan)
    cpk = metrics.get("cpk", np.nan)
    sigma = metrics.get("sigma_level", np.nan)
    defects = metrics.get("defect_percentage", np.nan)
    skew = metrics.get("skewness", np.nan)

    rows = [
        {
            "Signal": "IS 456 acceptance",
            "Calculated value": f"{compliance_score:.2f}% compliant; {non_compliant} non-compliant tests",
            "Interpretation": "IS 456 acceptance is satisfied." if compliance_score >= 100 else "Some tests fail IS 456 acceptance.",
            "Status": "Good" if compliance_score >= 100 else "Critical" if compliance_score < 90 else "Monitor",
            "Recommended action": "Continue routine monitoring." if compliance_score >= 100 else "Investigate failed tests and affected pour locations.",
        },
        {
            "Signal": "Process capability",
            "Calculated value": f"Cp={metrics.get('cp', np.nan):.3f}, Cpk={cpk:.3f}",
            "Interpretation": "Capability is excellent: Cpk is 1.33 or higher." if _capability_class(cpk) == "Excellent" else "Capability is good: Cpk is above 1.00 and below 1.33." if _capability_class(cpk) == "Good" else "Capability is at the minimum boundary: Cpk displays as 1.00 and needs close monitoring." if _capability_class(cpk) == "Moderate Risk" else "Critical capability below 1.00; process spread is high against specification limits.",
            "Status": _capability_class(cpk),
            "Recommended action": "Maintain current controls." if _capability_class(cpk) in {"Excellent", "Good"} else "Monitor closely and reduce variation." if _capability_class(cpk) == "Moderate Risk" else "Immediate variation reduction required: review batching, curing, materials, and test procedure consistency.",
        },
        {
            "Signal": "Sigma / Zbench",
            "Calculated value": f"{sigma:.3f} sigma",
            "Interpretation": "Excellent capability margin above specified strength." if not pd.isna(sigma) and sigma >= 4.5 else "Good capability margin above specified strength." if not pd.isna(sigma) and sigma >= 3 else "Margin above specified strength requires monitoring." if not pd.isna(sigma) and sigma >= 2 else "Critical low sigma margin above specified strength.",
            "Status": _sigma_status(sigma),
            "Recommended action": "Maintain current controls and continue trend monitoring." if not pd.isna(sigma) and sigma >= 3 else "Improve mean strength or reduce standard deviation.",
        },
        {
            "Signal": "Coefficient of variation",
            "Calculated value": f"{cv:.2f}%",
            "Interpretation": "Variation is controlled." if not pd.isna(cv) and cv <= 8 else "Variation needs attention." if not pd.isna(cv) and cv <= 10 else "High variability detected.",
            "Status": _metric_status(cv, 8, 10, higher_is_better=False),
            "Recommended action": "Maintain production consistency." if not pd.isna(cv) and cv <= 8 else "Check source material consistency, water control, batching, curing, and testing repeatability.",
        },
        {
            "Signal": "SQC warning/action limits",
            "Calculated value": f"Warnings={warning_breaches}, Actions={action_breaches}",
            "Interpretation": "No special-cause signal detected." if action_breaches == 0 else "Special-cause variation indicated by action-limit breach.",
            "Status": "Good" if action_breaches == 0 and warning_breaches == 0 else "Monitor" if action_breaches == 0 else "Critical",
            "Recommended action": "Continue monitoring." if action_breaches == 0 else "Immediate process review: verify mix design, batching records, curing, sampling, and testing equipment.",
        },
        {
            "Signal": "Defects and PPM",
            "Calculated value": f"Observed defects={defects:.2f}%, PPM={metrics.get('ppm', np.nan):.0f}",
            "Interpretation": "No observed below-specification defects." if not pd.isna(defects) and defects == 0 else "Below-specification results are present.",
            "Status": "Good" if not pd.isna(defects) and defects == 0 else "Critical",
            "Recommended action": "No defect correction needed." if not pd.isna(defects) and defects == 0 else "Trace defective batches and isolate affected structures/suppliers.",
        },
        {
            "Signal": "Distribution shape",
            "Calculated value": f"Skewness={skew:.3f}, Outliers={outliers}",
            "Interpretation": "Distribution is reasonably balanced." if not pd.isna(skew) and abs(skew) <= 0.5 and outliers == 0 else "Distribution or outliers need review.",
            "Status": "Good" if not pd.isna(skew) and abs(skew) <= 0.5 and outliers == 0 else "Monitor",
            "Recommended action": "No distribution action needed." if not pd.isna(skew) and abs(skew) <= 0.5 and outliers == 0 else "Review low/high tail results and confirm test records.",
        },
        {
            "Signal": "Overall risk",
            "Calculated value": risk[0],
            "Interpretation": risk[1],
            "Status": risk[0],
            "Recommended action": "Use the highest-severity signals above to prioritize corrective action.",
        },
    ]
    return pd.DataFrame(rows)


def interpretation_summary(data: pd.DataFrame, metrics: Dict[str, float], risk: Tuple[str, str], compliance_score: float) -> List[str]:
    table = risk_intelligence_table(data, metrics, risk, compliance_score)
    return [
        f"{row['Signal']}: {row['Calculated value']} - {row['Interpretation']} Recommended action: {row['Recommended action']}"
        for _, row in table.iterrows()
    ]

def detect_abnormalities(data: pd.DataFrame, metrics: Dict[str, float]) -> pd.DataFrame:
    result = data.copy()
    std = metrics["std_dev"]
    mean = metrics["mean"]
    uwl = metrics.get("upper_warning_limit", np.nan)
    lwl = metrics.get("lower_warning_limit", np.nan)
    ual = metrics.get("upper_action_limit", np.nan)
    lal = metrics.get("lower_action_limit", np.nan)
    result["outlier"] = False if not std else (result["test_average"] - mean).abs() > 2 * std
    result["warning_limit_breach"] = False
    if not np.isnan(uwl) and not np.isnan(lwl):
        result["warning_limit_breach"] = result["test_average"].gt(uwl) | result["test_average"].lt(lwl)
    result["action_limit_breach"] = False
    if not np.isnan(ual) and not np.isnan(lal):
        result["action_limit_breach"] = result["test_average"].gt(ual) | result["test_average"].lt(lal)
    result["sudden_drop"] = result["test_average"].diff() <= -5
    result["high_variation"] = metrics["coefficient_of_variation"] > 10
    result["repeated_low_trend"] = (
        result["test_average"].lt(result["specified_strength"]).rolling(3).sum().fillna(0) >= 2
    )
    return result


def classify_risk(data: pd.DataFrame, metrics: Dict[str, float]) -> Tuple[str, str]:
    non_compliant = (~data["aci_compliant"]).any()
    action_limit_breach = data.get("action_limit_breach", pd.Series(False, index=data.index)).any()
    trend_concern = data[["outlier", "sudden_drop", "repeated_low_trend", "warning_limit_breach"]].any().any()
    marginal = round(float(metrics["ppk"]), 2) <= 1.00 if not np.isnan(metrics["ppk"]) else False
    high_variation = metrics["coefficient_of_variation"] > 10
    if action_limit_breach:
        return "Red", "One or more tests fall outside SPC action limits, indicating special-cause variation."
    if non_compliant:
        return "Red", "One or more tests fail the IS 456 acceptance checks."
    if trend_concern or marginal or high_variation:
        return "Amber", "Compliant overall, but variation or trend signals need attention."
    return "Green", "Compliant with stable process indicators."



def aci214_process_classification(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(
            columns=[
                "Supplier",
                "Concrete Type",
                "Tests",
                "Mean Strength (MPa)",
                "Standard Deviation (MPa)",
                "Coefficient of Variation (%)",
                "Process Performance according to ACI214R-02",
            ]
        )

    grouped = (
        data.groupby(["supplier", "grade"], dropna=False)["test_average"]
        .agg(["count", "mean", "std"])
        .reset_index()
    )
    grouped["cv"] = grouped["std"] / grouped["mean"] * 100

    def classify(cv: float) -> str:
        if pd.isna(cv):
            return "Not enough data"
        if cv <= 6:
            return "Excellent"
        if cv <= 8:
            return "Very Good"
        if cv <= 10:
            return "Good"
        if cv <= 12:
            return "Fair"
        return "Poor"

    grouped["class"] = grouped["cv"].apply(classify)
    return pd.DataFrame(
        {
            "Supplier": grouped["supplier"],
            "Concrete Type": grouped["grade"],
            "Tests": grouped["count"].astype(int),
            "Mean Strength (MPa)": grouped["mean"].round(3),
            "Standard Deviation (MPa)": grouped["std"].round(3),
            "Coefficient of Variation (%)": grouped["cv"].round(2),
            "Process Performance according to ACI214R-02": grouped["class"],
        }
    ).sort_values(["Supplier", "Concrete Type"]).reset_index(drop=True)

def positive_insights(data: pd.DataFrame) -> Dict[str, str]:
    insights = {}
    if not data.empty:
        insights["Best supplier"] = _best_mean(data, "supplier")
        insights["Best mix ID"] = _best_mean(data, "mix_id")
        insights["Strongest grade"] = _best_mean(data, "grade")
        insights["Most consistent structure"] = _lowest_cv(data, "structure")
    return insights


def _best_mean(data: pd.DataFrame, column: str) -> str:
    grouped = data.groupby(column)["test_average"].mean().sort_values(ascending=False)
    if grouped.empty:
        return "Not available"
    return f"{grouped.index[0]} ({grouped.iloc[0]:.2f} MPa avg)"


def _lowest_cv(data: pd.DataFrame, column: str) -> str:
    grouped = data.groupby(column)["test_average"].agg(["mean", "std", "count"])
    grouped = grouped[grouped["count"] >= 2].copy()
    if grouped.empty:
        return "Not enough repeated tests"
    grouped["cv"] = grouped["std"] / grouped["mean"] * 100
    best = grouped.sort_values("cv").iloc[0]
    return f"{grouped.sort_values('cv').index[0]} ({best['cv']:.2f}% CV)"


def _safe_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", "_", str(name))[:31]
    return cleaned or "Sheet"


def export_report(
    analysed: pd.DataFrame,
    metrics: Dict[str, float],
    risk: Tuple[str, str],
    insights: Dict[str, str],
    all_data: pd.DataFrame | None = None,
) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        analysed.to_excel(writer, sheet_name="Analysed Data", index=False)
        pd.DataFrame([metrics]).to_excel(writer, sheet_name="Six Sigma Metrics", index=False)
        pd.DataFrame([{"risk": risk[0], "summary": risk[1]}]).to_excel(
            writer, sheet_name="Risk Classification", index=False
        )
        pd.DataFrame(insights.items(), columns=["Insight", "Result"]).to_excel(
            writer, sheet_name="Positive Insights", index=False
        )
        aci214_process_classification(analysed).to_excel(
            writer, sheet_name="ACI214 Process Class", index=False
        )
        capability_metrics_table(metrics).to_excel(
            writer, sheet_name="Capability Metrics", index=False
        )
        compliance_score = float(analysed["aci_compliant"].mean() * 100) if len(analysed) else 0
        risk_intelligence_table(analysed, metrics, risk, compliance_score).to_excel(
            writer, sheet_name="Risk Intelligence", index=False
        )
        if all_data is not None and not all_data.empty and "grade" in all_data.columns:
            grade_summary_rows = []
            for grade, grade_data in all_data.groupby("grade", dropna=False):
                grade_label = str(grade)
                grade_data = grade_data.sort_values("test_date").reset_index(drop=True)
                grade_data["test_no"] = range(1, len(grade_data) + 1)
                grade_analysed = aci_compliance(grade_data)
                grade_metrics = six_sigma_metrics(grade_analysed)
                grade_analysed = detect_abnormalities(grade_analysed, grade_metrics)
                grade_risk = classify_risk(grade_analysed, grade_metrics)
                grade_compliance = float(grade_analysed["aci_compliant"].mean() * 100) if len(grade_analysed) else 0
                prefix = _safe_sheet_name(grade_label)
                grade_analysed.to_excel(writer, sheet_name=_safe_sheet_name(f"{prefix} Data"), index=False)
                capability_metrics_table(grade_metrics).to_excel(writer, sheet_name=_safe_sheet_name(f"{prefix} Metrics"), index=False)
                risk_intelligence_table(grade_analysed, grade_metrics, grade_risk, grade_compliance).to_excel(writer, sheet_name=_safe_sheet_name(f"{prefix} Risk"), index=False)
                grade_summary_rows.append({
                    "Grade": grade_label,
                    "Tests": len(grade_analysed),
                    "Mean": grade_metrics.get("mean"),
                    "Std Dev": grade_metrics.get("std_dev"),
                    "LCL": grade_metrics.get("lcl"),
                    "UCL/USL": grade_metrics.get("ucl"),
                    "Cp": grade_metrics.get("cp"),
                    "Cpk": grade_metrics.get("cpk"),
                    "Sigma": grade_metrics.get("sigma_level"),
                    "IS 456 Compliance %": grade_compliance,
                    "Risk": grade_risk[0],
                })
            pd.DataFrame(grade_summary_rows).to_excel(writer, sheet_name="Grade Summary", index=False)
    return output.getvalue()
