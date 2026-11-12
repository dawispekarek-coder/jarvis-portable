import unittest
from research_dates import date_hints,freshness_message
class DateEvidenceTests(unittest.TestCase):
 def test_only_labeled_iso_date_counts(self):
  pages=[
    {'excerpt':'Last updated: 2026-10-21. This article is about release notes.'},
    {'excerpt':'The product launched 2026-10-01 and includes 125 tasks.'}
  ]
  dates=date_hints(pages)
  self.assertEqual(len(dates),1)
  self.assertEqual(dates[0]['source'],1)
  self.assertEqual(dates[0]['date'],'2026-10-21')
  self.assertIn('nebyl nezávisle ověřen',freshness_message(pages))
 def test_no_date_cannot_claim_freshness(self):
  x=freshness_message([{'excerpt':'General documentation with no metadata'}])
  self.assertIn('nebylo zjištěno',x)
 def test_invalid_calendar_date_rejected(self):
  self.assertFalse(date_hints([{'excerpt':'Last updated: 2026-02-31.'}]))
 def test_future_date_not_accepted_as_current(self):
  hints=date_hints([{'excerpt':'Published: 2999-01-01.'}])
  self.assertEqual(hints[0]['status'],'future_label')
if __name__=='__main__':unittest.main()