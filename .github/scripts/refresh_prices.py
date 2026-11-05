from __future__ import annotations

import base64
import json
import re
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

CATALOG_URL = "https://moton.by/catalog"
MIN_VARIANTS = 500


def main() -> None:
    request = urllib.request.Request(
        CATALOG_URL,
        headers={"User-Agent": "MOTON-price-feed/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        page = response.read().decode("utf-8", errors="replace")

    loader = re.search(
        r'<script\\b(?=[^>]*\\bid=["\\']moton-products-loader["\\'])[^>]*>(.*?)</script\\s*>',
        page,
        re.IGNORECASE | re.DOTALL,
    )
    if not loader:
        raise RuntimeError("MOTON catalog loader was not found")
    encoded = re.search(r"atob\\(['\\"]([^'\\"]+)['\\"]\\)", loader.group(1))
    if not encoded:
        raise RuntimeError("Compressed catalog data was not found")

    decoded = zlib.decompress(base64.b64decode(encoded.group(1))).decode("utf-8")
    products_match = re.search(
        r"var products=(\\[.*?\\]);var root=document\\.getElementById",
        decoded,
        re.DOTALL,
    )
    if not products_match:
        raise RuntimeError("Product array could not be read")
    products = json.loads(products_match.group(1))

    variants = []
    for product in products:
        for variant in product.get("variants") or []:
            sku = variant.get("sku")
            if sku is None or not str(sku).strip():
                continue
            variants.append(
                {
                    "sku": str(sku).strip(),
                    "price": variant.get("price"),
                    "brand": product.get("brand") or "",
                    "name": product.get("name") or "",
                    "volume": variant.get("volume"),
                }
            )

    if len(variants) < MIN_VARIANTS:
        raise RuntimeError(f"Catalog unexpectedly small: {len(variants)} variants")

    payload = {
        "source": CATALOG_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "products": variants,
    }
    Path("prices.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )
    print(f"Refreshed {len(variants)} variants from {len(products)} products")


if __name__ == "__main__":
    main()
