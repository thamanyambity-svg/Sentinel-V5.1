# SENTINEL API Refactor Progress - api_server.py

## Approved Plan (2024)
- [ ] **Step 1**: Add missing imports (datetime.timedelta, uuid)
- [ ] **Step 2**: Replace parse_journal_log() → strict JSONL only, return [] if invalid
- [ ] **Step 3**: Fix get_journal() → remove @json_response + dead code
- [ ] **Step 4**: Add _get_ticks_raw() helper + fix get_full_dashboard()
- [ ] **Step 5**: Enhance format_ml_data() → exact HERO PANEL fields
- [ ] **Step 6**: Rename get_ml → get_decision + add /ml legacy alias
- [ ] **Step 7**: Update docs/index/print statements for /decision
- [ ] **Validation**: Test all endpoints

**Status**: Starting Step 1
