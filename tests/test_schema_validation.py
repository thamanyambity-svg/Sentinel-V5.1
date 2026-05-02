import unittest

from schema_validation import (
    validate_ml_signal_payload,
    validate_status_payload,
    validate_trade_history_payload,
)


class SchemaValidationTests(unittest.TestCase):
    def test_validate_status_payload_ok(self):
        ok, errors = validate_status_payload(
            {"balance": 1000.0, "equity": 1005.0, "positions": []}
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_validate_status_payload_invalid_positions(self):
        ok, errors = validate_status_payload({"positions": {}})
        self.assertFalse(ok)
        self.assertIn("positions must be a list", errors)

    def test_validate_trade_history_payload_ok(self):
        payload = {"trades": [{"pnl": 12.5, "time_open": 1710000000}]}
        ok, errors = validate_trade_history_payload(payload)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_validate_trade_history_payload_invalid(self):
        payload = {"trades": [{"pnl": "bad", "time_open": "bad"}]}
        ok, errors = validate_trade_history_payload(payload)
        self.assertFalse(ok)
        self.assertTrue(any("pnl must be numeric" in e for e in errors))
        self.assertTrue(any("time_open must be numeric timestamp" in e for e in errors))

    def test_validate_ml_signal_payload_ok(self):
        ok, errors = validate_ml_signal_payload({"direction": "BUY", "confidence": 0.82})
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_validate_ml_signal_payload_invalid(self):
        ok, errors = validate_ml_signal_payload({"direction": 42, "confidence": "high"})
        self.assertFalse(ok)
        self.assertIn("confidence must be numeric", errors)
        self.assertIn("direction must be a string", errors)

<<<<<<< ours

if __name__ == "__main__":
    unittest.main()

=======
    def test_validate_ml_signal_payload_invalid_ranges_and_values(self):
        ok, errors = validate_ml_signal_payload({"direction": "UP", "confidence": 1.5})
        self.assertFalse(ok)
        self.assertIn("confidence must be between 0.0 and 1.0", errors)
        self.assertIn("direction must be one of BUY/SELL/CALL/PUT/NEUTRAL", errors)


if __name__ == "__main__":
    unittest.main()
>>>>>>> theirs
