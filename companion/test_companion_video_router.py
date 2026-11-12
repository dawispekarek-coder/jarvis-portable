import unittest
from unittest.mock import patch
from pathlib import Path
import companion_video_router as vr

IMAGE=r"H:\LP18\assets\shot_01.png"
class TestVideoRouter(unittest.TestCase):
 def test_catalog_free_only(self):
  self.assertTrue(all(p["cost_usd"]==0 for p in vr.CATALOG))
  self.assertTrue(all(p["host"].endswith(".hf.space") for p in vr.CATALOG))
 def test_status(self):
  st=vr.status()
  self.assertEqual(st["zero_spend_hard_limit_usd"],0)
  self.assertEqual(len(st["providers"]),2)
 def test_refuse_unknown_files(self):
  with self.assertRaises(ValueError):vr.generate(r"C:\Windows\notepad.exe","move naturally",3)
 def test_no_upload_in_preview(self):
  with patch.object(vr,"_upload",side_effect=AssertionError("must not upload")):
   x=vr.generate(IMAGE,"Move naturally, no camera drift",3,execute=False)
   self.assertTrue(x["dry_run"]);self.assertFalse(x["submitted"])
 def test_quota_fallback(self):
  with patch.object(vr,"_info",return_value=["image"]),patch.object(vr,"_submit",side_effect=[vr.QuotaError("quota"),"https://second"]),patch.object(vr,"_wait",return_value="https://coderados-svd-img2vid-xt.hf.space/file.mp4"),patch.object(vr,"_download",return_value=r"H:\LP18\renders\cloud_videorouter\test.mp4"):
   x=vr.generate(IMAGE,"Wave your paw, no camera drift",3,execute=True)
   self.assertEqual(x["provider"],"svd_xt")
   self.assertEqual(len(vr.CATALOG),2)
   self.assertFalse(x["publish_allowed"])
 def test_no_duplicate_after_accepted(self):
  with patch.object(vr,"_info",return_value=["image"]),patch.object(vr,"_submit",return_value="https://first"),patch.object(vr,"_wait",side_effect=TimeoutError("slow")):
   x=vr.generate(IMAGE,"Walk slowly, no camera drift",3,execute=True)
   self.assertEqual(x["state"],"pending_or_failed")
   self.assertEqual(x["provider"],"wan14_fast")
 def test_web_only_not_auto(self):
  self.assertTrue(all("host" not in p for p in vr.WEB_ONLY))
if __name__=="__main__":unittest.main(verbosity=2)

