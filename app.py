from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    Response,
)
import os
import tempfile
import pandas as pd
import numpy as np
from collections import defaultdict
from itertools import combinations
import os
from werkzeug.utils import secure_filename
import logging
import json
import time
import math
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = "bundling_recommendation_key"
app.config["ALLOWED_EXTENSIONS"] = {"csv", "xlsx", "xls"}
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), "flask_session")
app.config["SESSION_FILE_THRESHOLD"] = 500

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", tempfile.gettempdir())
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

if not os.path.exists(app.config["SESSION_FILE_DIR"]):
    os.makedirs(app.config["SESSION_FILE_DIR"])

try:
    from flask_session import Session

    Session(app)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileHandler:
    """Class untuk menangani operasi file"""

    @staticmethod
    def allowed_file(filename):
        """Cek apakah ekstensi file diizinkan"""
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
        )

    @staticmethod
    def read_file(filepath):
        """Baca file CSV atau Excel"""
        try:
            if filepath.endswith(".csv"):
                return pd.read_csv(filepath)
            else:
                return pd.read_excel(filepath)
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {str(e)}")
            return None

    @staticmethod
    def save_file(file, upload_folder, filename=None):
        """Simpan file yang diupload"""
        try:
            if filename is None:
                filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            return filepath, filename
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            return None, None


class DateFilter:
    """Class untuk filtering data berdasarkan tanggal"""

    @staticmethod
    def extract_date_from_datetime(datetime_string):
        """Ekstrak tanggal dari string datetime"""
        if pd.isna(datetime_string) or datetime_string is None:
            return None

        datetime_str = str(datetime_string).strip()
        if datetime_str.lower() == "order":
            return None
        pattern1 = r"^(\d{1,2}/\d{1,2}/\d{4})"
        match1 = re.match(pattern1, datetime_str)
        if match1:
            return match1.group(1)

        pattern2 = r"^(\d{4}-\d{1,2}-\d{1,2})"
        match2 = re.match(pattern2, datetime_str)
        if match2:
            return match2.group(1)

        pattern3 = r"^(\d{1,2}-\d{1,2}-\d{4})"
        match3 = re.match(pattern3, datetime_str)
        if match3:
            return match3.group(1)

        if not any(char.isdigit() for char in datetime_str):
            return None

        return datetime_str.split(" ")[0] if " " in datetime_str else datetime_str

    def get_unique_dates_from_column(self, df, column_name):
        """Mendapatkan tanggal unik dari kolom datetime setelah transformasi"""
        if column_name not in df.columns:
            return []

        dates = df[column_name].apply(self.extract_date_from_datetime)
        valid_dates = dates.dropna()
        valid_dates = valid_dates[valid_dates.str.len() > 5]
        unique_dates = valid_dates.unique().tolist()

        try:

            def parse_date(date_str):
                try:
                    if "/" in date_str:
                        return datetime.strptime(date_str, "%d/%m/%Y")
                    elif "-" in date_str and date_str.count("-") == 2:
                        parts = date_str.split("-")
                        if len(parts[0]) == 4:
                            return datetime.strptime(date_str, "%Y-%m-%d")
                        else:
                            return datetime.strptime(date_str, "%d-%m-%Y")
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    return datetime(1900, 1, 1)

            unique_dates.sort(key=parse_date)
        except:
            unique_dates.sort()

        return unique_dates

    def filter_dataframe_by_date_range(self, df, date_column, start_date, end_date):
        """Filter DataFrame berdasarkan rentang tanggal"""
        if date_column not in df.columns:
            return df, "Kolom tanggal tidak ditemukan"

        try:
            df_copy = df.copy()
            df_copy["extracted_date"] = df_copy[date_column].apply(
                self.extract_date_from_datetime
            )

            def parse_date_string(date_str):
                try:
                    if "/" in date_str:
                        return datetime.strptime(date_str, "%d/%m/%Y")
                    elif "-" in date_str:
                        parts = date_str.split("-")
                        if len(parts[0]) == 4:
                            return datetime.strptime(date_str, "%Y-%m-%d")
                        else:
                            return datetime.strptime(date_str, "%d-%m-%Y")
                    return None
                except:
                    return None

            start_dt = parse_date_string(start_date)
            end_dt = parse_date_string(end_date)

            if start_dt is None or end_dt is None:
                return df, "Format tanggal tidak valid"

            def date_in_range(date_str):
                if pd.isna(date_str) or date_str is None:
                    return False
                date_obj = parse_date_string(date_str)
                if date_obj is None:
                    return False
                return start_dt <= date_obj <= end_dt

            mask = df_copy["extracted_date"].apply(date_in_range)
            filtered_df = df[mask].copy()

            return filtered_df, None

        except Exception as e:
            return df, f"Error saat filtering: {str(e)}"


class ProductAnalyzer:
    def __init__(self):
        self.transaction_product_col = "Seller SKU"
        self.logger = logger

    def find_product_column(self, df, target_names):
        """Mencari nama kolom produk yang mirip dengan target (case insensitive)"""
        df_columns = [col.strip().lower() for col in df.columns]

        for target in target_names:
            target_lower = target.lower()
            for i, col in enumerate(df_columns):
                if target_lower in col or col in target_lower:
                    return df.columns[i]
        return None

    def analyze_product_sales(self, transaction_df, product_df):
        try:
            self.logger.info("=== STARTING PRODUCT ANALYSIS ===")
            self.logger.info(f"Product file shape: {product_df.shape}")
            self.logger.info(f"Product file columns: {product_df.columns.tolist()}")

            product_sku_col = None
            product_code_col = None

            for col in product_df.columns:
                col_lower = str(col).lower()
                if "sku" in col_lower and "penjual" in col_lower:
                    product_sku_col = col
                elif "kode" in col_lower and "produk" in col_lower:
                    product_code_col = col

            if not product_sku_col:
                product_sku_col = product_df.columns[0]
            if not product_code_col:
                product_code_col = (
                    product_df.columns[1]
                    if len(product_df.columns) > 1
                    else product_df.columns[0]
                )

            self.logger.info(
                f"Using columns: SKU='{product_sku_col}', Code='{product_code_col}'"
            )
            master_products = set()
            product_mapping = {}

            processed_count = 0
            skipped_count = 0

            for idx, row in product_df.iterrows():
                try:
                    product_sku = row[product_sku_col]
                    product_code = (
                        row[product_code_col]
                        if product_code_col != product_sku_col
                        else f"P{idx+1}"
                    )

                    if pd.isna(product_sku):
                        skipped_count += 1
                        continue

                    sku_clean = str(product_sku).strip()
                    code_clean = (
                        str(product_code).strip()
                        if pd.notna(product_code)
                        else f"P{idx+1}"
                    )

                    if not sku_clean or sku_clean.lower() in [
                        "nan",
                        "none",
                        "",
                        "null",
                    ]:
                        skipped_count += 1
                        continue

                    master_products.add(sku_clean)
                    product_mapping[sku_clean] = {
                        "name": sku_clean,
                        "code": code_clean,
                    }
                    processed_count += 1

                except Exception as e:
                    self.logger.warning(f"Error processing row {idx}: {e}")
                    skipped_count += 1
                    continue

            self.logger.info(
                f"Master data processed: {processed_count}, skipped: {skipped_count}"
            )

            if len(master_products) == 0:
                return (
                    None,
                    "Tidak ada data produk yang valid ditemukan dalam file master data.",
                )
            transaction_products = set()
            transaction_counts = defaultdict(int)

            for idx, row in transaction_df.iterrows():
                try:
                    product_code = row[self.transaction_product_col]
                    if pd.isna(product_code):
                        continue
                    code_clean = str(product_code).strip()

                    if not code_clean or code_clean.lower() in [
                        "nan",
                        "none",
                        "",
                        "null",
                    ]:
                        continue

                    transaction_products.add(code_clean)
                    transaction_counts[code_clean] += 1

                except Exception as e:
                    self.logger.warning(f"Error processing transaction row {idx}: {e}")
                    continue

            sold_products_exact = master_products.intersection(transaction_products)
            sold_products = sold_products_exact

            if len(sold_products) == 0:
                master_lower = {p.lower(): p for p in master_products}
                transaction_lower = {p.lower() for p in transaction_products}
                sold_lower = set(master_lower.keys()).intersection(transaction_lower)
                sold_products = {master_lower[p] for p in sold_lower}

            unsold_products = master_products - sold_products
            sold_stats = []
            for product in sold_products:
                count = transaction_counts.get(product, 0)
                sold_stats.append((product, count))

            sold_stats.sort(key=lambda x: x[1], reverse=True)
            total_products = len(master_products)
            sold_count = len(sold_products)
            unsold_count = len(unsold_products)

            result = {
                "total_products": total_products,
                "sold_products_count": sold_count,
                "unsold_products_count": unsold_count,
                "sold_percentage": (
                    (sold_count / total_products * 100) if total_products > 0 else 0
                ),
                "unsold_percentage": (
                    (unsold_count / total_products * 100) if total_products > 0 else 0
                ),
                "sold_products": [
                    {
                        "code": product_mapping[code].get("code", code),
                        "name": product_mapping[code].get("name", code),
                        "sales_count": count,
                    }
                    for code, count in sold_stats
                ],
                "unsold_products": [
                    {
                        "code": product_mapping[code].get("code", code),
                        "name": product_mapping[code].get("name", code),
                        "sales_count": 0,
                    }
                    for code in sorted(unsold_products)
                ],
                "top_selling": sold_stats[:10],
                "product_mapping": {k: v["name"] for k, v in product_mapping.items()},
                "transaction_product_col": self.transaction_product_col,
                "product_product_col": product_sku_col,
                "product_name_col": product_sku_col,
            }

            return result, None

        except Exception as e:
            import traceback

            error_msg = f"Error in product analysis: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            return None, error_msg


class DataProcessor:
    def __init__(self):
        self.logger = logger

    def prepare_transactions(
        self,
        df,
        order_col="Order ID",
        product_col="Seller SKU",
        sku_id_col="SKU ID",
        min_support_count=2,
    ):
        try:
            if order_col not in df.columns or product_col not in df.columns:
                available_cols = df.columns.tolist()
                self.logger.error(
                    f"Kolom yang dibutuhkan tidak ditemukan. Kolom yang tersedia: {available_cols}"
                )
                return (
                    None,
                    f"Kolom {order_col} atau {product_col} tidak ditemukan dalam data",
                    0,
                    0,
                    0,
                    {},
                )

            using_sku_id = sku_id_col in df.columns
            if using_sku_id:
                self.logger.info(
                    f"Menggunakan kombinasi {product_col} dan {sku_id_col} untuk identifikasi produk unik"
                )

            cols_to_use = [order_col, product_col]
            if using_sku_id:
                cols_to_use.append(sku_id_col)

            df_subset = df[cols_to_use].copy()
            df_clean = df_subset.dropna(subset=cols_to_use)

            df_clean[order_col] = df_clean[order_col].astype(str)
            df_clean[product_col] = df_clean[product_col].astype(str)
            if using_sku_id:
                df_clean[sku_id_col] = df_clean[sku_id_col].astype(str)

            df_clean[product_col] = df_clean[product_col].str.strip()

            if len(df_clean) > 2:
                df_work = df_clean.iloc[2:].copy()
                self.logger.info(
                    f"Data setelah skip 2 baris pertama: {len(df_work)} rows"
                )
            else:
                df_work = df_clean.copy()

            unique_orders = df_work[order_col].unique()
            order_mapping = {
                order_id: f"T{i+1}" for i, order_id in enumerate(unique_orders)
            }
            df_work["TID"] = df_work[order_col].map(order_mapping)
            product_counts = df_work[product_col].value_counts().to_dict()
            self.logger.info(f"Total unique products: {len(product_counts)}")

            filtered_products = {
                product: count
                for product, count in product_counts.items()
                if count >= min_support_count
            }

            self.logger.info(
                f"Filtering products with support_count >= {min_support_count}:"
            )
            self.logger.info(f"Original products: {len(product_counts)}")
            self.logger.info(f"Filtered products: {len(filtered_products)}")

            transactions_by_order = defaultdict(list)

            for _, row in df_work.iterrows():
                order_id = row["TID"]
                product = row[product_col]

                if (
                    product in filtered_products
                    and product not in transactions_by_order[order_id]
                ):
                    transactions_by_order[order_id].append(product)

            transactions = list(transactions_by_order.values())

            multi_product_transactions = [t for t in transactions if len(t) >= 2]
            single_product_count = len(transactions) - len(multi_product_transactions)

            final_transactions = transactions
            total_before = len(unique_orders)
            total_combined = len(final_transactions)

            self.logger.info(f"Total transactions: {len(final_transactions)}")
            self.logger.info(
                f"Multi-product transactions: {len(multi_product_transactions)}"
            )
            self.logger.info(f"Single-product transactions: {single_product_count}")

            return (
                final_transactions,
                None,
                single_product_count,
                total_before,
                total_combined,
                filtered_products,
            )

        except Exception as e:
            import traceback

            self.logger.error(f"Error dalam mempersiapkan transaksi: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None, f"Error: {str(e)}", 0, 0, 0, {}

    def prepare_transactions_with_date_filter(
        self,
        df,
        order_col="Order ID",
        product_col="Seller SKU",
        sku_id_col="SKU ID",
        date_col=None,
        start_date=None,
        end_date=None,
        min_support_count=2,
    ):
        """Mempersiapkan data transaksi dengan filtering tanggal"""
        try:
            # Filter berdasarkan tanggal jika parameter disediakan
            if date_col and start_date and end_date:
                self.logger.info(
                    f"Filtering data berdasarkan kolom {date_col} dari {start_date} hingga {end_date}"
                )
                date_filter = DateFilter()
                df, error = date_filter.filter_dataframe_by_date_range(
                    df, date_col, start_date, end_date
                )
                if error:
                    return None, error, 0, 0, 0, {}

                if len(df) == 0:
                    return (
                        None,
                        "Tidak ada data dalam rentang tanggal yang dipilih",
                        0,
                        0,
                        0,
                        {},
                    )

            # Lanjutkan dengan proses normal prepare_transactions
            return self.prepare_transactions(
                df, order_col, product_col, sku_id_col, min_support_count
            )

        except Exception as e:
            import traceback

            self.logger.error(
                f"Error dalam mempersiapkan transaksi dengan filter tanggal: {str(e)}"
            )
            self.logger.error(traceback.format_exc())
            return None, f"Error: {str(e)}", 0, 0, 0, {}


class EclatAlgorithm:
    """Class untuk implementasi algoritma ECLAT"""

    def __init__(self):
        self.logger = logger

    def create_tidlist_1itemset(self, transactions, filtered_products):
        """Buat TID-LIST untuk 1-itemset"""
        tidlist_1 = defaultdict(list)

        for tid, transaction in enumerate(transactions):
            tid_str = f"T{tid+1}"
            for product in set(transaction):
                # Hanya proses produk yang sudah difilter
                if product in filtered_products:
                    if tid_str not in tidlist_1[product]:
                        tidlist_1[product].append(tid_str)

        return dict(tidlist_1)

    def create_tidlist_2itemset(self, tidlist_1):
        """Buat TID-LIST untuk 2-itemset dari 1-itemset"""
        tidlist_2 = {}
        items = list(tidlist_1.keys())

        self.logger.info(f"Creating 2-itemset from {len(items)} items...")

        combo_count = 0
        start_time = time.time()

        # Generate semua kombinasi 2-itemset dari 1-itemset
        for combo in combinations(items, 2):
            combo_count += 1
            if combo_count % 500 == 0:
                elapsed = time.time() - start_time
                rate = combo_count / elapsed if elapsed > 0 else 0
                self.logger.info(
                    f"Processed {combo_count:,} combinations... ({elapsed:.1f}s, {rate:.0f}/sec)"
                )

            itemset = tuple(sorted(combo))

            # Hitung intersection dari TID lists
            tid_sets = [set(tidlist_1[item]) for item in itemset]
            tid_intersection = list(set.intersection(*tid_sets))

            if tid_intersection:  # Hanya simpan jika ada intersection
                tidlist_2[itemset] = tid_intersection

        elapsed = time.time() - start_time
        self.logger.info(
            f"Total 2-itemset combinations checked: {combo_count:,} ({elapsed:.1f}s)"
        )
        return tidlist_2

    def create_tidlist_kitemset_from_previous(self, tidlist_prev, tidlist_1, k):
        """Buat k-itemset dari (k-1)-itemset yang sudah ada"""
        tidlist_k = {}
        prev_itemsets = list(tidlist_prev.keys())

        self.logger.info(
            f"Creating {k}-itemset from {len(prev_itemsets)} {k-1}-itemsets..."
        )

        if not prev_itemsets:
            self.logger.info(
                f"No {k-1}-itemsets found, skipping {k}-itemset generation"
            )
            return tidlist_k

        combo_count = 0
        start_time = time.time()

        # Generate candidate k-itemset dari (k-1)-itemset
        for i, itemset1 in enumerate(prev_itemsets):
            for j, itemset2 in enumerate(prev_itemsets[i + 1 :], i + 1):
                combo_count += 1

                if combo_count % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = combo_count / elapsed if elapsed > 0 else 0
                    self.logger.info(
                        f"Processed {combo_count:,} combinations... ({elapsed:.1f}s, {rate:.0f}/sec)"
                    )

                # Check apakah kedua itemset bisa digabung
                set1 = set(itemset1)
                set2 = set(itemset2)

                # Untuk itemset bisa digabung, harus berbeda tepat 1 item
                diff = set1.symmetric_difference(set2)

                if len(diff) == 2:  # Berbeda tepat 1 item di masing-masing itemset
                    # Gabungkan menjadi k-itemset
                    new_itemset = tuple(sorted(set1.union(set2)))

                    if len(new_itemset) == k and new_itemset not in tidlist_k:
                        # Hitung intersection dari TID lists menggunakan 1-itemset
                        tid_sets = [set(tidlist_1[item]) for item in new_itemset]
                        tid_intersection = list(set.intersection(*tid_sets))

                        if tid_intersection:  # Hanya simpan jika ada intersection
                            tidlist_k[new_itemset] = tid_intersection

        elapsed = time.time() - start_time
        self.logger.info(
            f"Total {k}-itemset combinations checked: {combo_count:,} ({elapsed:.1f}s)"
        )
        return tidlist_k

    def run_eclat(self, transactions, filtered_products, min_support=0.01):
        """Implementasi algoritma ECLAT yang diperbaiki"""
        total_transactions = len(transactions)
        min_support_count = min_support * total_transactions

        self.logger.info(f"Starting ECLAT with {total_transactions} transactions")
        self.logger.info(
            f"Min support: {min_support}, Min support count: {min_support_count}"
        )

        # LANGKAH 1: Buat TID-LIST untuk 1-itemset
        self.logger.info("=== Creating 1-itemset TID-LIST ===")
        tidlist_1 = self.create_tidlist_1itemset(transactions, filtered_products)

        # Filter 1-itemset berdasarkan min_support
        filtered_tidlist_1 = {}
        for itemset, tid_list in tidlist_1.items():
            if len(tid_list) >= min_support_count:
                filtered_tidlist_1[itemset] = tid_list

        self.logger.info(
            f"Found {len(tidlist_1)} initial 1-itemsets, {len(filtered_tidlist_1)} after support filtering"
        )

        # LANGKAH 2: Buat TID-LIST untuk 2-itemset
        self.logger.info("=== Creating 2-itemset TID-LIST ===")
        start_time = time.time()
        tidlist_2 = self.create_tidlist_2itemset(filtered_tidlist_1)

        # Filter 2-itemset berdasarkan min_support
        filtered_tidlist_2 = {}
        for itemset, tid_list in tidlist_2.items():
            if len(tid_list) >= min_support_count:
                filtered_tidlist_2[itemset] = tid_list

        elapsed = time.time() - start_time
        self.logger.info(
            f"Found {len(tidlist_2)} initial 2-itemsets, {len(filtered_tidlist_2)} after support filtering in {elapsed:.1f}s"
        )

        # LANGKAH 3: Level-wise generation untuk k >= 3
        all_tidlists = {
            "tidlist_1": filtered_tidlist_1,
            "tidlist_2": filtered_tidlist_2,
        }

        k = 3
        tidlist_prev = filtered_tidlist_2

        while len(tidlist_prev) > 0 and k <= 10:  # Maksimal sampai 10-itemset
            self.logger.info(f"=== Creating {k}-itemset TID-LIST ===")
            start_time = time.time()
            tidlist_k = self.create_tidlist_kitemset_from_previous(
                tidlist_prev, filtered_tidlist_1, k
            )

            # Filter k-itemset berdasarkan min_support
            filtered_tidlist_k = {}
            for itemset, tid_list in tidlist_k.items():
                if len(tid_list) >= min_support_count:
                    filtered_tidlist_k[itemset] = tid_list

            elapsed = time.time() - start_time
            self.logger.info(
                f"Found {len(tidlist_k)} initial {k}-itemsets, {len(filtered_tidlist_k)} after support filtering in {elapsed:.1f}s"
            )

            if len(filtered_tidlist_k) == 0:
                self.logger.info(
                    f"No more {k}-itemsets found after support filtering. Stopping generation."
                )
                break

            all_tidlists[f"tidlist_{k}"] = filtered_tidlist_k
            tidlist_prev = filtered_tidlist_k
            k += 1

        self.logger.info(f"Itemset generation completed up to {k-1}-itemset")

        return all_tidlists, k - 1


class RuleGenerator:
    """Class untuk generate association rules dengan deduplikasi"""

    def __init__(self):
        self.logger = logger

    def calculate_confidence_and_lift(self, all_tidlists, total_transactions):
        """Menghitung confidence dan lift untuk setiap association rule"""
        self.logger.info("Calculating confidence and lift for association rules...")

        # Gabungkan semua tidlists
        all_itemsets = {}
        max_k = 0
        for key, tidlist in all_tidlists.items():
            if key.startswith("tidlist_"):
                k = int(key.split("_")[1])
                max_k = max(max_k, k)
                all_itemsets.update(tidlist)

        self.logger.info(f"Processing itemsets from 1 to {max_k}-itemset")

        association_rules = []

        # Untuk setiap itemset dengan size >= 2, buat association rules
        for itemset, tid_list in all_itemsets.items():
            if isinstance(itemset, tuple) and len(itemset) >= 2:
                itemset_support_count = len(tid_list)
                itemset_support = itemset_support_count / total_transactions
                itemset_size = len(itemset)

                # Buat semua kemungkinan rules A -> B
                for i in range(1, len(itemset)):
                    for antecedent_items in combinations(itemset, i):
                        consequent_items = tuple(
                            item for item in itemset if item not in antecedent_items
                        )

                        # Cari support untuk antecedent
                        if len(antecedent_items) == 1:
                            antecedent_key = antecedent_items[0]
                        else:
                            antecedent_key = tuple(sorted(antecedent_items))

                        if antecedent_key in all_itemsets:
                            antecedent_support_count = len(all_itemsets[antecedent_key])
                            antecedent_support = (
                                antecedent_support_count / total_transactions
                            )

                            # Cari support untuk consequent
                            if len(consequent_items) == 1:
                                consequent_key = consequent_items[0]
                            else:
                                consequent_key = tuple(sorted(consequent_items))

                            if consequent_key in all_itemsets:
                                consequent_support_count = len(
                                    all_itemsets[consequent_key]
                                )
                                consequent_support = (
                                    consequent_support_count / total_transactions
                                )

                                # Hitung confidence: support(A∪B) / support(A)
                                confidence = (
                                    itemset_support / antecedent_support
                                    if antecedent_support > 0
                                    else 0
                                )

                                # Hitung lift: support(A∪B) / (support(A) × support(B))
                                expected_support = (
                                    antecedent_support * consequent_support
                                )
                                lift = (
                                    itemset_support / expected_support
                                    if expected_support > 0
                                    else 0
                                )

                                # Skip rules dengan lift yang tidak masuk akal (terlalu tinggi)
                                if lift > 100:
                                    continue

                                # Format antecedent dan consequent
                                if isinstance(antecedent_key, tuple):
                                    antecedent_str = " + ".join(antecedent_key)
                                else:
                                    antecedent_str = str(antecedent_key)

                                if isinstance(consequent_key, tuple):
                                    consequent_str = " + ".join(consequent_key)
                                else:
                                    consequent_str = str(consequent_key)

                                # TAMBAHAN: Buat itemset identifier untuk deduplikasi
                                full_itemset = sorted(
                                    list(antecedent_items) + list(consequent_items)
                                )
                                itemset_id = tuple(full_itemset)

                                association_rules.append(
                                    {
                                        "Itemset_Size": itemset_size,
                                        "Antecedent": antecedent_str,
                                        "Consequent": consequent_str,
                                        "Rule": f"{antecedent_str} -> {consequent_str}",
                                        "Antecedent_Support_Count": antecedent_support_count,
                                        "Consequent_Support_Count": consequent_support_count,
                                        "Itemset_Support_Count": itemset_support_count,
                                        "Antecedent_Support": round(
                                            antecedent_support, 4
                                        ),
                                        "Consequent_Support": round(
                                            consequent_support, 4
                                        ),
                                        "Itemset_Support": round(itemset_support, 4),
                                        "Confidence": round(confidence, 4),
                                        "Lift": round(lift, 4),
                                        "Expected_Support": round(expected_support, 6),
                                        # TAMBAHAN: Field untuk deduplikasi
                                        "Itemset_ID": itemset_id,
                                        "Antecedent_Items": tuple(
                                            sorted(antecedent_items)
                                        ),
                                        "Consequent_Items": tuple(
                                            sorted(consequent_items)
                                        ),
                                    }
                                )

        self.logger.info(f"Generated {len(association_rules)} association rules")
        return association_rules

    def deduplicate_rules(self, association_rules):
        """
        Menghilangkan rules duplikat yang memiliki itemset sama tapi antecedent-consequent dibalik
        Contoh: A -> B dan B -> A dari itemset {A, B} akan direduksi menjadi 1 rule terbaik
        """
        self.logger.info("Starting rule deduplication process...")

        # Group rules berdasarkan itemset yang sama
        itemset_groups = defaultdict(list)

        for rule in association_rules:
            itemset_id = rule["Itemset_ID"]
            itemset_groups[itemset_id].append(rule)

        # Untuk setiap group, pilih rule terbaik
        deduplicated_rules = []
        duplicate_count = 0
        duplicate_examples = []

        for itemset_id, rules_group in itemset_groups.items():
            if len(rules_group) == 1:
                # Hanya ada 1 rule untuk itemset ini, langsung ambil
                deduplicated_rules.append(rules_group[0])
            else:
                # Ada multiple rules untuk itemset yang sama
                self.logger.debug(
                    f"Found {len(rules_group)} rules for itemset {itemset_id}"
                )

                # Prioritas pemilihan rule terbaik:
                # 1. Confidence tertinggi
                # 2. Jika confidence sama, pilih lift tertinggi
                # 3. Jika lift juga sama, pilih support tertinggi
                best_rule = max(
                    rules_group,
                    key=lambda r: (r["Confidence"], r["Lift"], r["Itemset_Support"]),
                )

                deduplicated_rules.append(best_rule)
                duplicate_count += len(rules_group) - 1

                # Simpan contoh duplikasi untuk logging
                if len(duplicate_examples) < 3:  # Simpan max 3 contoh
                    example = {
                        "kept": best_rule["Rule"],
                        "removed": [
                            rule["Rule"] for rule in rules_group if rule != best_rule
                        ],
                    }
                    duplicate_examples.append(example)

                # Log info tentang rules yang dihapus
                for rule in rules_group:
                    if rule != best_rule:
                        self.logger.debug(
                            f"Removed duplicate: {rule['Rule']} (Conf: {rule['Confidence']}, Lift: {rule['Lift']})"
                        )

                self.logger.debug(
                    f"Selected best: {best_rule['Rule']} (Conf: {best_rule['Confidence']}, Lift: {best_rule['Lift']})"
                )

        # Log summary dengan contoh
        self.logger.info(
            f"Deduplication completed: {len(association_rules)} -> {len(deduplicated_rules)} rules ({duplicate_count} duplicates removed)"
        )

        if duplicate_examples:
            self.logger.info("Examples of deduplication:")
            for i, example in enumerate(duplicate_examples, 1):
                self.logger.info(f"  {i}. Kept: {example['kept']}")
                for removed in example["removed"]:
                    self.logger.info(f"     Removed: {removed}")

        return deduplicated_rules

    def analyze_lift_distribution(self, association_rules):
        """Analisis distribusi nilai lift untuk debugging"""
        if not association_rules:
            return

        lifts = [rule["Lift"] for rule in association_rules]

        self.logger.info(f"Lift Analysis:")
        self.logger.info(f"Min Lift: {min(lifts):.4f}")
        self.logger.info(f"Max Lift: {max(lifts):.4f}")
        self.logger.info(f"Mean Lift: {np.mean(lifts):.4f}")
        self.logger.info(f"Median Lift: {np.median(lifts):.4f}")

        # Distribusi lift
        lift_ranges = {
            "< 0.5": len([l for l in lifts if l < 0.5]),
            "0.5-1.0": len([l for l in lifts if 0.5 <= l < 1.0]),
            "1.0-2.0": len([l for l in lifts if 1.0 <= l < 2.0]),
            "2.0-5.0": len([l for l in lifts if 2.0 <= l < 5.0]),
            "5.0-10.0": len([l for l in lifts if 5.0 <= l < 10.0]),
            ">= 10.0": len([l for l in lifts if l >= 10.0]),
        }

        self.logger.info(f"Lift Distribution:")
        for range_name, count in lift_ranges.items():
            percentage = (count / len(lifts)) * 100
            self.logger.info(f"{range_name}: {count} rules ({percentage:.1f}%)")

    # Di dalam class RuleGenerator, method generate_association_rules


# CARI BAGIAN INI (di bagian akhir method):


def generate_association_rules(
    self,
    all_tidlists,
    total_transactions,
    min_confidence=0.2,
    min_lift=1.0,
    min_support=0.01,
    deduplicate=True,
):
    """Generate association rules yang diperbaiki dengan filtering dan deduplikasi"""
    # ... kode lainnya ...

    # Filter berdasarkan min_support, min_confidence dan min_lift
    filtered_rules = []
    for rule in association_rules:
        if (
            rule["Itemset_Support"] >= min_support
            and rule["Confidence"] >= min_confidence
            and rule["Lift"] >= min_lift
        ):
            filtered_rules.append(rule)

    # GANTI SORTING INI:
    # filtered_rules.sort(key=lambda x: x["Lift"], reverse=True)

    # DENGAN SORTING YANG LEBIH ROBUST:
    filtered_rules.sort(
        key=lambda x: (
            x["Lift"],  # Primary: Lift tertinggi
            x["Confidence"],  # Secondary: Confidence tertinggi
            x["Itemset_Support"],  # Tertiary: Support tertinggi
        ),
        reverse=True,
    )

    self.logger.info(
        f"After filtering: {len(filtered_rules)} rules passed the thresholds"
    )

    # TAMBAHAN: Log top 5 rules untuk debugging
    if filtered_rules:
        self.logger.info("Top 5 rules by lift:")
        for i, rule in enumerate(filtered_rules[:5]):
            self.logger.info(
                f"  {i+1}. {rule['Rule']} (Lift: {rule['Lift']}, Conf: {rule['Confidence']})"
            )

    return filtered_rules


class EnhancedRuleValidator:
    """Class untuk validasi enhanced rules dengan data historis (UPDATED dengan deduplikasi)"""

    def __init__(self):
        self.logger = logger

    def deduplicate_enhanced_rules(self, enhanced_rules):
        """
        Deduplikasi khusus untuk enhanced rules yang mempertimbangkan:
        1. Original rule (2 produk)
        2. Added unsold product
        """
        self.logger.info("Starting enhanced rule deduplication...")

        # Group berdasarkan kombinasi 3 produk (termasuk unsold product)
        combination_groups = defaultdict(list)

        for rule in enhanced_rules:
            # Extract semua produk dalam enhanced rule
            antecedent_products = rule["Antecedent"].split(" + ")
            consequent_products = rule["Consequent"].split(" + ")
            unsold_product = rule.get("Added_Unsold_Product", "")

            # Buat set semua produk dalam kombinasi
            all_products = set(antecedent_products + consequent_products)
            if unsold_product:
                all_products.add(unsold_product)

            # ID unik untuk kombinasi 3 produk
            combination_id = tuple(sorted(all_products))
            combination_groups[combination_id].append(rule)

        # Pilih rule terbaik dari setiap group
        deduplicated_enhanced = []
        duplicate_count = 0

        for combination_id, rules_group in combination_groups.items():
            if len(rules_group) == 1:
                deduplicated_enhanced.append(rules_group[0])
            else:
                # Pilih berdasarkan prioritas:
                # 1. Historical occurrence count tertinggi
                # 2. Confidence tertinggi
                # 3. Lift tertinggi
                best_rule = max(
                    rules_group,
                    key=lambda r: (
                        r.get("Historical_Occurrence_Count", 0),
                        r.get("Confidence", 0),
                        r.get("Lift", 0),
                    ),
                )

                deduplicated_enhanced.append(best_rule)
                duplicate_count += len(rules_group) - 1

                self.logger.debug(
                    f"Enhanced dedup: kept {best_rule['Enhanced_Rule']} (Hist: {best_rule.get('Historical_Occurrence_Count', 0)})"
                )

        self.logger.info(
            f"Enhanced deduplication: {len(enhanced_rules)} -> {len(deduplicated_enhanced)} rules ({duplicate_count} duplicates removed)"
        )

        return deduplicated_enhanced

    def validate_enhanced_rules_with_historical_data(
        self, rules_2_product, unsold_products, historical_filepath
    ):
        """
        Validasi enhanced rules dengan data historis (data pesanan maret)
        """
        self.logger.info("=== VALIDATING ENHANCED RULES WITH HISTORICAL DATA ===")

        try:
            # Baca data historis
            file_handler = FileHandler()
            df_historical = file_handler.read_file(historical_filepath)

            if df_historical is None:
                return []

            # Skip header dan description row jika ada
            if len(df_historical) > 2 and str(df_historical.iloc[1, 0]).startswith(
                "Platform unique"
            ):
                df_historical = df_historical.iloc[2:].reset_index(drop=True)
                self.logger.info(
                    "Skipped header and description rows in historical data"
                )

            self.logger.info(f"Historical data loaded: {len(df_historical)} records")

            # Identifikasi kolom Seller SKU di data historis
            seller_sku_col = None
            for col in df_historical.columns:
                if "seller" in str(col).lower() and "sku" in str(col).lower():
                    seller_sku_col = col
                    break

            if not seller_sku_col:
                # Fallback: coba kolom index 6 (biasanya Seller SKU)
                if len(df_historical.columns) > 6:
                    seller_sku_col = df_historical.columns[6]

            # Group historical data by Order ID untuk analisis transaksi
            order_col = df_historical.columns[0]  # Biasanya Order ID di kolom pertama

            # Buat struktur transaksi dari data historis
            historical_transactions = {}
            for _, row in df_historical.iterrows():
                order_id = str(row[order_col])
                product_sku = str(row[seller_sku_col]).strip()

                if (
                    order_id
                    and product_sku
                    and product_sku.lower() not in ["nan", "none", ""]
                ):
                    if order_id not in historical_transactions:
                        historical_transactions[order_id] = set()
                    historical_transactions[order_id].add(product_sku)

            # Convert ke list of sets untuk analisis
            historical_transaction_sets = list(historical_transactions.values())

            # Validasi setiap rule 2 produk dengan unsold products
            enhanced_rules = []

            for rule in rules_2_product:
                # Extract produk dari rule 2 produk
                rule_products = set()

                # Parse antecedent dan consequent
                antecedent_products = rule["Antecedent"].split(" + ")
                consequent_products = rule["Consequent"].split(" + ")

                rule_products.update(antecedent_products)
                rule_products.update(consequent_products)

                # Untuk setiap produk tidak terjual, cek kombinasi 3 produk
                for unsold_product in unsold_products:
                    # Kombinasi 3 produk: 2 dari rule + 1 unsold
                    combination_3_products = rule_products.union({unsold_product})

                    # Hitung berapa kali kombinasi ini muncul dalam data historis
                    occurrence_count = 0

                    for transaction_set in historical_transaction_sets:
                        # Cek apakah semua 3 produk ada dalam transaksi ini
                        if combination_3_products.issubset(transaction_set):
                            occurrence_count += 1

                    # Jika kombinasi pernah muncul, buat enhanced rule
                    if occurrence_count > 0:
                        enhanced_rule = rule.copy()
                        enhanced_rule["Enhanced"] = True
                        enhanced_rule["Added_Unsold_Product"] = unsold_product
                        enhanced_rule["Historical_Occurrence_Count"] = occurrence_count
                        enhanced_rule["Original_Rule"] = rule["Rule"]
                        enhanced_rule["Validation_Source"] = (
                            "Historical Data (Pesanan Maret)"
                        )

                        # Update rule display
                        enhanced_rule["Enhanced_Rule"] = (
                            f"{rule['Antecedent']} + {rule['Consequent']} + {unsold_product}"
                        )
                        enhanced_rule["Enhanced_Products_Count"] = 3

                        # Estimasi metrics untuk enhanced rule
                        total_historical_transactions = len(historical_transaction_sets)
                        enhanced_support = (
                            occurrence_count / total_historical_transactions
                        )

                        enhanced_rule["Enhanced_Support"] = enhanced_support
                        enhanced_rule["Enhanced_Support_Count"] = occurrence_count
                        enhanced_rule["Historical_Total_Transactions"] = (
                            total_historical_transactions
                        )

                        enhanced_rules.append(enhanced_rule)

            # TAMBAHAN: Deduplikasi enhanced rules
            enhanced_rules = self.deduplicate_enhanced_rules(enhanced_rules)

            # Sort enhanced rules berdasarkan historical occurrence count
            enhanced_rules.sort(
                key=lambda x: x["Historical_Occurrence_Count"], reverse=True
            )

            self.logger.info(
                f"Enhanced rules with historical validation: {len(enhanced_rules)}"
            )

            return enhanced_rules

        except Exception as e:
            import traceback

            self.logger.error(f"Error in historical validation: {str(e)}")
            self.logger.error(traceback.format_exc())
            return []

    def generate_enhanced_association_rules(
        self,
        all_tidlists,
        total_transactions,
        unsold_products,
        historical_filepath,
        min_confidence=0.2,
        min_lift=1.0,
        min_support=0.01,
    ):
        """
        Generate enhanced association rules dengan alur yang benar:
        1. Generate 2-product rules dari data potongan (dengan deduplikasi)
        2. Tambahkan 1 unsold product
        3. Validasi kombinasi dengan data pesanan maret (dengan deduplikasi)
        """
        self.logger.info("=== GENERATING ENHANCED ASSOCIATION RULES ===")

        # Step 1: Generate rules dasar dari data potongan (dengan deduplikasi)
        rule_generator = RuleGenerator()
        base_rules = rule_generator.calculate_confidence_and_lift(
            all_tidlists, total_transactions
        )

        # Deduplikasi base rules
        base_rules = rule_generator.deduplicate_rules(base_rules)

        # Filter hanya rules 2 produk dan yang memenuhi kriteria
        two_product_rules = []
        for rule in base_rules:
            # Hitung total produk dalam rule
            antecedent_products = rule["Antecedent"].split(" + ")
            consequent_products = rule["Consequent"].split(" + ")
            total_products = len(antecedent_products) + len(consequent_products)

            if (
                total_products == 2
                and rule["Itemset_Support"] >= min_support
                and rule["Confidence"] >= min_confidence
                and rule["Lift"] >= min_lift
            ):
                two_product_rules.append(rule)

        self.logger.info(
            f"Found {len(two_product_rules)} unique rules with exactly 2 products from data potongan"
        )

        if not two_product_rules:
            self.logger.warning(
                "No 2-product rules found. Cannot create enhanced rules."
            )
            return {"original_rules": [], "enhanced_rules": [], "total_enhanced": 0}

        if not unsold_products:
            self.logger.warning(
                "No unsold products available. Returning 2-product rules without enhancement."
            )
            return {
                "original_rules": two_product_rules,
                "enhanced_rules": two_product_rules,
                "total_enhanced": len(two_product_rules),
            }

        # Step 2: Validasi dengan data historis (dengan deduplikasi enhanced)
        enhanced_rules = self.validate_enhanced_rules_with_historical_data(
            two_product_rules, unsold_products, historical_filepath
        )

        return {
            "original_rules": two_product_rules,
            "enhanced_rules": enhanced_rules,
            "total_enhanced": len(enhanced_rules),
            "historical_validation": True,
        }


class BundlingRecommendationSystem:
    """Main class untuk sistem rekomendasi bundling"""

    def __init__(self):
        self.file_handler = FileHandler()
        self.date_filter = DateFilter()
        self.product_analyzer = ProductAnalyzer()
        self.data_processor = DataProcessor()
        self.eclat_algorithm = EclatAlgorithm()
        self.rule_generator = RuleGenerator()
        self.enhanced_validator = EnhancedRuleValidator()
        self.logger = logger

    def get_top_products(self, transactions, top_n=10):
        """Mendapatkan top N produk berdasarkan frekuensi"""
        # Flatten list of transactions
        all_products = [item for sublist in transactions for item in sublist]
        # Count frequency
        product_counts = pd.Series(all_products).value_counts()
        # Get top N
        top_products = product_counts.head(top_n)
        return top_products

    def prepare_unsold_products_list(self, analysis_result):
        """Prepare list produk tidak terjual dari hasil analisis produk"""
        if not analysis_result or "unsold_products" not in analysis_result:
            self.logger.warning("No unsold products data available")
            return []

        unsold_list = []
        for product in analysis_result["unsold_products"]:
            # Gunakan nama produk (SKU Penjual) sebagai identifier
            product_name = product.get("name", "") or product.get("code", "")
            if product_name:
                unsold_list.append(product_name)

        self.logger.info(f"Prepared {len(unsold_list)} unsold products for analysis")
        return unsold_list

    def run_complete_analysis(
        self,
        main_filepath,
        product_filepath=None,
        historical_filepath=None,
        order_col="Order ID",
        product_col="Seller SKU",
        sku_id_col="SKU ID",
        date_col="Created Time",
        start_date=None,
        end_date=None,
        min_support=0.01,
        min_confidence=0.2,
        min_lift=1.0,
        min_support_count=2,
    ):
        """
        Menjalankan analisis lengkap sistem rekomendasi bundling
        """
        try:
            self.logger.info("=== STARTING COMPLETE BUNDLING ANALYSIS ===")

            # Step 1: Baca file utama
            df_main = self.file_handler.read_file(main_filepath)
            if df_main is None:
                return None, "Error reading main file"

            # Step 2: Analisis produk jika ada file produk
            product_analysis = None
            unsold_products = []

            if product_filepath:
                df_product = self.file_handler.read_file(product_filepath)
                if df_product is not None:
                    product_analysis, error = (
                        self.product_analyzer.analyze_product_sales(df_main, df_product)
                    )
                    if product_analysis:
                        unsold_products = self.prepare_unsold_products_list(
                            product_analysis
                        )

            # Step 3: Preprocess data transaksi
            if start_date and end_date and date_col:
                (
                    transactions,
                    error,
                    filtered_count,
                    total_count,
                    total_combined,
                    filtered_products,
                ) = self.data_processor.prepare_transactions_with_date_filter(
                    df_main,
                    order_col,
                    product_col,
                    sku_id_col,
                    date_col,
                    start_date,
                    end_date,
                    min_support_count,
                )
            else:
                (
                    transactions,
                    error,
                    filtered_count,
                    total_count,
                    total_combined,
                    filtered_products,
                ) = self.data_processor.prepare_transactions(
                    df_main, order_col, product_col, sku_id_col, min_support_count
                )

            if error:
                return None, error

            # Step 4: Jalankan ECLAT
            start_time = time.time()
            all_tidlists, max_itemset_level = self.eclat_algorithm.run_eclat(
                transactions, filtered_products, min_support
            )

            if not all_tidlists:
                return (
                    None,
                    f"Tidak ada itemsets yang ditemukan dengan min_support={min_support}",
                )

            # Step 5: Generate rules
            if unsold_products and historical_filepath:
                # Enhanced rules dengan validasi historis
                rules_result = (
                    self.enhanced_validator.generate_enhanced_association_rules(
                        all_tidlists,
                        len(transactions),
                        unsold_products,
                        historical_filepath,
                        min_confidence,
                        min_lift,
                        min_support,
                    )
                )
                rules = rules_result["enhanced_rules"]
                original_rules_count = len(rules_result["original_rules"])
                enhanced_rules_count = len(rules_result["enhanced_rules"])
            else:
                # Standard rules
                rules = self.rule_generator.generate_association_rules(
                    all_tidlists,
                    len(transactions),
                    min_confidence,
                    min_lift,
                    min_support,
                )
                original_rules_count = len(rules)
                enhanced_rules_count = 0

            process_time = time.time() - start_time

            # Step 6: Compile results
            result = {
                "rules": rules,
                "product_analysis": product_analysis,
                "transactions": transactions,
                "filtered_products": filtered_products,
                "top_products": self.get_top_products(transactions).to_dict(),
                "total_transactions": len(transactions),
                "unique_product_count": len(filtered_products),
                "process_time": process_time,
                "original_rules_count": original_rules_count,
                "enhanced_rules_count": enhanced_rules_count,
                "has_unsold_products": len(unsold_products) > 0,
                "has_historical_validation": historical_filepath is not None,
            }

            return result, None

        except Exception as e:
            import traceback

            error_msg = f"Error in complete analysis: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            return None, error_msg


# =========================== FLASK ROUTES dengan Class Integration ===========================

# Inisialisasi sistem rekomendasi
bundling_system = BundlingRecommendationSystem()


@app.route("/")
def index():
    """Halaman utama dengan triple file upload"""
    # Reset semua session data untuk fresh start
    keys_to_reset = [
        "transaction_filepath",
        "transaction_filename",
        "transaction_columns",
        "transaction_df_preview",
        "product_filepath",
        "product_filename",
        "product_columns",
        "product_df_preview",
        "historical_filepath",
        "historical_filename",
        "product_analysis",
        "rules",
        "min_support",
        "min_confidence",
        "min_lift",
    ]

    for key in keys_to_reset:
        session.pop(key, None)

    return render_template("index.html", algorithm="Enhanced ECLAT")


@app.route("/upload_status")
def upload_status():
    """API endpoint untuk mendapatkan status file yang sudah diupload"""
    try:
        status = {
            "main_analysis": {
                "uploaded": "transaction_filepath" in session,
                "filename": session.get("transaction_filename", ""),
                "required": True,
            },
            "product_master": {
                "uploaded": "product_filepath" in session,
                "filename": session.get("product_filename", ""),
                "required": False,
            },
            "historical_validation": {
                "uploaded": "historical_filepath" in session,
                "filename": session.get("historical_filename", ""),
                "required": False,
            },
        }

        # Count uploaded files
        uploaded_count = sum(
            1 for file_info in status.values() if file_info["uploaded"]
        )

        return {
            "success": True,
            "status": status,
            "uploaded_count": uploaded_count,
            "total_files": 3,
            "ready_for_analysis": status["main_analysis"]["uploaded"],
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route("/upload", methods=["POST"])
def upload_triple_files():
    """Handler upload untuk 3 file sekaligus menggunakan FileHandler class"""

    # Check if at least main analysis file is provided
    if "main_analysis_file" not in request.files:
        flash("File data analisis utama wajib diunggah", "danger")
        return redirect(url_for("index"))

    main_file = request.files["main_analysis_file"]
    product_file = request.files.get("product_master_file")
    historical_file = request.files.get("historical_validation_file")

    if main_file.filename == "":
        flash("File data analisis utama wajib dipilih", "danger")
        return redirect(url_for("index"))

    upload_results = []
    error_occurred = False

    try:
        # === UPLOAD MAIN ANALYSIS FILE (WAJIB) ===
        if main_file and bundling_system.file_handler.allowed_file(main_file.filename):
            try:
                main_filepath, main_filename = bundling_system.file_handler.save_file(
                    main_file, app.config["UPLOAD_FOLDER"]
                )

                if main_filepath:
                    session["transaction_filepath"] = main_filepath
                    session["transaction_filename"] = main_filename

                    # Validasi struktur file utama
                    df_main = bundling_system.file_handler.read_file(main_filepath)

                    if df_main is None:
                        error_occurred = True
                        flash("Error reading main analysis file", "danger")
                    else:
                        # Skip header dan description jika ada
                        if len(df_main) > 2 and str(df_main.iloc[1, 0]).startswith(
                            "Platform unique"
                        ):
                            df_main = df_main.iloc[2:].reset_index(drop=True)

                        # Validasi kolom yang diperlukan
                        required_columns = [
                            "Order ID",
                            "Seller SKU",
                            "SKU ID",
                            "Created Time",
                        ]
                        missing_columns = [
                            col
                            for col in required_columns
                            if col not in df_main.columns
                        ]

                        if missing_columns:
                            error_occurred = True
                            flash(
                                f"File data analisis utama tidak memiliki kolom yang diperlukan: {', '.join(missing_columns)}",
                                "danger",
                            )
                        else:
                            session["transaction_columns"] = df_main.columns.tolist()
                            session["transaction_df_preview"] = df_main.head(5).to_json(
                                orient="records"
                            )
                            upload_results.append(
                                f"✅ Data Analisis Utama: {main_filename} ({len(df_main)} records)"
                            )

            except Exception as e:
                error_occurred = True
                flash(f"Error processing main analysis file: {str(e)}", "danger")
        else:
            error_occurred = True
            flash("Format file data analisis utama tidak didukung", "danger")

        # === UPLOAD PRODUCT MASTER FILE (OPSIONAL) ===
        if (
            product_file
            and product_file.filename != ""
            and bundling_system.file_handler.allowed_file(product_file.filename)
        ):
            try:
                product_filepath, product_filename = (
                    bundling_system.file_handler.save_file(
                        product_file, app.config["UPLOAD_FOLDER"]
                    )
                )

                if product_filepath:
                    session["product_filepath"] = product_filepath
                    session["product_filename"] = product_filename

                    # Validasi file produk
                    df_product = bundling_system.file_handler.read_file(
                        product_filepath
                    )

                    if df_product is not None:
                        session["product_columns"] = df_product.columns.tolist()
                        session["product_df_preview"] = df_product.head(5).to_json(
                            orient="records"
                        )
                        upload_results.append(
                            f"✅ Data Master Produk: {product_filename} ({len(df_product)} products)"
                        )

            except Exception as e:
                flash(
                    f"Warning: Error processing product master file: {str(e)}",
                    "warning",
                )

        # === UPLOAD HISTORICAL VALIDATION FILE (OPSIONAL) ===
        if (
            historical_file
            and historical_file.filename != ""
            and bundling_system.file_handler.allowed_file(historical_file.filename)
        ):
            try:
                # Save dengan nama yang konsisten untuk easy detection
                historical_filepath, _ = bundling_system.file_handler.save_file(
                    historical_file,
                    app.config["UPLOAD_FOLDER"],
                    "data_pesanan_maret.xlsx",
                )

                if historical_filepath:
                    session["historical_filepath"] = historical_filepath
                    session["historical_filename"] = historical_file.filename

                    # Validasi file historis
                    df_historical = bundling_system.file_handler.read_file(
                        historical_filepath
                    )

                    if df_historical is not None:
                        # Skip header jika ada
                        if len(df_historical) > 2 and str(
                            df_historical.iloc[1, 0]
                        ).startswith("Platform unique"):
                            df_historical = df_historical.iloc[2:].reset_index(
                                drop=True
                            )

                        upload_results.append(
                            f"✅ Data Historis Validasi: {historical_file.filename} ({len(df_historical)} records)"
                        )

            except Exception as e:
                flash(
                    f"Warning: Error processing historical validation file: {str(e)}",
                    "warning",
                )

        # === HASIL UPLOAD ===
        if not error_occurred:
            # Tentukan next step berdasarkan file yang diupload
            has_product_file = "product_filepath" in session
            has_historical_file = "historical_filepath" in session
            skip_product_analysis = request.form.get("skipProductAnalysis") == "on"

            logger.info(
                f"Upload summary: Main=✅, Product={'✅' if has_product_file else '❌'}, Historical={'✅' if has_historical_file else '❌'}"
            )

            # Routing logic
            if has_product_file and not skip_product_analysis:
                return redirect(url_for("product_analysis"))
            else:
                if not has_product_file:
                    flash(
                        "Tidak ada file produk - akan menggunakan standard ECLAT tanpa enhanced features",
                        "info",
                    )

                if has_historical_file:
                    flash(
                        "Data historis tersedia untuk validasi enhanced rules",
                        "success",
                    )

                return redirect(url_for("configure"))

        else:
            return redirect(url_for("index"))

    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route("/product_analysis")
def product_analysis():
    """Halaman analisis produk menggunakan ProductAnalyzer class"""
    if "transaction_filepath" not in session:
        flash("Silakan unggah file data pesanan terlebih dahulu", "danger")
        return redirect(url_for("index"))

    if "product_filepath" not in session:
        flash(
            "File data produk tidak ditemukan. Silakan unggah data produk untuk melakukan analisis.",
            "warning",
        )
        return redirect(url_for("index"))

    try:
        logger.info("=== STARTING PRODUCT ANALYSIS ROUTE ===")

        # Baca file transaksi dan produk menggunakan FileHandler
        transaction_filepath = session["transaction_filepath"]
        df_transaction = bundling_system.file_handler.read_file(transaction_filepath)

        product_filepath = session["product_filepath"]
        df_product = bundling_system.file_handler.read_file(product_filepath)

        if df_transaction is None or df_product is None:
            flash("Error reading files", "danger")
            return redirect(url_for("index"))

        # Analisis menggunakan ProductAnalyzer
        analysis_result, error = bundling_system.product_analyzer.analyze_product_sales(
            df_transaction, df_product
        )

        if error:
            logger.error(f"Analysis error: {error}")
            flash(error, "danger")
            return redirect(url_for("index"))

        if not analysis_result:
            flash("Gagal melakukan analisis produk", "danger")
            return redirect(url_for("index"))

        # Simpan hasil analisis di session
        try:
            session["product_analysis"] = json.dumps(analysis_result, default=str)
            logger.info("Analysis result saved to session")
        except Exception as se:
            logger.warning(f"Failed to save to session: {se}")

        # Flash message untuk memberitahu hasil
        flash(
            f"Analisis produk berhasil! Dari {analysis_result['total_products']} produk master, "
            f"ditemukan {analysis_result['sold_products_count']} produk terjual "
            f"({analysis_result['sold_percentage']:.1f}%) dan "
            f"{analysis_result['unsold_products_count']} produk tidak terjual "
            f"({analysis_result['unsold_percentage']:.1f}%).",
            "success",
        )

        return render_template(
            "product_analysis.html",
            analysis=analysis_result,
            transaction_filename=session.get("transaction_filename", ""),
            product_filename=session.get("product_filename", ""),
        )

    except Exception as e:
        import traceback

        error_msg = f"Error dalam product_analysis route: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        flash(error_msg, "danger")
        return redirect(url_for("index"))


@app.route("/configure")
def configure():
    """Halaman konfigurasi dengan informasi upload status"""
    if "transaction_filepath" not in session:
        flash("Silakan unggah file data analisis utama terlebih dahulu", "danger")
        return redirect(url_for("index"))

    # Baca file dari session
    transaction_filename = session.get("transaction_filename", "")

    # Ambil preview yang sudah disimpan di session
    preview = None
    if "transaction_df_preview" in session:
        try:
            df_preview = pd.read_json(
                session.get("transaction_df_preview"), orient="records"
            )
            preview = df_preview.to_html(classes="table table-striped table-sm")
        except Exception as e:
            # Jika ada error, baca file lagi
            filepath = session.get("transaction_filepath")
            df = bundling_system.file_handler.read_file(filepath)
            if df is not None:
                preview = df.head().to_html(classes="table table-striped table-sm")

    # Validasi kolom
    required_columns = ["Order ID", "Seller SKU", "SKU ID", "Created Time"]
    missing_columns = [
        col
        for col in required_columns
        if col not in session.get("transaction_columns", [])
    ]

    if missing_columns:
        flash(
            f"Kolom yang diperlukan tidak ditemukan: {', '.join(missing_columns)}",
            "danger",
        )
        return redirect(url_for("index"))

    # Parameter default
    min_support = session.get("min_support", 0.01)
    min_confidence = session.get("min_confidence", 0.2)
    min_lift = session.get("min_lift", 1.0)

    # Check status upload
    has_product_analysis = "product_filepath" in session
    has_historical_data = "historical_filepath" in session

    return render_template(
        "configure.html",
        filename=transaction_filename,
        preview=preview,
        columns=session.get("transaction_columns", []),
        min_support=min_support,
        min_confidence=min_confidence,
        min_lift=min_lift,
        algorithm="Enhanced ECLAT",
        has_product_analysis=has_product_analysis,
        has_historical_data=has_historical_data,
        upload_status={
            "product_file": session.get("product_filename", "Tidak ada"),
            "historical_file": session.get("historical_filename", "Tidak ada"),
        },
    )


@app.route("/get_unique_dates", methods=["POST"])
def get_unique_dates():
    """API endpoint untuk mendapatkan tanggal unik menggunakan DateFilter class"""
    try:
        if "transaction_filepath" not in session:
            return {"success": False, "error": "File tidak ditemukan dalam session"}

        data = request.get_json()
        column_name = data.get("column")

        if not column_name:
            return {"success": False, "error": "Nama kolom tidak valid"}

        # Baca file
        filepath = session["transaction_filepath"]
        df = bundling_system.file_handler.read_file(filepath)

        if df is None:
            return {"success": False, "error": "Error reading file"}

        if column_name not in df.columns:
            return {"success": False, "error": f"Kolom {column_name} tidak ditemukan"}

        # Dapatkan tanggal unik menggunakan DateFilter
        unique_dates = bundling_system.date_filter.get_unique_dates_from_column(
            df, column_name
        )

        return {"success": True, "dates": unique_dates, "total_records": len(df)}

    except Exception as e:
        logger.error(f"Error getting unique dates: {str(e)}")
        return {"success": False, "error": str(e)}


@app.route("/preview_date_filter", methods=["POST"])
def preview_date_filter():
    """API endpoint untuk preview hasil filtering tanggal menggunakan DateFilter class"""
    try:
        if "transaction_filepath" not in session:
            return {"success": False, "error": "File tidak ditemukan dalam session"}

        data = request.get_json()
        column_name = data.get("column")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not all([column_name, start_date, end_date]):
            return {"success": False, "error": "Parameter tidak lengkap"}

        # Baca file
        filepath = session["transaction_filepath"]
        df = bundling_system.file_handler.read_file(filepath)

        if df is None:
            return {"success": False, "error": "Error reading file"}

        # Filter DataFrame menggunakan DateFilter
        filtered_df, error = bundling_system.date_filter.filter_dataframe_by_date_range(
            df, column_name, start_date, end_date
        )

        if error:
            return {"success": False, "error": error}

        return {
            "success": True,
            "filtered_count": len(filtered_df),
            "total_count": len(df),
        }

    except Exception as e:
        logger.error(f"Error previewing date filter: {str(e)}")
        return {"success": False, "error": str(e)}


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Analisis dengan Enhanced ECLAT Algorithm menggunakan BundlingRecommendationSystem
    """
    if "transaction_filepath" not in session:
        flash("Silakan unggah file data pesanan terlebih dahulu", "danger")
        return redirect(url_for("index"))

    try:
        # Parameter
        order_column = "Order ID"
        product_column = "Seller SKU"
        sku_id_column = "SKU ID"
        date_column = "Created Time"

        # Ambil parameter
        try:
            min_support = float(request.form.get("min_support", "0.01"))
            min_confidence = float(request.form.get("min_confidence", "0.2"))
            min_lift = float(request.form.get("min_lift", "1.0"))
        except ValueError as e:
            flash(f"Error parsing parameters: {str(e)}", "danger")
            return redirect(url_for("configure"))

        start_date = request.form.get("start_date", None)
        end_date = request.form.get("end_date", None)
        min_support_count = 2

        # Simpan parameter
        session["min_support"] = min_support
        session["min_confidence"] = min_confidence
        session["min_lift"] = min_lift

        # Get file paths
        main_filepath = session["transaction_filepath"]
        product_filepath = session.get("product_filepath")
        historical_filepath = session.get("historical_filepath")

        # Jalankan analisis lengkap menggunakan BundlingRecommendationSystem
        result, error = bundling_system.run_complete_analysis(
            main_filepath=main_filepath,
            product_filepath=product_filepath,
            historical_filepath=historical_filepath,
            order_col=order_column,
            product_col=product_column,
            sku_id_col=sku_id_column,
            date_col=date_column,
            start_date=start_date,
            end_date=end_date,
            min_support=min_support,
            min_confidence=min_confidence,
            min_lift=min_lift,
            min_support_count=min_support_count,
        )

        if error:
            flash(error, "danger")
            return redirect(url_for("configure"))

        # Simpan hasil
        session["rules"] = json.dumps(result["rules"], default=str)
        session["process_time"] = result["process_time"]
        session["original_rules_count"] = result["original_rules_count"]
        session["enhanced_rules_count"] = result["enhanced_rules_count"]

        # Flash success message
        if result["enhanced_rules_count"] > 0:
            flash(
                f"Berhasil generate {len(result['rules'])} enhanced rules dengan validasi historis! "
                f"({result['original_rules_count']} rules dasar → {result['enhanced_rules_count']} rules tervalidasi)",
                "success",
            )
        else:
            flash(
                f"Generated {len(result['rules'])} standard rules.",
                "info",
            )

        return render_template(
            "results.html",
            rules=result["rules"],
            top_products=result["top_products"],
            total_transactions=result["total_transactions"],
            display_total_transactions=result["total_transactions"],
            unique_product_count=result["unique_product_count"],
            filtered_count=0,
            total_count=result["total_transactions"],
            algorithm="Enhanced ECLAT (Class-based)",
            order_column=order_column,
            product_column=product_column,
            sku_id_column=sku_id_column,
            date_column=date_column,
            start_date=start_date,
            end_date=end_date,
            min_support=min_support,
            min_confidence=min_confidence,
            min_lift=min_lift,
            process_time=result["process_time"],
            has_unsold_products=result["has_unsold_products"],
            has_historical_validation=result["has_historical_validation"],
            original_rules_count=result["original_rules_count"],
            enhanced_rules_count=result["enhanced_rules_count"],
        )

    except Exception as e:
        import traceback

        logger.error(f"Error dalam enhanced analysis: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for("configure"))


@app.route("/export_rules")
def export_rules():
    """Export rules ke CSV"""
    try:
        # Cek apakah ada rules dalam session
        if "rules" not in session:
            flash("Tidak ada rules untuk diexport", "danger")
            return redirect(url_for("index"))

        # Ambil rules dari session
        rules_json = session.get("rules")

        # Cek apakah rules kosong
        if not rules_json or rules_json == "null" or rules_json == "[]":
            flash("Tidak ada rules yang tersedia untuk diexport", "warning")
            return redirect(url_for("index"))

        # Parse JSON rules
        try:
            rules = json.loads(rules_json)
        except json.JSONDecodeError as je:
            logger.error(f"Error decode JSON: {str(je)}")
            flash(f"Error format data: {str(je)}", "danger")
            return redirect(url_for("index"))

        # Cek lagi setelah parsing
        if not rules or len(rules) == 0:
            flash("Tidak ada rules yang tersedia untuk diexport", "warning")
            return redirect(url_for("index"))

        # Convert rules ke DataFrame
        df = pd.DataFrame(rules)

        # Buat CSV
        csv_data = df.to_csv(index=False)

        # Buat response file
        response = Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-disposition": f"attachment; filename=eclat_aturan_asosiasi_class_based.csv"
            },
        )

        # Set headers untuk mengatasi masalah encoding
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"

        return response

    except Exception as e:
        logger.error(f"Error saat export: {str(e)}")
        import traceback

        traceback.print_exc()
        flash(f"Error saat export: {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route("/api/get_rules_data")
def get_rules_data():
    """API endpoint untuk mendapatkan data rules untuk visualisasi"""
    try:
        # Cek apakah ada rules dalam session
        if "rules" not in session:
            return {"success": False, "error": "Tidak ada rules yang tersedia"}

        # Ambil rules dari session
        rules_json = session.get("rules")

        # Cek apakah rules kosong
        if not rules_json or rules_json == "null" or rules_json == "[]":
            return {"success": False, "error": "Tidak ada rules yang tersedia"}

        # Parse JSON rules
        try:
            rules = json.loads(rules_json)
        except json.JSONDecodeError as je:
            logger.error(f"Error decode JSON: {str(je)}")
            return {"success": False, "error": f"Error format data: {str(je)}"}

        # Cek lagi setelah parsing
        if not rules or len(rules) == 0:
            return {"success": False, "error": "Tidak ada rules yang tersedia"}

        return {"success": True, "rules": rules, "total_rules": len(rules)}

    except Exception as e:
        logger.error(f"Error dalam get_rules_data: {str(e)}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    app.run(debug=True)
