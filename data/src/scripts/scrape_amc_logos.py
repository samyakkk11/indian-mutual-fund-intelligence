import os
import time
import pandas as pd
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_CSV = r"A:\Power BI projects\indian-mutual-fund-intelligence\data\src\amc_logo_mapping.csv"

OUTPUT_CSV = r"A:\Power BI projects\indian-mutual-fund-intelligence\data\src\amc_logo_mapping_result.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 20
DELAY = 1


# ============================================================
# CLEAN DOMAIN
# ============================================================

def clean_domain(domain):

    if pd.isna(domain):
        return None

    domain = str(domain).strip()

    if not domain:
        return None

    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain

    return domain.rstrip("/")


# ============================================================
# DOWNLOAD WEBSITE HTML
# ============================================================

def get_html(domain):

    try:

        response = requests.get(
            domain,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

        return response.text, response.url

    except Exception as e:

        print(f"   Website error: {e}")

        return None, domain


# ============================================================
# SCORE LOGO
# ============================================================

def score_logo(img, image_url):

    score = 0

    src = image_url.lower()

    alt = str(
        img.get("alt", "")
    ).lower()

    title = str(
        img.get("title", "")
    ).lower()

    img_id = str(
        img.get("id", "")
    ).lower()

    classes = " ".join(
        img.get("class", [])
    ).lower()

    combined = " ".join([
        src,
        alt,
        title,
        img_id,
        classes
    ])

    # Strong logo indicators
    strong_keywords = [
        "logo",
        "brand-logo",
        "brand_logo",
        "site-logo",
        "site_logo",
        "header-logo",
        "header_logo",
        "company-logo",
        "company_logo"
    ]

    for keyword in strong_keywords:

        if keyword in combined:
            score += 10

    # Medium indicators
    medium_keywords = [
        "brand",
        "header",
        "navbar",
        "nav-logo",
        "company"
    ]

    for keyword in medium_keywords:

        if keyword in combined:
            score += 4

    # Prefer SVG
    if src.endswith(".svg"):
        score += 5

    # PNG
    elif src.endswith(".png"):
        score += 3

    return score


# ============================================================
# FIND LOGO
# ============================================================

def find_logo(html, base_url):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    candidates = []

    # ========================================================
    # METHOD 1: IMG TAGS
    # ========================================================

    for img in soup.find_all("img"):

        sources = [
            img.get("src"),
            img.get("data-src"),
            img.get("data-lazy-src"),
            img.get("data-original"),
            img.get("data-image")
        ]

        # ----------------------------------------------------
        # SRCSET
        # ----------------------------------------------------

        srcset = img.get("srcset")

        if srcset:

            first_source = (
                srcset
                .split(",")[0]
                .strip()
                .split(" ")[0]
            )

            sources.append(
                first_source
            )

        # ----------------------------------------------------
        # PROCESS SOURCES
        # ----------------------------------------------------

        for source in sources:

            if not source:
                continue

            if source.startswith("data:"):
                continue

            image_url = urljoin(
                base_url,
                source
            )

            score = score_logo(
                img,
                image_url
            )

            if score > 0:

                candidates.append(
                    (score, image_url)
                )

    # ========================================================
    # METHOD 2: OPEN GRAPH IMAGE
    # ========================================================

    og_image = soup.find(
        "meta",
        attrs={
            "property": "og:image"
        }
    )

    if og_image:

        content = og_image.get(
            "content"
        )

        if content:

            image_url = urljoin(
                base_url,
                content
            )

            candidates.append(
                (5, image_url)
            )

    # ========================================================
    # METHOD 3: LINK ICON
    # ========================================================

    for link in soup.find_all("link"):

        rel = " ".join(
            link.get("rel", [])
        ).lower()

        href = link.get("href")

        if not href:
            continue

        if "icon" in rel:

            image_url = urljoin(
                base_url,
                href
            )

            candidates.append(
                (2, image_url)
            )

    # ========================================================
    # NO CANDIDATES
    # ========================================================

    if not candidates:
        return None

    # ========================================================
    # SORT BY SCORE
    # ========================================================

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # Return URL + score
    return candidates[0]


# ============================================================
# VERIFY IMAGE URL
# ============================================================

def verify_image(url):

    if not url:
        return False, ""

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10,
            stream=True
        )

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        response.close()

        if "image/" in content_type:

            return True, content_type

        # Some servers return incorrect content type
        # but the URL itself clearly points to an image.

        path = urlparse(url).path.lower()

        image_extensions = [
            ".svg",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".ico"
        ]

        for extension in image_extensions:

            if path.endswith(extension):

                return True, extension.replace(".", "")

        return False, content_type

    except Exception:

        return False, ""


# ============================================================
# SAVE PROGRESS
# ============================================================

def save_progress(df):

    try:

        df.to_csv(
            OUTPUT_CSV,
            index=False,
            encoding="utf-8-sig"
        )

        return True

    except PermissionError:

        print(
            "\nERROR: Cannot write output CSV."
        )

        print(
            "Close the output CSV if it is open in Excel."
        )

        return False

    except Exception as e:

        print(
            f"\nERROR while saving: {e}"
        )

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("AMC OFFICIAL LOGO URL SCRAPER")
    print("=" * 65)

    print(
        f"\nInput:\n{INPUT_CSV}"
    )

    print(
        f"\nOutput:\n{OUTPUT_CSV}"
    )

    # ========================================================
    # CHECK INPUT FILE
    # ========================================================

    if not os.path.exists(INPUT_CSV):

        print(
            "\nERROR: Input CSV does not exist."
        )

        return

    # ========================================================
    # LOAD INPUT
    # ========================================================

    df = pd.read_csv(
        INPUT_CSV
    )

    print(
        f"\nLoaded {len(df)} AMC records."
    )

    # ========================================================
    # CHECK COLUMNS
    # ========================================================

    required_columns = [
        "amc",
        "domain",
        "logo_url",
        "status"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        print(
            f"\nERROR: Missing columns: "
            f"{missing_columns}"
        )

        print(
            "\nYour CSV must contain:"
        )

        print(
            "amc, domain, logo_url, status"
        )

        return

    # ========================================================
    # IF RESULT FILE ALREADY EXISTS
    # ========================================================

    if os.path.exists(OUTPUT_CSV):

        print(
            "\nExisting result file found."
        )

        try:

            result_df = pd.read_csv(
                OUTPUT_CSV
            )

            # Only use previous results if the
            # required columns exist.

            if all(
                column in result_df.columns
                for column in required_columns
            ):

                # ------------------------------------------------
                # Merge previous results into current dataframe
                # ------------------------------------------------

                for index, row in result_df.iterrows():

                    previous_amc = str(
                        row["amc"]
                    ).strip()

                    matches = df[
                        df["amc"].astype(str).str.strip()
                        == previous_amc
                    ]

                    if len(matches) == 0:
                        continue

                    original_index = matches.index[0]

                    previous_logo = row["logo_url"]
                    previous_status = row["status"]

                    if (
                        pd.notna(previous_logo)
                        and str(previous_logo).strip()
                    ):

                        df.at[
                            original_index,
                            "logo_url"
                        ] = previous_logo

                    if (
                        pd.notna(previous_status)
                        and str(previous_status).strip()
                    ):

                        df.at[
                            original_index,
                            "status"
                        ] = previous_status

                print(
                    "Previous progress loaded."
                )

        except Exception as e:

            print(
                f"Could not load previous results: {e}"
            )

    # ========================================================
    # PROCESS EACH AMC
    # ========================================================

    for index, row in df.iterrows():

        amc = str(
            row["amc"]
        ).strip()

        current_status = str(
            row["status"]
        ).strip().upper()

        # ----------------------------------------------------
        # SKIP ALREADY SUCCESSFUL AMC
        # ----------------------------------------------------

        if current_status == "SUCCESS":

            print(
                f"\n[{index + 1}/{len(df)}] {amc}"
            )

            print(
                "   Already successful — SKIPPING"
            )

            continue

        print(
            f"\n[{index + 1}/{len(df)}] {amc}"
        )

        # ----------------------------------------------------
        # GET DOMAIN
        # ----------------------------------------------------

        domain = clean_domain(
            row["domain"]
        )

        if not domain:

            print(
                "   No domain available."
            )

            df.at[
                index,
                "logo_url"
            ] = ""

            df.at[
                index,
                "status"
            ] = "NO DOMAIN"

            save_progress(df)

            continue

        print(
            f"   Domain: {domain}"
        )

        # ----------------------------------------------------
        # DOWNLOAD WEBSITE
        # ----------------------------------------------------

        html, final_url = get_html(
            domain
        )

        if not html:

            df.at[
                index,
                "logo_url"
            ] = ""

            df.at[
                index,
                "status"
            ] = "WEBSITE ERROR"

            save_progress(df)

            continue

        # ----------------------------------------------------
        # FIND LOGO
        # ----------------------------------------------------

        result = find_logo(
            html,
            final_url
        )

        if not result:

            print(
                "   Logo not found."
            )

            df.at[
                index,
                "logo_url"
            ] = ""

            df.at[
                index,
                "status"
            ] = "LOGO NOT FOUND"

            save_progress(df)

            time.sleep(DELAY)

            continue

        # ----------------------------------------------------
        # GET URL AND SCORE
        # ----------------------------------------------------

        logo_url = result[1]
        score = result[0]

        print(
            f"   Candidate: {logo_url}"
        )

        print(
            f"   Score: {score}"
        )

        # ----------------------------------------------------
        # VERIFY IMAGE
        # ----------------------------------------------------

        valid, content_type = verify_image(
            logo_url
        )

        if valid:

            df.at[
                index,
                "logo_url"
            ] = logo_url

            df.at[
                index,
                "status"
            ] = "SUCCESS"

            print(
                "   STATUS: SUCCESS"
            )

        else:

            df.at[
                index,
                "logo_url"
            ] = logo_url

            df.at[
                index,
                "status"
            ] = "UNVERIFIED"

            print(
                "   STATUS: UNVERIFIED"
            )

        # ----------------------------------------------------
        # SAVE PROGRESS
        # ----------------------------------------------------

        save_progress(df)

        # ----------------------------------------------------
        # DELAY
        # ----------------------------------------------------

        time.sleep(DELAY)

    # ========================================================
    # FINAL SAVE
    # ========================================================

    save_progress(df)

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n")
    print("=" * 65)
    print("SCRAPING COMPLETE")
    print("=" * 65)

    total = len(df)

    success = (
        df["status"]
        .astype(str)
        .str.upper()
        .eq("SUCCESS")
        .sum()
    )

    unverified = (
        df["status"]
        .astype(str)
        .str.upper()
        .eq("UNVERIFIED")
        .sum()
    )

    not_found = (
        df["status"]
        .astype(str)
        .str.upper()
        .eq("LOGO NOT FOUND")
        .sum()
    )

    website_errors = (
        df["status"]
        .astype(str)
        .str.upper()
        .eq("WEBSITE ERROR")
        .sum()
    )

    no_domain = (
        df["status"]
        .astype(str)
        .str.upper()
        .eq("NO DOMAIN")
        .sum()
    )

    print(
        f"\nTotal AMC records : {total}"
    )

    print(
        f"Successful        : {success}"
    )

    print(
        f"Unverified        : {unverified}"
    )

    print(
        f"Logo not found    : {not_found}"
    )

    print(
        f"Website errors    : {website_errors}"
    )

    print(
        f"No domain         : {no_domain}"
    )

    print(
        f"\nResult file:"
    )

    print(
        OUTPUT_CSV
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()