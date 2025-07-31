import pandas as pd
from ....utils.logger import get_logger
import numpy as np
import re

logger = get_logger(__name__)


def handle_regex_replace(operations, matrix, page_logger):
    """
    Apply regex find-and-replace operations to all cells in the matrix.

    This function iterates through each cell in the matrix and applies regex patterns
    to clean data (e.g., removing currency symbols, formatting numbers, etc.)

    Args:
        operations (list): List containing operation dictionary with 'regex_replace' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking

    Returns:
        numpy.ndarray: Modified matrix with regex replacements applied

    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_regex_replace ===")
    page_logger.info(f"operations: {operations}")

    # Performing operations
    try:
        rows_in_matrix = len(matrix)
        columns_in_matrix = len(matrix[0])
        operation_dict = operations[0]
        regex_replace_ops = operation_dict["regex_replace"]

        # Process each regex replacement operation
        for regex_replace in regex_replace_ops:
            regex = regex_replace["regex"]
            replacement = regex_replace["replacement"]
            page_logger.info(f"Replacing {regex} with {replacement}\n")

            # Apply regex to each cell in the matrix
            for r in range(rows_in_matrix):
                for c in range(columns_in_matrix):
                    val = matrix[r, c]
                    # Only process non-empty string values
                    if isinstance(val, str) and val:
                        original_val = matrix[r, c]
                        updated_val = re.sub(regex, replacement, original_val)
                        matrix[r, c] = updated_val
                        # Log changes for debugging
                        if original_val != updated_val:
                            page_logger.info(
                                f"[r={r}, c={c}] '{original_val}' → '{updated_val}' using pattern '{regex}'"
                            )

        return matrix

    except Exception as e:
        raise Exception(f"Error in handle_regex_replace: {e}")


def handle_delete_rows(operations, matrix, page_logger):
    """
    Delete specified rows from the matrix.

    Removes entire rows based on their indices. Useful for eliminating header rows,
    footer summaries, or invalid data rows.

    Args:
        operations (list): List containing operation dictionary with 'delete_rows' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking

    Returns:
        numpy.ndarray: Matrix with specified rows removed

    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_delete_rows ===")
    page_logger.info(f"operations: {operations}")

    # Performing operations
    try:
        operation_dict = operations[0]
        delete_rows_ops = operation_dict["delete_rows"]

        for delete_rows in delete_rows_ops:
            row_indices = delete_rows.get("row_indices", [])
            # Validate indices are within bounds
            valid_indices = [i for i in row_indices if 0 <= i < matrix.shape[0]]
            if valid_indices:
                page_logger.info(f"Deleting rows {valid_indices}\n")
                matrix = np.delete(matrix, valid_indices, 0)
            else:
                page_logger.warning("No valid row indices to delete")

        return matrix

    except Exception as e:
        raise Exception(f"Error in handle_delete_rows: {e}")


def handle_map_column(operations, matrix, page_logger, header):
    """
    Map column headers to specific positions in the header array.

    Updates the header row to assign proper column names to specific positions.
    This is useful for standardizing column names across different document formats.

    Args:
        operations (list): List containing operation dictionary with 'map_column' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking
        header (numpy.ndarray): 1D array representing column headers

    Returns:
        tuple: (matrix, updated_header) - Matrix unchanged, header with new mappings

    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_map_column ===")
    page_logger.info(f"operations: {operations}")

    # Performing operations
    try:
        operation_dict = operations[0]
        map_column_ops = operation_dict["map_column"]

        for map_column_op in map_column_ops:
            header_name = map_column_op["header_name"]
            col_indices = map_column_op["column_index"]
            row_range = map_column_op.get("row_range", {})
            start_row = row_range.get("start_row", 0)
            end_row = row_range.get("end_row", len(header))

            page_logger.info(
                f"Mapping {header_name} to index {col_indices} within the range of {start_row} to {end_row}\n"
            )

            # Apply header name to specified column indices
            for col_index in col_indices:
                if col_index < len(header):
                    header[col_index] = header_name
                else:
                    header = np.insert(header, col_index, header_name)

            page_logger.info(f"header after mapping: \n {header}")

        page_logger.info(f"ending state of header: \n {header}")
        return matrix, header

    except Exception as e:
        raise Exception(f"Error in handle_map_column: {e}")


def handle_merge_rows(operations, matrix, page_logger):
    """
    Merge multiple rows by concatenating their cell values.

    Combines data from source rows into a target row. Useful when data is split
    across multiple rows due to formatting issues in the source document.

    Args:
        operations (list): List containing operation dictionary with 'merge_rows' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking

    Returns:
        numpy.ndarray: Matrix with rows merged (source rows remain but target updated)


    Note: Values are concatenated with space separator. Order depends on row indices.
    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_merge_rows ===")
    page_logger.info(f"operations: {operations}")

    operation_dict = operations[0]
    merge_ops = operation_dict["merge_rows"]

    # Performing operations
    try:
        rows_in_matrix = len(matrix)
        columns_in_matrix = len(matrix[0])

        for merge_op in merge_ops:
            row_range = merge_op.get("row_range", {})
            start_row = row_range.get("start_row", 0)
            end_row = row_range.get("end_row", len(matrix))
            if end_row < 0:
                end_row = len(matrix)
            source_row_indices = merge_op.get("source_row_indices", [])
            target_row_index = merge_op.get("target_row_index")

            page_logger.info(
                f"Merging {source_row_indices} to {target_row_index} within the range of {start_row} to {end_row}\n"
            )

            # Process each source row within the specified range
            for rows in source_row_indices:
                if start_row <= rows <= end_row:
                    if not (0 <= target_row_index < matrix.shape[0]):
                        raise ValueError("Invalid target row index")

                    # Merge each column of the source and target rows
                    for c in range(columns_in_matrix):
                        page_logger.info(
                            f"merging row {rows} and {target_row_index} at column {c}"
                        )
                        page_logger.info(f"source row value: {matrix[rows, c]}")
                        page_logger.info(
                            f"target row value: {matrix[target_row_index, c]}"
                        )

                        # Concatenate values based on row order
                        if rows > target_row_index:
                            merged_val = (
                                f"{matrix[target_row_index, c]} {matrix[rows, c]}"
                            )
                        else:
                            merged_val = (
                                f"{matrix[rows, c]} {matrix[target_row_index, c]}"
                            )

                        page_logger.info(
                            f"merging row {rows} and {target_row_index} at column {c}\n Final element value: {merged_val}"
                        )
                        matrix[target_row_index, c] = merged_val

        return matrix

    except Exception as e:
        raise Exception(f"Error in handle_merge_rows: {e}")


def handle_split_cols(operations, matrix, page_logger):
    """
    Split a single column into multiple columns using regex patterns.

    Uses regex with capture groups to extract different parts of a cell value
    into separate columns. Commonly used for splitting date/time strings or
    combined transaction descriptions.

    Args:
        operations (list): List containing operation dictionary with 'split_cols' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking

    Returns:
        numpy.ndarray: Matrix with source column data split into target columns

    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_split_cols ===")
    page_logger.info(f"operations: {operations}")

    try:
        operation_dict = operations[0]
        split_cols_ops = operation_dict["split_cols"]

        for split_cols in split_cols_ops:
            row_range = split_cols.get("row_range", {})
            start_row = row_range.get("start_row", 0)
            end_row = row_range.get("end_row", len(matrix))
            if end_row < 0:
                end_row = len(matrix)
            src_idx = split_cols.get("source_col_index")
            split_logic = split_cols.get("split_logic", "")
            method = split_cols.get("method", "regex")
            num_target_cols = split_cols.get("num_target_cols")
            params = split_cols.get("parameters", [])
            data_mapping = split_cols.get("data_mapping", [])
            index_created = split_cols.get("index_created", [])

            page_logger.info(
                f"Splitting column {src_idx} using method {method} with logic '{split_logic}' "
                f"and data mapping to columns {data_mapping} for row range {start_row} to {end_row}. "
                f"Parameters: {params}"
            )

            # Compile regex pattern for efficiency
            pattern = re.compile(split_logic)

            # Process each row in the specified range
            for row_idx in range(start_row, end_row):
                cell = matrix[row_idx, src_idx]
                match = pattern.match(cell)

                if match:
                    groups = list(match.groups())
                else:
                    # Fill with empty strings if no match
                    groups = [""] * num_target_cols

                # Assign matched groups to target columns
                for i, destination_id in enumerate(index_created):
                    if i < len(groups):
                        page_logger.info(
                            f"row {row_idx} original: '{cell}' -> groups: {groups}"
                        )
                        matrix[row_idx, destination_id] = groups[i]

        page_logger.info(f"matrix post split_cols: \n {matrix}")
        return matrix

    except Exception as e:
        raise Exception(f"Error in handle_split_cols: {e}")


def handle_insert_column(operations, matrix, page_logger, header):
    """
    Insert new columns at specified positions with default values.

    Adds new columns to the matrix and updates the header accordingly.
    Useful for adding calculated fields or standardizing table structure.

    Args:
        operations (list): List containing operation dictionary with 'insert_column' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking
        header (numpy.ndarray): 1D array representing column headers

    Returns:
        tuple: (updated_matrix, updated_header) with new columns inserted


    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_insert_column ===")
    page_logger.info(f"operations: {operations}")

    # Performing operations
    try:
        operation_dict = operations[0]
        insert_column_ops = operation_dict["insert_column"]

        for insert_column in insert_column_ops:
            column_name = insert_column["name"]
            index = insert_column["position"]
            # Ensure index is within valid range
            index = min(index, matrix.shape[1])
            default_value = insert_column.get("default_value", "")

            # Handle special case for NaN values
            if default_value.lower() == "nan":
                default_value = ""

            page_logger.info(
                f"Inserting column {column_name} at index {index} using default value '{default_value}'\n"
            )

            # Create a column filled with default_value
            default_col = np.full((matrix.shape[0],), default_value, dtype=object)
            page_logger.info(f"default_col: {default_col}")

            # Insert column into matrix and header
            matrix = np.insert(matrix, index, default_col, axis=1)
            header = np.insert(header, index, column_name)
            page_logger.info(f"header after inserting column {header} at index {index}")

        return matrix, header

    except Exception as e:
        raise Exception(f"Error in handle_insert_column: {e}")


def handle_copy_item(operations, matrix, page_logger):
    """
    Copy individual cell values from one position to another.

    Copies the value from a source cell to a target cell. Useful for filling
    missing data or duplicating values across the table.

    Args:
        operations (list): List containing operation dictionary with 'copy_item' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking

    Returns:
        numpy.ndarray: Matrix with copied values


    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_copy_item ===")
    page_logger.info(f"operations: {operations}")

    # Performing operations
    try:
        operation_dict = operations[0]
        copy_item_ops = operation_dict["copy_item"]

        for copy_item in copy_item_ops:
            from_row = copy_item["from_row"]
            from_col = copy_item["from_col"]
            to_row = copy_item["to_row"]
            to_col = copy_item["to_col"]

            page_logger.info(
                f"Copying item from row {from_row} and column {from_col} to row {to_row} and column {to_col}\n"
            )
            page_logger.info(
                f"Copied {matrix[from_row, from_col]} to {matrix[to_row, to_col]}"
            )

            # Validate all indices are within bounds
            if not (
                0 <= from_row < matrix.shape[0]
                and 0 <= from_col < matrix.shape[1]
                and 0 <= to_row < matrix.shape[0]
                and 0 <= to_col < matrix.shape[1]
            ):
                raise ValueError("Copy indices out of range")

            # Perform the copy operation
            matrix[to_row, to_col] = matrix[from_row, from_col]

        return matrix

    except Exception as e:
        raise Exception(f"Error in handle_copy_item: {e}")


def handle_merge_cols(operations, matrix, page_logger):
    """
    Merge multiple columns by concatenating their values row-wise.

    Combines values from source columns into a target column for each row.
    Useful for creating combined fields like "Full Name" from separate
    first and last name columns.

    Args:
        operations (list): List containing operation dictionary with 'merge_cols' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking

    Returns:
        numpy.ndarray: Matrix with merged column values


    Note: Values are concatenated with space separator. Order based on column indices.
    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info(f"=== Starting handle_merge_cols ===")
    page_logger.info(f"operations: {operations}")

    # Performing operations
    try:
        operation_dict = operations[0]
        merge_cols_ops = operation_dict["merge_cols"]

        for merge_cols in merge_cols_ops:
            row_range = merge_cols.get("row_range", {})
            target_col_index = merge_cols.get("target_col_index")
            # Exclude target column from source list and remove duplicates
            source_col_indices = [
                i
                for i in merge_cols.get("source_col_indices", [])
                if i != target_col_index
            ]
            source_col_indices = list(set(source_col_indices))
            start_row = row_range.get("start_row", 0)
            end_row = row_range.get("end_row", len(matrix))
            if end_row < 0:
                end_row = len(matrix)

            page_logger.info(
                f"Copying from index {source_col_indices} to {target_col_index} within the range of {start_row} to {end_row}\n"
            )

        # Process each row in the specified range
        for r in range(start_row, end_row):
            for source_col_index in source_col_indices:
                page_logger.info(
                    f"merging column {source_col_index} and {target_col_index} at row {r}"
                )
                page_logger.info(f"source column value: {matrix[r, source_col_index]}")
                page_logger.info(f"target column value: {matrix[r, target_col_index]}")

                # Concatenate values based on column order
                if source_col_index < target_col_index:
                    merged_val = (
                        f"{matrix[r, source_col_index]} {matrix[r, target_col_index]}"
                    )
                else:
                    merged_val = (
                        f"{matrix[r, target_col_index]} {matrix[r, source_col_index]}"
                    )

                page_logger.info(
                    f"merging column {source_col_index} and {target_col_index} at row {r}\n Final row: {merged_val}"
                )
                matrix[r, target_col_index] = merged_val
            page_logger.info(f"row {r} after merging: {matrix[r]}")

        return matrix

    except Exception as e:
        raise Exception(f"Error in handle_merge_cols: {e}")


def handle_delete_cols(operations, matrix, page_logger):
    """
    Delete specified columns from the matrix.

    Removes entire columns based on their indices. Useful for eliminating
    unwanted or empty columns from the extracted data.

    Args:
        operations (list): List containing operation dictionary with 'delete_cols' key
        matrix (numpy.ndarray): 2D array representing the data table
        page_logger (Logger): Logger instance for operation tracking

    Returns:
        numpy.ndarray: Matrix with specified columns removed


    Note: Columns are deleted in reverse order to avoid index shifting issues.
    """
    page_logger.info(f"starting state of dataframe: \n {matrix}")
    page_logger.info("=== Starting handle_delete_cols ===")
    page_logger.info(f"operations: {operations}")

    # Performing operations
    try:
        operation_dict = operations[0]
        delete_cols_ops = operation_dict["delete_cols"]
        page_logger.info(f"delete_cols_ops: {delete_cols_ops}")

        for delete_cols in delete_cols_ops:
            row_range = delete_cols.get("row_range", {})
            column_indices = delete_cols.get("col_indices", [])
            start_row = row_range.get("start_row", 0)
            end_row = row_range.get("end_row", len(matrix))
            if end_row < 0:
                end_row = len(matrix)

            page_logger.info(
                f"Deleting column at index {column_indices} within the range of {start_row} to {end_row}\n"
            )

            # Delete columns in reverse order to avoid index shifting
            for col_index in sorted(column_indices, reverse=True):
                if col_index < matrix.shape[1]:
                    page_logger.info(f"deleting column {col_index}")
                    page_logger.info(f"column value: {matrix[0, col_index]}")
                    matrix = np.delete(matrix, col_index, 1)
                    page_logger.info(f"column {col_index} deleted")

        return matrix

    except Exception as e:
        raise Exception(f"Error in handle_delete_cols: {e}")


# Operation handler mapping - maps operation types to their handler functions
OPERATION_HANDLERS = {
    "regex_replace": handle_regex_replace,
    "delete_rows": handle_delete_rows,
    "map_column": handle_map_column,
    "merge_rows": handle_merge_rows,
    "split_cols": handle_split_cols,
    "insert_column": handle_insert_column,
    "copy_item": handle_copy_item,
    "merge_cols": handle_merge_cols,
    "delete_cols": handle_delete_cols,
}


def process_gemini_response(
    json_response, temp_path, extracted_data_path, page_logger=None
):
    """
    Main processing function that applies a sequence of operations to clean tabular data.

    This function orchestrates the entire data cleaning process by:
    1. Loading CSV data into a numpy matrix
    2. Processing each operation in sequence
    3. Saving the cleaned data back to CSV

    Args:
        json_response (dict|list): Gemini AI response containing operations to perform
        temp_path (str): Path to input CSV file with raw extracted data
        extracted_data_path (str): Path where cleaned CSV data should be saved
        page_logger (Logger, optional): Logger instance for detailed operation tracking

    Returns:
        None: Results are saved to extracted_data_path

    Raises:
        Exception: If no transactions found after processing or operation failures

    """
    logger_ = page_logger or logger
    logger_.info("=== Starting GeminiResponseHandler execution ===")

    # Load CSV data into numpy matrix
    df = pd.read_csv(temp_path)
    matrix = df.to_numpy()
    header = matrix[0]  # First row contains headers
    page_logger.info(f"matrix (2D array) obtained from dataframe: \n {matrix}")

    # Extract operations from response (handle both dict and list formats)
    operations = (
        json_response.get("operations", [])
        if isinstance(json_response, dict)
        else json_response
    )

    # Replace NaN values with empty strings for consistent processing
    matrix = np.where(
        matrix == matrix,  # checks for non-NaN (nan != nan)
        matrix,  # keep original if not NaN
        "",  # replace if NaN
    )
    page_logger.info(f"matrix after replacing np.nan with empty string: \n {matrix}")

    # Process each operation sequentially
    for op in operations:
        op_type = op.get("operation_type")
        op_details = op.get("operation", {})
        logger_.info(f"Starting operation: {op_type} with details: {op_details}")

        # Get appropriate handler for this operation type
        handler = OPERATION_HANDLERS.get(op_type)
        if handler:
            try:
                logger_.info(f"Applying operation: {op_type}")

                # Special handling for operations that modify headers
                if op_type == "map_column" or op_type == "insert_column":
                    matrix, header = handler(
                        [op_details], matrix, logger_, header=header
                    )
                else:
                    matrix = handler([op_details], matrix, logger_)

                page_logger.info(f"matrix post {op_type}: \n {matrix}")
                logger_.info(f"Completed operation: {op_type}")
                page_logger.info(f"Post operation shape of matrix: {matrix.shape}")

            except Exception as e:
                raise Exception(f"Operation {op_type} failed: {e}")

        else:
            logger_.warning(f"No handler found for operation type: {op_type}")

    # Validate final result and save to CSV
    if len(matrix) == 0:
        raise Exception("No transactions found in the dataframe")

    # Create DataFrame with proper headers if possible
    if len(header) == len(matrix[0]):
        df = pd.DataFrame(matrix, columns=header)
        df.to_csv(extracted_data_path, index=False)
    else:
        # Fallback: save without custom headers if mismatch
        df = pd.DataFrame(matrix)
        df.to_csv(extracted_data_path, index=False)

    logger_.info(f"Final matrix:\n {matrix}")
