import chardet
from django.shortcuts import render
from django.contrib import messages
import pandas as pd
from .utils.compare_csv import compare_dataframes
import traceback
from .models import Evaluation
import json
import os
from extractor.models import ExtractedDataUsingAzure
from io import StringIO
from extractor.utils.logger import get_logger

logger = get_logger(__name__)


def EvalView(request):
    if request.method == "POST":
        # Get uploaded files
        file1 = request.FILES.get("file1")
        file2 = request.FILES.get("file2")
        file2_name = file2.name

        upload_dir = "media/original_csv"
        os.makedirs(upload_dir, exist_ok=True)

        file1_path = os.path.join(upload_dir, file1.name)
        file2_path = os.path.join(upload_dir, file2.name)

        comparison = compare_files(file1_path, file2_name, request)
        return comparison

    return render(request, "eval.html")


def compare_files(file1_path, file2_name, request):

    if request.method == "POST":
        try:
            # Get uploaded files
            file1 = request.FILES.get("file1")
            file2 = request.FILES.get("file2")

            logger.info(f"[DEBUG] [EVAL]File1: {file1.name if file1 else 'None'}")
            logger.info(f"[DEBUG] [EVAL]File2: {file2.name if file2 else 'None'}")

            if not file1 or not file2:
                error_msg = "Both files are required for comparison"
                logger.info(f"[ERROR] {error_msg}")
                messages.error(request, error_msg)
                return render(request, "eval.html")

            # Configuration parameters
            index_col = None
            compare_columns = None
            tolerance = 0.0001

            logger.info(
                f"[DEBUG] [EVAL]Configuration - index_col: {index_col}, tolerance: {tolerance}"
            )

            # Read CSV files
            logger.info("[DEBUG] [EVAL]Reading CSV files...")
            try:
                file1.seek(0)
                raw_data = file1.read()
                encoding_result = chardet.detect(raw_data)
                encoding = encoding_result["encoding"] or "utf-8"

                file1_content = raw_data.decode(encoding)
                df1 = pd.read_csv(StringIO(file1_content), index_col=index_col)

                logger.info(
                    f"[DEBUG] [EVAL]File1 loaded successfully - Shape: {df1.shape}"
                )

                if df1.empty:
                    logger.warning(
                        "[WARNING] [EVAL] File1 DataFrame is empty after validation"
                    )

            except Exception as e:
                error_msg = f"Error reading file1: {str(e)}"
                logger.error(f"[ERROR] {error_msg}")
                messages.error(request, error_msg)
                return render(request, "eval.html")

            try:
                file2.seek(0)
                raw_data = file2.read()
                encoding_result = chardet.detect(raw_data)
                encoding = encoding_result["encoding"] or "utf-8"

                file2_content = raw_data.decode(encoding)
                df2 = pd.read_csv(StringIO(file2_content), index_col=index_col)

                logger.info(
                    f"[DEBUG] [EVAL]File2 loaded successfully - Shape: {df2.shape}"
                )

                if df2.empty:
                    logger.warning(
                        "[WARNING] [EVAL] File2 DataFrame is empty after validation"
                    )

            except Exception as e:
                error_msg = f"Error reading file2: {str(e)}"
                logger.error(f"[ERROR] {error_msg}")
                messages.error(request, error_msg)
                return render(request, "eval.html")

            # Get common columns if not specified
            if compare_columns is None:
                compare_columns = list(set(df1.columns) & set(df2.columns))
                logger.info(
                    f"[DEBUG] [EVAL]Auto-detected common columns: {compare_columns}"
                )
            else:
                logger.info(f"[DEBUG] [EVAL]Using specified columns: {compare_columns}")

            # Validate columns exist in both dataframes
            missing_cols_df1 = set(compare_columns) - set(df1.columns)
            missing_cols_df2 = set(compare_columns) - set(df2.columns)

            logger.info(
                f"[DEBUG] [EVAL]Missing columns check - DF1: {missing_cols_df1}, DF2: {missing_cols_df2}"
            )

            if missing_cols_df1 or missing_cols_df2:
                error_msg = f"Missing columns - DF1: {missing_cols_df1}, DF2: {missing_cols_df2}"
                logger.info(f"[ERROR] {error_msg}")
                messages.error(request, error_msg)
                return render(request, "eval.html")

            # Get common indexes
            common_indexes = df1.index.intersection(df2.index)
            logger.info(f"[DEBUG] [EVAL]Common indexes count: {len(common_indexes)}")
            logger.info(
                f"[DEBUG] [EVAL]DF1 index range: {df1.index.min()} to {df1.index.max()}"
            )
            logger.info(
                f"[DEBUG] [EVAL]DF2 index range: {df2.index.min()} to {df2.index.max()}"
            )

            if len(common_indexes) == 0:
                error_msg = "No common indexes found between the files"
                logger.info(f"[ERROR] {error_msg}")

                results = {
                    "matches": 0,
                    "differences": 0,
                    "match_percentage": 0.0,
                    "detailed_results": {
                        "error": error_msg,
                        "df1_shape": df1.shape,
                        "df2_shape": df2.shape,
                        "common_columns": compare_columns,
                        "common_indexes_count": 0,
                        "file1_name": file1.name,
                        "file2_name": file2.name,
                    },
                }

                messages.warning(request, error_msg)
                return render(
                    request,
                    "eval.html",
                    {
                        "results": results,
                        "detailed_results": results["detailed_results"],
                    },
                )

            # Filter dataframes to common indexes and columns
            logger.info(
                "[DEBUG] [EVAL]Filtering dataframes to common indexes and columns..."
            )

            try:
                df1_filtered = df1.loc[common_indexes, compare_columns]
                df2_filtered = df2.loc[common_indexes, compare_columns]

                logger.info(f"[DEBUG] [EVAL]Filtered DF1 shape: {df1_filtered.shape}")
                logger.info(f"[DEBUG] [EVAL]Filtered DF2 shape: {df2_filtered.shape}")

                logger.info(
                    f"[DEBUG] [EVAL] Validated DF1 filtered shape: {df1_filtered.shape}"
                )
                logger.info(
                    f"[DEBUG] [EVAL] Validated DF2 filtered shape: {df2_filtered.shape}"
                )
                logger.info(
                    f"[DEBUG] [EVAL] Validated DF1 columns: {list(df1_filtered.columns)}"
                )
                logger.info(
                    f"[DEBUG] [EVAL] Validated DF2 columns: {list(df2_filtered.columns)}"
                )

            except Exception as filter_error:
                error_msg = (
                    f"Error filtering DataFrames for comparison: {str(filter_error)}"
                )
                logger.error(f"[ERROR] [EVAL] {error_msg}")
                messages.error(request, error_msg)
                return render(request, "eval.html", {"error": error_msg})

            # Perform comparison
            logger.info("[DEBUG] [EVAL]Starting detailed comparison...")
            comparison_results = compare_dataframes(
                df1_filtered, df2_filtered, tolerance
            )
            logger.info("[DEBUG] [EVAL]Comparison completed successfully")
            logger.info(
                f"[DEBUG] [EVAL]Results summary - Matches: {comparison_results['matches']}, Differences: {comparison_results['differences']}, Match %: {comparison_results['match_percentage']}"
            )
            logger.info(
                f"[DEBUG] [EVAL]Bank statement scores - Date: {comparison_results['date_score']}, Credit: {comparison_results['credit_score']}, Debit: {comparison_results['debit_score']}, Description: {comparison_results['description_score']}, Balance: {comparison_results['balance_score']}"
            )

            # Add metadata
            comparison_results["detailed_results"].update(
                {
                    "df1_shape": df1.shape,
                    "df2_shape": df2.shape,
                    "common_columns": compare_columns,
                    "common_indexes_count": len(common_indexes),
                    "compared_cells": len(common_indexes) * len(compare_columns),
                    "file1_name": file1.name,
                    "file2_name": file2.name,
                    "total_cells_compared": len(common_indexes) * len(compare_columns),
                }
            )

            logger.info("[DEBUG] [EVAL]Final results prepared with metadata")

            # Add success message
            messages.success(
                request,
                f"Files compared successfully! Found {comparison_results['differences']} differences out of {comparison_results['matches'] + comparison_results['differences']} total comparisons.",
            )
            logger.info(
                f"[DEBUG] [EVAL]Comparison results: {json.dumps(comparison_results, indent=4)}"
            )
            logger.info(
                f"numerical differences: {json.dumps(comparison_results['detailed_results']['numerical_differences'], indent=4)}"
            )
            logger.info(
                f"string differences: {json.dumps(comparison_results['detailed_results']['string_differences'], indent=4)}"
            )
            logger.info(
                f"missing values: {json.dumps(comparison_results['detailed_results']['missing_values'], indent=4)}"
            )
            logger.info(
                f"type mismatches: {json.dumps(comparison_results['detailed_results']['type_mismatches'], indent=4)}"
            )

            evaluation = Evaluation(
                original_csv_path=file1_path,
                evaluation_score=comparison_results["match_percentage"],
                date_score=comparison_results["date_score"],
                credit_score=comparison_results["credit_score"],
                debit_score=comparison_results["debit_score"],
                description_score=comparison_results["description_score"],
                balance_score=comparison_results["balance_score"],
            )
            evaluation.save()
            start = file2_name.find("temp_csv_") + 9  # +9 to skip "temp_csv_"
            search_in_azure = file2_name[start:]
            logger.info(f"[DEBUG] [EVAL]File2 name: {file2_name}")
            logger.info(f"[DEBUG] [EVAL]Search in Azure: {search_in_azure}")

            if ExtractedDataUsingAzure.objects.filter(
                csv_name=search_in_azure
            ).exists():
                extractor = ExtractedDataUsingAzure.objects.filter(
                    csv_name=search_in_azure
                ).update(evaluation=evaluation.id)
                logger.info(f"[DEBUG] [EVAL]Extractor: {extractor}")
            else:
                logger.info(f"[DEBUG] [EVAL]No extractor found")

            return render(
                request,
                "eval.html",
                {
                    "results": comparison_results,
                    "detailed_results": comparison_results["detailed_results"],
                    "bank_scores": {
                        "date_score": comparison_results["date_score"],
                        "credit_score": comparison_results["credit_score"],
                        "debit_score": comparison_results["debit_score"],
                        "description_score": comparison_results["description_score"],
                        "balance_score": comparison_results["balance_score"],
                    },
                    "header_comparison": comparison_results["header_comparison"],
                },
            )

        except Exception as e:
            error_msg = f"Unexpected error during comparison: {str(e)}"
            logger.info(f"[CRITICAL ERROR] {error_msg}")
            logger.info(f"[DEBUG] [EVAL]Exception type: {type(e).__name__}")
            logger.info(f"[DEBUG] [EVAL]Traceback:\n{traceback.format_exc()}")

            messages.error(request, error_msg)

            error_results = {
                "matches": 0,
                "differences": 0,
                "match_percentage": 0.0,
                "detailed_results": {
                    "error": error_msg,
                    "error_type": type(e).__name__,
                    "file1_name": (
                        file1.name if "file1" in locals() and file1 else "Unknown"
                    ),
                    "file2_name": (
                        file2.name if "file2" in locals() and file2 else "Unknown"
                    ),
                },
            }

            return render(
                request,
                "eval.html",
                {
                    "results": error_results,
                    "detailed_results": error_results["detailed_results"],
                },
            )
