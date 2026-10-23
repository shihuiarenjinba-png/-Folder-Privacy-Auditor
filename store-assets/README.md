# Store artwork gate — Folder Privacy Auditor

The MSIX workflow intentionally remains HOLD until real, owner-approved product artwork is committed.

Required files:

- `store-assets/assets/StoreLogo.png` — 50×50 PNG
- `store-assets/assets/Square44x44Logo.png` — 44×44 PNG
- `store-assets/assets/Square150x150Logo.png` — 150×150 PNG
- `store-assets/approval.json` — approval evidence matching this product

Do not copy another product's logo, use generated placeholder artwork, or mark approval without owner review.

After the real PNG files are reviewed, copy `approval.example.json` to `approval.json` and fill the actual evidence fields. The workflow requires `status=OWNER_APPROVED` and `product_key=folder-privacy-auditor`.
