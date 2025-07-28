import json
import re
import pandas as pd
from ..logging_config import get_logger

logger = get_logger(__name__)


def parse_ocr_analysis(data):  # normalizing the data from azure

    if data is None:
        return []

    if not isinstance(data, (list, dict)):
        try:
            if isinstance(data, str):
                data = json.loads(data)
            else:
                return []
        except json.JSONDecodeError as e:
            return []

    # Convert dict to list if single page
    if isinstance(data, dict):
        data = [data]

    if not data:  # Empty list
        return []

    def reformat_fields(fields):
        if not fields or not isinstance(fields, dict):
            return {}
        return {key: value.get("value", None) for key, value in fields.items()}

    def reformat_key_value_data(key_value_pairs):
        if not key_value_pairs or not isinstance(key_value_pairs, (list, dict)):
            return {}

        reformatted_data = {}
        if isinstance(key_value_pairs, dict):
            key_value_pairs = [key_value_pairs]
        # print(f"[DEBUG] Key value pairs: {key_value_pairs}")

        for item in key_value_pairs:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            value = item.get("value")

            if key and value:
                reformatted_data[key] = value.get("content", None)
            # print(f"[DEBUG] Reformatted data: {reformatted_data}")

        return reformatted_data

    def parse_items(items):
        if not items or not isinstance(items, list):
            return []
        parsed_items = []
        for item in items:
            if isinstance(item, dict):
                parsed_items.append(item)
            else:
                logger.warning(f"Unexpected item format: {item}")
        return parsed_items

    def format_and_fill_table_data(tables):
        if not tables or not isinstance(tables, list):
            return []

        def is_date(value):
            if not isinstance(value, str):
                return False
            date_pattern = r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}"
            return bool(re.match(date_pattern, value))

        formatted_output = []
        for i, table in enumerate(tables, start=1):
            if not isinstance(table, dict):
                logger.warning(f"Invalid table format at index {i}")
                continue

            columns = table.get("columns", [])
            rows = table.get("rows", [])

            if not columns or not rows:
                logger.warning(f"Empty columns or rows in table {i}")
                continue

            table_data = {"Table_Number": f"Table {i}", "Columns": columns, "Rows": []}

            date_column = None
            previous_date = None

            for row in rows:
                if not isinstance(row, dict):
                    continue

                formatted_row = {}
                for col in columns:
                    value = row.get(col, "")
                    if date_column is None and value and is_date(value):
                        date_column = col

                    if col == date_column:
                        if not value and previous_date:
                            formatted_row[col] = previous_date
                        else:
                            formatted_row[col] = value
                            if value:
                                previous_date = value
                    else:
                        formatted_row[col] = value

                if any(
                    str(v).strip() for v in formatted_row.values()
                ):  # Only add non-empty rows
                    table_data["Rows"].append(formatted_row)

            if table_data["Rows"]:  # Only add tables with rows
                formatted_output.append(table_data)

        return formatted_output

    try:
        parsed_pages = []
        data.sort(key=lambda x: x.get("page_number", 0) if isinstance(x, dict) else 0)

        for page in data:
            if not isinstance(page, dict):
                continue

            page_number = page.get("page_number", "Unknown")
            file_path = page.get("file_path", "Unknown")

            page_data = {
                "page_number": page_number,
                "file_path": file_path,
                "fields": {},
                "key_value_pairs": {},
                "tables": [],
            }

            analysis = page.get("analysis", {})

            fields = analysis.get("fields", {})
            key_value_pairs = analysis.get("key_value_pairs", {})
            tables = analysis.get("tables", [])
            page_data["key_value_pairs"] = reformat_key_value_data(key_value_pairs)
            page_data["fields"] = reformat_fields(fields)
            page_data["tables"] = format_and_fill_table_data(tables)

            if (
                page_data["fields"]
                or page_data["key_value_pairs"]
                or page_data["tables"]
            ):
                parsed_pages.append(page_data["tables"])

        return parsed_pages

    except Exception as e:
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return []


def extract_table_to_dataframe(formatted_data, initial_column_mapping=None):
    """
    Extracts table data from the Azure Document Intelligence result format
    and consolidates them into a single pandas DataFrame.

    :param formatted_data: The list of dictionaries containing page and table data.
    :return: A pandas DataFrame with the extracted table data.
    """
    all_data_rows = []
    logger.info(f"Initial column mapping: {initial_column_mapping}")

    # Initialize column_mapping outside the loop to preserve the best mapping found
    best_column_mapping = initial_column_mapping or {}

    try:
        for page in formatted_data:
            try:
                for table in page:
                    try:
                        cells = table.get("cells", [])
                        logger.info(f"Cells: {cells}")
                        rows = table.get("Rows", [])
                        if len(rows) < 2:
                            # Skip tables without a header and at least one data row
                            logger.info(
                                "Skipping table - insufficient rows (need header + data)"
                            )
                            continue

                        # Try to find column mapping for this specific table
                        table_column_mapping = {}
                        for row in rows:
                            filtered_list = [
                                item for item in row.values() if item.strip()
                            ]
                            if len(filtered_list) > 3:
                                logger.info(f"Row: {filtered_list}")
                                # Check if any value in the row contains the keywords
                                row_values_lower = [
                                    str(value).lower() for value in row.values()
                                ]
                                if (
                                    any("date" in value for value in row_values_lower)
                                    or any(
                                        "balance" in value for value in row_values_lower
                                    )
                                    or any(
                                        "description" in value
                                        for value in row_values_lower
                                    )
                                ):
                                    logger.info(
                                        f"Row has date, balance, or description: {row}"
                                    )
                                    table_column_mapping = {
                                        col_key: col_value
                                        for col_key, col_value in row.items()
                                    }
                                    print(
                                        f"Column Mapping updated: {table_column_mapping}"
                                    )
                                    if (
                                        table_column_mapping != best_column_mapping
                                        and len(row) > len(best_column_mapping.values())
                                    ):
                                        best_column_mapping = table_column_mapping
                                break
                            elif not table_column_mapping and not best_column_mapping:
                                table_column_mapping = {
                                    col_key: col_value
                                    for col_key, col_value in max(rows, key=len).items()
                                }
                                if table_column_mapping != best_column_mapping and len(
                                    row
                                ) > len(best_column_mapping.values()):
                                    best_column_mapping = table_column_mapping

                        logger.info(f"Table Column Mapping: {table_column_mapping}")
                        logger.info(
                            f"Best Column Mapping so far: {best_column_mapping}"
                        )
                        all_data_rows.extend(rows[:-1])

                    except Exception as table_error:
                        logger.error(
                            f"[ERROR] Error processing individual table: {table_error}"
                        )
                        continue

            except Exception as page_error:
                logger.error(f"[ERROR] Error processing page: {page_error}")
                continue

    except Exception as data_error:
        logger.error(f"[ERROR] Error processing formatted_data: {data_error}")

    if not all_data_rows:
        logger.warning("[WARNING] No data rows extracted, returning empty DataFrame")
        return pd.DataFrame(), best_column_mapping

    try:
        logger.info(f"[DEBUG] Creating DataFrame from {len(all_data_rows)} rows")
        df = pd.DataFrame(all_data_rows)

        if df.empty:
            logger.warning("[WARNING] DataFrame is empty after validation")
            return df, best_column_mapping

        # Rename columns from generic names like 'Column_0' to descriptive names from the header
        if best_column_mapping:
            try:
                # Clean encoding issues in column_mapping
                best_column_mapping = {
                    k: v.replace("?", "").replace("\n", " ").strip()
                    for k, v in best_column_mapping.items()
                }
                logger.info(f"[DEBUG] Best Column Mapping: {best_column_mapping}")

                # Ensure mapping values are strings
                best_column_mapping = {
                    k: str(v) for k, v in best_column_mapping.items()
                }
                logger.info(
                    f"[DEBUG] Column mapping after string conversion: {best_column_mapping}"
                )

                df.rename(columns=best_column_mapping, inplace=True)
                logger.info(
                    f"[DEBUG] DataFrame columns after renaming: {list(df.columns)}"
                )

                # Ensure DataFrame columns follow the order from the header
                final_columns = list(best_column_mapping.values())
                # Filter out any columns not in the original header mapping - SAFETY CHECK
                existing_columns = [col for col in final_columns if col in df.columns]
                if existing_columns:
                    df = df[existing_columns]
                    logger.info(
                        f"[DEBUG] DataFrame columns after reordering: {list(df.columns)}"
                    )
                else:
                    logger.warning("[WARNING] No existing columns found after mapping")

            except Exception as mapping_error:
                logger.error(f"[ERROR] Error applying column mapping: {mapping_error}")
                # Continue with original DataFrame without mapping

        logger.info(f"[DEBUG] Final DataFrame:\n{df}")
        logger.info(f"[DEBUG] Final Column Mapping: {best_column_mapping}")
        logger.info(f"[DEBUG] Final DataFrame shape: {df.shape}")
        logger.info(f"[DEBUG] Final DataFrame dtypes:\n{df.dtypes}")

        return df, best_column_mapping

    except Exception as df_creation_error:
        logger.error(f"[ERROR] Failed to create DataFrame: {df_creation_error}")
        return pd.DataFrame(), best_column_mapping
