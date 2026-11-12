"""Knowledge Inbox auto-reindex tests, isolated from live index."""
from pathlib import Path
from unittest.mock import patch
import tempfile,unittest
import knowledge

class KnowledgeRefreshTests(unittest.TestCase):
    def test_added_updated_deleted_file_reindexes(self):
        with tempfile.TemporaryDirectory(prefix='v2_knowledge_') as tmp:
            d=Path(tmp); inbox=d/'inbox'; inbox.mkdir()
            doc=inbox/'my_note.md'
            with patch.object(knowledge,'INBOX',inbox),patch.object(knowledge,'DB',d/'test.sqlite'):
                knowledge.refresh_if_needed()
                self.assertFalse(knowledge.status()['stale'])
                doc.write_text('# Note\nFresh keyword umiestneni4736 is documented here.',encoding='utf-8')
                self.assertTrue(knowledge.status()['stale'])
                result=knowledge.search('umiestneni4736')
                self.assertTrue(any(x['source']=='KnowledgeInbox/my_note.md' for x in result))
                self.assertFalse(knowledge.status()['stale'])
                doc.write_text('# Note\nChanged keyword uvodni9917 now replaces the old.',encoding='utf-8')
                self.assertTrue(knowledge.status()['stale'])
                self.assertTrue(any(x['source']=='KnowledgeInbox/my_note.md' for x in knowledge.search('uvodni9917')))
                self.assertFalse(any(x['source']=='KnowledgeInbox/my_note.md' for x in knowledge.search('umiestneni4736')))
                doc.unlink()
                self.assertTrue(knowledge.status()['stale'])
                self.assertFalse(any(x['source']=='KnowledgeInbox/my_note.md' for x in knowledge.search('uvodni9917')))
                self.assertFalse(knowledge.status()['stale'])

    def test_rejects_secret_names_and_other_extensions(self):
        with tempfile.TemporaryDirectory(prefix='v2_knowledge_') as tmp:
            d=Path(tmp);inbox=d/'inbox';inbox.mkdir()
            (inbox/'password.txt').write_text('Unusual word shh99933 is present.',encoding='utf-8')
            (inbox/'script.py').write_text('Unusual word shh99933 is present.',encoding='utf-8')
            with patch.object(knowledge,'INBOX',inbox),patch.object(knowledge,'DB',d/'test.sqlite'):
                knowledge.build_index()
                self.assertEqual(knowledge.search('shh99933'),[])

    def test_current_overview_precedes_history(self):
        hits=knowledge.search('Jaké levely pokrývá beta ForeverRoute?',4)
        self.assertTrue(hits)
        self.assertEqual(hits[0]['source'],'ForeverRoute/README.md')
        self.assertEqual(hits[0]['scope'],'project_docs')

if __name__=='__main__':unittest.main()
