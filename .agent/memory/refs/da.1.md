# da.1 Parser and chunker design (Phase 1)
- doc_id from file name: pypdf text of 2026_ONCA_719 showed citation "2026 ONCA 7191" (footnote digit glued), same for 714 and 727. Title still read from CITATION line via pack regex.
- PyMuPDF used (cleaner than pypdf, which produced artefacts like "j udge"). Paragraph markers "[n]" on their own line; headings are all caps, either "III. ANALYSIS" or "A." then the title on the next line. First regex matched transcript answers ("A. So, you knew...") in 722 and 728 -> restricted to all-caps titles.
- Headings come before the first [1] marker; parser accepts headings anywhere, not only after the first marker.
- Sections: 12 of 15 sample decisions have headings; short decisions (<=15 paragraphs) have none -> one 'Reasons' section.
- Chunk token estimate is a cheap regex*1.3 to keep chunker free of torch; embedder truncates at 512.
- Bug found: psycopg opens a transaction on first SELECT, so conn.transaction() became a savepoint and recorded_run's rollback discarded inserts. Fixed with explicit commit in store_document. Second ingest run now reports unchanged=15.
- Known gaps: footnotes remain in paragraph text, no OCR, no lowercase headings.
