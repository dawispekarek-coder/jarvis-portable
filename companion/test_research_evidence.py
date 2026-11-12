import unittest
from unittest.mock import Mock
import research_agent as r
from research_evidence import assess,diverse_candidates
from page_reader import PageUnavailable
def hit(domain,name):
 return {"title":name,"url":"https://"+domain+"/docs"}
def page(item,text):
 return {"title":item["title"],"url":item["url"],"excerpt":text*3}
class EvidenceTests(unittest.TestCase):
 def test_diverse_hosts_before_repeats(self):
  links=[hit("docs.a.org","A1"),hit("docs.a.org","A2"),hit("docs.b.org","B1")]
  chosen=diverse_candidates(links)
  self.assertEqual([x["title"] for x in chosen],["A1","B1","A2"])
 def test_403_first_link_retries_later_domain(self):
  links=[hit("blocked.org","Block"),hit("docs.a.org","A"),hit("docs.b.org","B")]
  def fetch(item):
   if "blocked" in item["url"]:raise PageUnavailable("403")
   return page(item,"The public official documentation of LangGraph explains state graphs. ")
  bundle=r.collect("LangGraph docs",lambda q:{"results":links},fetch)
  self.assertEqual(len(bundle["pages"]),2)
  self.assertEqual(bundle["read_failures"],1)
  self.assertEqual(bundle["audit"]["independent_domains"],2)
  self.assertTrue(bundle["audit"]["recommended_verification"])
 def test_detect_possible_disagreement_without_claiming_proven(self):
  a=page(hit("one.org","A"),"This device supports 4 GB of memory and handles normal tasks. ")
  b=page(hit("two.org","B"),"This device supports 8 GB of memory and handles normal tasks. ")
  audit=assess({"pages":[a,b]})
  self.assertTrue(audit["potential_numeric_mismatches"])
  report=r.format_report({"query":"memory","pages":[a,b],"audit":audit},summary="Zdroj [1] a [2] mají odlišné údaje.")
  self.assertIn("Možný rozdíl",report)
  self.assertIn("nejde o potvrzený rozpor",report)
 def test_same_domain_is_not_independent(self):
  pages=[page(hit("same.org","A"),"This device supports 4 GB of memory. "),
         page(hit("same.org","B"),"This device supports 8 GB of memory. ")]
  audit=assess({"pages":pages})
  self.assertEqual(audit["independent_domains"],1)
  self.assertTrue(audit["sources_limited"])
  self.assertFalse(audit["potential_numeric_mismatches"])
 def test_mismatched_url_rejected(self):
  item=hit("right.org","Known")
  replaced=page(hit("wrong.org","Wrong"),"The documentation explains durable local state. ")
  data=r.collect("LangGraph docs",lambda q:{"results":[item]},lambda x:replaced)
  self.assertEqual(data["evidence_level"],1)
  self.assertFalse(data["pages"])
 def test_limits_attempts(self):
  hits=[hit("source"+str(i)+".org",str(i)+" doc") for i in range(10)]
  reader=Mock(side_effect=PageUnavailable("offline"))
  r.collect("LangGraph docs",lambda q:{"results":hits},reader)
  self.assertEqual(reader.call_count,5)
 def test_single_source_explicit_warning(self):
  a=page(hit("one.org","A"),"LangGraph allows state graph compilation with persistence. ")
  result=r.format_report({"query":"LangGraph","pages":[a]},summary="LangGraph informace [1].")
  self.assertIn("chybí druhý nezávislý zdroj",result)
  self.assertIn("https://one.org/docs",result)

 def test_model_must_not_invent_source_indices(self):
  import io,json
  from unittest.mock import patch
  a=page(hit("one.org","A"),"LangGraph official reference explains state graphs and persistence. ")
  bundle={"query":"LangGraph","pages":[a],"audit":assess({"pages":[a]})}
  for text,expected in (("Actual result from source [1].",True),
                        ("Unknown source [9] offers a fake proof.",False),
                        ("See https://fake.example/ for details.",False)):
   stream=io.BytesIO(json.dumps({"message":{"content":text}}).encode())
   with patch("research_agent.urllib.request.urlopen",return_value=stream):
    result=r.summarize_evidence(bundle)
   self.assertEqual(bool(result),expected,text)