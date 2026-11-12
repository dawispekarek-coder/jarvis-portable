import unittest
from page_reader import PageUnavailable
import research_agent as r
def item(domain):
 return {'title':'LangGraph documentation','url':'https://'+domain+'/docs'}
def read(hit):
 return {'url':hit['url'],'title':hit['title'],'excerpt':'LangGraph official documentation explains states and durable persistence. '*3}
class FollowupTests(unittest.TestCase):
 def test_second_source_from_other_domain(self):
  a=item('site-a.org');b=item('site-b.org');calls=[]
  def find(q):
   calls.append(q)
   return {'results':[a] if len(calls)==1 else [a,b]}
  out=r.research('LangGraph state',find,read,lambda x:'Sources [1] and [2].')
  self.assertEqual(len(calls),2)
  self.assertEqual(out['followup']['read'],1)
  self.assertEqual(out['audit']['independent_domains'],2)
  self.assertIn(b['url'],out['reply'])
 def test_failed_followup_keeps_caveat(self):
  a=item('site-a.org');b=item('site-b.org');calls=[]
  def find(q):
   calls.append(q)
   return {'results':[a] if len(calls)==1 else [b]}
  def blocked(hit):
   if hit['url']==b['url']:raise PageUnavailable('403')
   return read(hit)
  out=r.research('LangGraph state',find,blocked,lambda x:'Source [1].')
  self.assertEqual(out['followup']['read'],0)
  self.assertIn('nepodařilo se načíst další',out['reply'])
  self.assertIn('chybí druhý nezávislý',out['reply'])
 def test_two_domains_no_followup(self):
  a=item('site-a.org');b=item('site-b.org');calls=[]
  def find(q):calls.append(q);return {'results':[a,b]}
  out=r.research('LangGraph state',find,read,lambda x:'Sources [1] and [2].')
  self.assertEqual(len(calls),1)
  self.assertFalse(out['followup']['attempted'])
 def test_no_pages_no_repeat(self):
  a=item('site-a.org');calls=[]
  def find(q):calls.append(q);return {'results':[a]}
  def denied(hit):raise PageUnavailable('403')
  out=r.research('LangGraph state',find,denied,lambda x:'never')
  self.assertEqual(len(calls),1)
  self.assertFalse(out['pages'])
if __name__=='__main__':unittest.main()
