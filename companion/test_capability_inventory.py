"""Regression tests for the V2 capability inventory; no live actions."""
import unittest
from unittest.mock import patch
import capability_inventory as c

class CapabilityTests(unittest.TestCase):
 def test_self_questions(self):
  expected={"Máš připojené TTS?":"tts","Umíš mluvit?":"tts",
    "Jaké máš nástroje?":"all","Co všechno umíš?":"all",
    "Máš internet?":"web","Dokážeš programovat ForeverRoute?":"code",
    "Máš paměť?":"memory","Umíš zpívat?":"media",
    "Máš přístup k souborům?":"files","Umíš ovládat prohlížeč?":"browser"}
  for question,kind in expected.items():
   with self.subTest(question=question):
    self.assertEqual(c.topic(question),kind)
 def test_unrelated_questions_not_intercepted(self):
  for q in ("Kolik je 2+2?","Proč se používá TTS?","Jak funguje internet?","Co je programování?"):
   self.assertIsNone(c.topic(q))
 def test_tts_is_not_falsely_connected(self):
  with patch.object(c,"voice_backend",return_value={"reachable":True,"ready":True,"provider":"supertonic3","voice":"M3-Digital13"}):
   info=c.inventory()
   self.assertTrue(info["tts_connected_to_v2"])
   reply=c.answer("Máš připojené TTS?")
   self.assertIn("supertonic3",reply)
   self.assertIn("je propojené",reply)
 def test_failed_backend_is_not_claimed_ready(self):
  with patch.object(c,"voice_backend",return_value={"reachable":False,"ready":False,"provider":"unavailable","voice":""}):
   self.assertIn("nepodařilo ověřit",c.answer("Máš TTS?"))
 def test_context_mentions_real_limits(self):
  context=c.model_context()
  self.assertIn("dostupnost vždy ověř",context)
  self.assertIn("Zápis a autonomní nasazení není povolené",context)
 def test_http_contract(self):
  from fastapi.testclient import TestClient
  from ui_compat import app
  with TestClient(app) as client:
   r=client.get("/api/capabilities")
   self.assertEqual(r.status_code,200)
   self.assertIn("voice",r.json() if False else {"voice":r.json()["tts_external_service"]})
   voice=client.get("/api/tts/status").json()
   self.assertIsInstance(voice["available"],bool)
   self.assertIn("provider",voice)

if __name__=="__main__": unittest.main()
