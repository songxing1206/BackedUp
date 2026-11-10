import base64,tempfile,unittest
from pathlib import Path
from pdf_fixture import make_pdf
from app.pdf_index import parse_pdf,range_regions
from app.retrieval import paragraphs,Retriever
from app.sources import AssetStore

class DocumentSchemaTests(unittest.TestCase):
 def fixture(self,root):
  rows=[(50,780,'Structured Evidence Study',20),(50,756,'Jane Smith, Alex Doe',12),(50,735,'2024 doi:10.1234/example.1',10),(50,700,'Abstract',14),(50,680,'Training improved recall in adults.'),(50,650,'Introduction',14),(50,625,'Left column first line.'),(50,605,'Left column second line.'),(50,585,'Left column third line.'),(330,625,'Right column first line.'),(330,605,'Right column second line.'),(330,585,'Right column third line.')]
  return make_pdf(Path(root)/'paper.pdf',pages=[rows])
 def test_unified_document_preserves_raw_links_and_markdown(self):
  with tempfile.TemporaryDirectory() as root:
   path=self.fixture(root);index=parse_pdf(path,'a'*32);document=index['document']
   self.assertEqual(document['schema_version'],'document-1');self.assertEqual(document['original_file']['source_id'],'a'*32)
   self.assertEqual(document['metadata']['title'],'Structured Evidence Study');self.assertIn('Jane Smith',document['metadata']['authors'][0]);self.assertEqual(document['metadata']['year'],'2024');self.assertEqual(document['metadata']['doi'],'10.1234/example.1')
   self.assertIn('Introduction',[s['title'] for s in document['sections']]);self.assertIn('# Structured Evidence Study',document['markdown'])
   paragraph=next(p for p in document['paragraphs'] if 'Left column first' in p['normalized_text']);self.assertTrue(paragraph['block_ids']);self.assertTrue(paragraph['pdf_refs'][0]['box'])
   blocks={b['id']:b for b in index['pages'][0]['blocks']};block=blocks[paragraph['block_ids'][0]];self.assertTrue(range_regions(index['pages'][0],block,0,len(block['text'].strip())))
 def test_two_column_order_and_document_bm25_use_same_raw_blocks(self):
  with tempfile.TemporaryDirectory() as root:
   index=parse_pdf(self.fixture(root),'b'*32);text=index['document']['pages'][0]['normalized_text']
   self.assertLess(text.index('Left column third'),text.index('Right column first'))
   units=list(paragraphs(index));ids={b['id'] for _,blocks in units for b in blocks};raw={b['id'] for p in index['pages'] for b in p['blocks']};self.assertTrue(ids);self.assertTrue(ids<=raw)
   selected=Retriever(Path(root)/'search').select(Retriever(Path(root)/'search').build(index),'recall adults')
   self.assertTrue(any('recall' in b['text'] for b in selected))
 def test_asset_upload_persists_document_separately_without_confirming_identity(self):
  with tempfile.TemporaryDirectory() as root:
   path=self.fixture(root);store=AssetStore(Path(root)/'assets');source=store.upload('paper.pdf',base64.b64encode(path.read_bytes()).decode())
   self.assertFalse(source['metadata_verified']);self.assertEqual(source['document_schema'],'document-1');self.assertTrue(store.document_path(source['id']).is_file());self.assertEqual(store.document(source['id'])['metadata']['title'],'Structured Evidence Study')

if __name__=='__main__':unittest.main()
