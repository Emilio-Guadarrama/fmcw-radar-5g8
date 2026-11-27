# hardware/exports/

Readable exports for review. The inspector agent can only read and search files, so provide:

| Export | Format | Status |
|---|---|---|
| BOM | CSV | [bom.csv](bom.csv): planning BOM, not a schematic export |
| Netlist | text | not available yet |
| DRC report | text | not available yet |
| Schematic, layout | PDF or images (PDF reading may need extra software) | not available yet |
| Fabrication files | Gerbers / ODB++ | not available yet |

## bom.csv
Snapshot of item rows 3-28 of the first sheet of [the BOM workbook](../../bom/FMCW_6GHz_BOM.xlsx), made 2026-11-27. The workbook is the source: regenerate or re-export the CSV after changing it.

- Column "Ext" was recalculated with the workbook's rule (quantity x unit price when included and priced, else 0).
- Title, totals, summary sheet, links and cell colors are not included.
- Prices are not rechecked. The workbook's known conflicts with the charter are listed in [requirements](../../docs/requirements.md), section 5.
- It is a copy of the BOM, so it keeps the BOM's MIT license.
