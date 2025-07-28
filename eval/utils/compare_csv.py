import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from difflib import SequenceMatcher


def compare_dataframes(
    df1: pd.DataFrame, df2: pd.DataFrame, tolerance: float = 0.0001
) -> Dict[str, Any]:
    """
    Compare two dataframes cell by cell and return detailed results with column-specific scores.

    Args:
        df1 (pd.DataFrame): First dataframe
        df2 (pd.DataFrame): Second dataframe
        tolerance (float): Tolerance for numerical comparisons

    Returns:
        Dict containing comparison results including column-specific scores
    """
    print(f"[COMPARE] Starting dataframe comparison with tolerance: {tolerance}")
    print(f"[COMPARE] DF1 shape: {df1.shape}, DF2 shape: {df2.shape}")

    # First perform header comparison
    header_results = compare_headers(df1, df2)

    total_cells = df1.size
    matches = 0
    differences = 0

    print(f"[COMPARE] Total cells to compare: {total_cells}")

    # Track different types of differences
    numerical_differences = []
    string_differences = []
    missing_values = []
    type_mismatches = []

    # Track column-specific scores for bank statement fields
    column_scores = {}
    column_matches = {}
    column_totals = {}

    cell_count = 0

    # Compare cell by cell
    print("[COMPARE] Starting cell-by-cell comparison...")
    for idx in df1.index:
        for col in df1.columns:
            cell_count += 1
            val1 = df1.loc[idx, col]
            val2 = df2.loc[idx, col]

            # Initialize column tracking
            if col not in column_matches:
                column_matches[col] = 0
                column_totals[col] = 0

            column_totals[col] += 1

            # Debug every 100th cell or if it's one of the first 5 cells
            is_debug_cell = (cell_count % 100 == 0) or (cell_count <= 5)

            if is_debug_cell:
                print(
                    f"[COMPARE] Cell {cell_count}/{total_cells} - Index: {idx}, Column: {col}"
                )

            # Check for missing values
            if pd.isna(val1) and pd.isna(val2):
                matches += 1
                column_matches[col] += 1
                if is_debug_cell:
                    print(f"    Both values are NaN - MATCH")
            elif pd.isna(val1) or pd.isna(val2):
                differences += 1
                missing_values.append(
                    {"index": idx, "column": col, "df1_value": val1, "df2_value": val2}
                )
                if is_debug_cell:
                    print(f"    Missing value difference - DIFF")
            else:
                # Compare values based on type
                if is_numeric_comparison(val1, val2):
                    numeric_diff = abs(float(val1) - float(val2))
                    if numeric_diff <= tolerance:
                        matches += 1
                        column_matches[col] += 1
                        if is_debug_cell:
                            print(
                                f"    Numeric values within tolerance ({numeric_diff:.6f} <= {tolerance}) - MATCH"
                            )
                    else:
                        differences += 1
                        numerical_differences.append(
                            {
                                "index": idx,
                                "column": col,
                                "df1_value": val1,
                                "df2_value": val2,
                                "difference": numeric_diff,
                            }
                        )
                        if is_debug_cell:
                            print(
                                f"    Numeric values exceed tolerance ({numeric_diff:.6f} > {tolerance}) - DIFF"
                            )
                else:
                    # String comparison
                    if str(val1) == str(val2):
                        matches += 1
                        column_matches[col] += 1
                        if is_debug_cell:
                            print(f"    String values match - MATCH")
                    else:
                        differences += 1
                        if type(val1) != type(val2):
                            type_mismatches.append(
                                {
                                    "index": idx,
                                    "column": col,
                                    "df1_value": val1,
                                    "df1_type": type(val1).__name__,
                                    "df2_value": val2,
                                    "df2_type": type(val2).__name__,
                                }
                            )
                            if is_debug_cell:
                                print(
                                    f"    Type mismatch ({type(val1).__name__} vs {type(val2).__name__}) - DIFF"
                                )
                        else:
                            string_differences.append(
                                {
                                    "index": idx,
                                    "column": col,
                                    "df1_value": val1,
                                    "df2_value": val2,
                                }
                            )
                            if is_debug_cell:
                                print(f"    String values differ - DIFF")

    # Calculate column-specific scores
    for col in column_matches:
        if column_totals[col] > 0:
            column_scores[col] = round(
                (column_matches[col] / column_totals[col]) * 100, 2
            )
        else:
            column_scores[col] = 0.0

    # Calculate overall match percentage
    match_percentage = (matches / total_cells * 100) if total_cells > 0 else 0

    # Map columns to expected bank statement fields and calculate specific scores
    bank_statement_scores = calculate_bank_statement_scores(column_scores, df1.columns)

    print(f"[COMPARE] Comparison completed:")
    print(f"    Matches: {matches}")
    print(f"    Differences: {differences}")
    print(f"    Match percentage: {match_percentage:.2f}%")
    print(f"    Column scores: {column_scores}")
    print(f"    Bank statement scores: {bank_statement_scores}")

    return {
        "matches": matches,
        "differences": differences,
        "match_percentage": round(match_percentage, 2),
        "header_comparison": header_results,
        "column_scores": column_scores,
        "evaluation_score": round(match_percentage, 2),
        "date_score": bank_statement_scores.get("date_score", 0.0),
        "credit_score": bank_statement_scores.get("credit_score", 0.0),
        "debit_score": bank_statement_scores.get("debit_score", 0.0),
        "description_score": bank_statement_scores.get("description_score", 0.0),
        "balance_score": bank_statement_scores.get("balance_score", 0.0),
        "detailed_results": {
            "total_cells_compared": total_cells,
            "numerical_differences": numerical_differences,
            "string_differences": string_differences,
            "missing_values": missing_values,
            "type_mismatches": type_mismatches,
            "numerical_differences_count": len(numerical_differences),
            "string_differences_count": len(string_differences),
            "missing_values_count": len(missing_values),
            "type_mismatches_count": len(type_mismatches),
            "tolerance_used": tolerance,
            "column_wise_scores": column_scores,
            "header_analysis": header_results,
        },
    }


def compare_headers(
    df1: pd.DataFrame, df2: pd.DataFrame, similarity_threshold: float = 0.8
) -> Dict[str, Any]:
    """
    Compare headers between two dataframes.

    Args:
        df1 (pd.DataFrame): First dataframe
        df2 (pd.DataFrame): Second dataframe
        similarity_threshold (float): Threshold for fuzzy header matching (0-1)

    Returns:
        Dict containing header comparison results
    """
    print(f"[HEADER_COMPARE] Starting header comparison")

    headers1 = list(df1.columns)
    headers2 = list(df2.columns)

    print(f"[HEADER_COMPARE] DF1 headers: {headers1}")
    print(f"[HEADER_COMPARE] DF2 headers: {headers2}")

    # Exact matches
    common_headers = list(set(headers1) & set(headers2))

    # Headers only in df1
    only_in_df1 = list(set(headers1) - set(headers2))

    # Headers only in df2
    only_in_df2 = list(set(headers2) - set(headers1))

    # Check header order for common headers
    order_matches = []
    order_differences = []

    for header in common_headers:
        pos1 = headers1.index(header)
        pos2 = headers2.index(header)
        if pos1 == pos2:
            order_matches.append({"header": header, "position": pos1})
        else:
            order_differences.append(
                {"header": header, "df1_position": pos1, "df2_position": pos2}
            )

    # Fuzzy matching for similar headers
    similar_headers = []
    for h1 in only_in_df1:
        for h2 in only_in_df2:
            similarity = SequenceMatcher(None, h1.lower(), h2.lower()).ratio()
            if similarity >= similarity_threshold:
                similar_headers.append(
                    {
                        "df1_header": h1,
                        "df2_header": h2,
                        "similarity": round(similarity, 3),
                    }
                )

    # Calculate match percentage
    total_unique_headers = len(set(headers1) | set(headers2))
    header_match_percentage = (
        (len(common_headers) / total_unique_headers * 100)
        if total_unique_headers > 0
        else 0
    )

    results = {
        "total_headers_df1": len(headers1),
        "total_headers_df2": len(headers2),
        "common_headers": common_headers,
        "common_headers_count": len(common_headers),
        "only_in_df1": only_in_df1,
        "only_in_df2": only_in_df2,
        "header_match_percentage": round(header_match_percentage, 2),
        "order_matches": order_matches,
        "order_differences": order_differences,
        "similar_headers": similar_headers,
        "headers_identical": headers1 == headers2,
        "headers_same_order": len(order_differences) == 0
        and len(common_headers) == len(headers1) == len(headers2),
    }

    print(f"[HEADER_COMPARE] Results: {header_match_percentage:.1f}% header match")
    print(
        f"[HEADER_COMPARE] Common: {len(common_headers)}, Only in DF1: {len(only_in_df1)}, Only in DF2: {len(only_in_df2)}"
    )

    return results


def calculate_bank_statement_scores(
    column_scores: Dict[str, float], columns: List[str]
) -> Dict[str, float]:
    """
    Map column scores to specific bank statement field scores.

    Args:
        column_scores: Dictionary of column names to match percentages
        columns: List of available columns

    Returns:
        Dictionary with specific bank statement scores
    """

    # Define mapping patterns for common bank statement column names
    date_patterns = [
        "date",
        "transaction_date",
        "trans_date",
        "posting_date",
        "value_date",
    ]
    credit_patterns = ["credit", "deposit", "credit_amount", "deposits", "cr"]
    debit_patterns = ["debit", "withdrawal", "debit_amount", "withdrawals", "dr"]
    description_patterns = [
        "description",
        "narrative",
        "details",
        "transaction_details",
        "particulars",
        "memo",
    ]
    balance_patterns = [
        "balance",
        "running_balance",
        "available_balance",
        "closing_balance",
        "current_balance",
    ]

    def find_best_match(patterns: List[str], available_columns: List[str]) -> str:
        """Find the best matching column for given patterns."""
        available_lower = [col.lower() for col in available_columns]

        # First try exact matches
        for pattern in patterns:
            if pattern in available_lower:
                return available_columns[available_lower.index(pattern)]

        # Then try partial matches
        for pattern in patterns:
            for col in available_columns:
                if pattern in col.lower():
                    return col

        return None

    # Find best matching columns
    date_column = find_best_match(date_patterns, columns)
    credit_column = find_best_match(credit_patterns, columns)
    debit_column = find_best_match(debit_patterns, columns)
    description_column = find_best_match(description_patterns, columns)
    balance_column = find_best_match(balance_patterns, columns)

    print(f"[BANK_SCORES] Mapped columns:")
    print(f"  Date: {date_column}")
    print(f"  Credit: {credit_column}")
    print(f"  Debit: {debit_column}")
    print(f"  Description: {description_column}")
    print(f"  Balance: {balance_column}")

    # Calculate scores
    bank_scores = {
        "date_score": column_scores.get(date_column, 0.0) if date_column else 0.0,
        "credit_score": column_scores.get(credit_column, 0.0) if credit_column else 0.0,
        "debit_score": column_scores.get(debit_column, 0.0) if debit_column else 0.0,
        "description_score": (
            column_scores.get(description_column, 0.0) if description_column else 0.0
        ),
        "balance_score": (
            column_scores.get(balance_column, 0.0) if balance_column else 0.0
        ),
    }

    return bank_scores


def is_numeric_comparison(val1: Any, val2: Any) -> bool:
    """
    Check if both values can be compared as numbers.

    Returns:
        bool: True if both values are numeric, False otherwise
    """
    try:
        float(val1)
        float(val2)
        return True
    except (ValueError, TypeError):
        return False
